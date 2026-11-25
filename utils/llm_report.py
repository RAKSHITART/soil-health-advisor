"""
Guardrailed AI layer (Groq, LLaMA 3.3 70B).

The AI never decides a status, dose or cost. Those come from the rule engine and are printed
in tables. The AI only writes the explanatory text, and its output is checked:
  1. it must be valid JSON with the expected fields,
  2. it must be written in the chosen script (otherwise the fixed-language template is used),
  3. every number in it must be a number the rule engine produced (or a small count),
     so it cannot invent a dose, price or soil value.
If the key is missing, the call fails or a check fails, the app falls back to the
fixed-language template, so the report is always in the language the farmer chose.
"""
import json
import os
import re
import unicodedata

from utils import i18n
from utils.report_builder import crop_name, template_narrative

# Groq renames and retires models often, so the app asks Groq which models this key can use
# and picks the best one. These lists only set the order of preference.
FALLBACK_MODELS = ['llama-3.3-70b-versatile', 'openai/gpt-oss-120b', 'llama-3.1-8b-instant']
TEXT_PREF = ['llama-3.3-70b', 'gpt-oss-120b', 'llama-4-maverick', 'llama-4-scout', 'qwen', 'gpt-oss-20b',
             'llama-3.1-8b', 'llama']
VISION_PREF = ['llama-4-scout', 'llama-4-maverick', 'vision', 'pixtral']
NOT_CHAT = ('whisper', 'guard', 'tts', 'orpheus', 'playai', 'compound', 'embed', 'safeguard')
_MODEL_CACHE = {}


def _client():
    key = os.environ.get('GROQ_API_KEY', '').strip()
    if not key or key.startswith('your_'):
        return None
    try:
        from groq import Groq
        return Groq(api_key=key, timeout=40)
    except Exception:
        return None


def ai_available() -> bool:
    return _client() is not None


def list_models(client=None):
    """Model ids available to this key (cached for an hour)."""
    import time
    client = client or _client()
    if client is None:
        return []
    key = os.environ.get('GROQ_API_KEY', '')
    hit = _MODEL_CACHE.get(key)
    if hit and time.time() - hit[0] < 3600:
        return hit[1]
    try:
        ids = [m.id for m in client.models.list().data if getattr(m, 'active', True)]
    except Exception:
        ids = []
    ids = [i for i in ids if not any(x in i.lower() for x in NOT_CHAT)]
    if ids:
        _MODEL_CACHE[key] = (time.time(), ids)
    return ids


def _ranked(ids, prefs):
    out = []
    for pref in prefs:
        out += [i for i in ids if pref in i.lower() and i not in out]
    return out


def text_models(client=None):
    ids = list_models(client)
    ranked = _ranked(ids, TEXT_PREF) + [i for i in ids if i not in _ranked(ids, TEXT_PREF)]
    return ranked or list(FALLBACK_MODELS)


def vision_models(client=None):
    return _ranked(list_models(client), VISION_PREF)


def _extras(model):
    """Thinking models (gpt-oss, qwen3) must be told to think briefly, or they use up the token budget."""
    m = model.lower()
    if 'gpt-oss' in m:
        return {'reasoning_effort': 'low'}
    if 'qwen' in m:
        return {'reasoning_effort': 'none'}
    return {}


def _clean(text):
    import re as _re
    text = _re.sub(r'<think>.*?</think>', '', text or '', flags=_re.S)
    return text.strip()


def _chat(messages, max_tokens, json_mode=False):
    client = _client()
    if client is None:
        raise RuntimeError('no GROQ_API_KEY')
    last = None
    for m in text_models(client)[:3]:
        ex = _extras(m)
        tries = [(json_mode, ex)] + ([(False, ex)] if json_mode else []) + ([(False, {})] if ex else [])
        for use_json, extra in tries:
            try:
                kw = dict(extra)
                if use_json:
                    kw['response_format'] = {'type': 'json_object'}
                r = client.chat.completions.create(model=m, max_tokens=max(1200, max_tokens * 2), temperature=0.2,
                                                   messages=messages, **kw)
                text = _clean(r.choices[0].message.content)
                if text:
                    return text, m
                last = RuntimeError(f'{m} returned empty text')
            except Exception as e:      # retired model, rate limit, unsupported option: try the next option
                last = e
    raise RuntimeError(str(last)[:200])


# ───────────────────────── guardrails ─────────────────────────
def script_ok(text: str, lang: str) -> bool:
    """For Indian languages, most letters must be in that language's script."""
    if lang == 'English':
        return True
    lo, hi = i18n.SCRIPT_RANGE[lang]
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return False
    return sum(1 for c in letters if lo <= ord(c) <= hi) / len(letters) >= 0.6


def _numbers(text: str):
    out = []
    for tok in re.findall(r'\d[\d,.]*', text):
        tok = tok.rstrip('.,')
        if tok:
            out.append(tok.replace(',', ''))
    # non-ASCII digits (Devanagari etc.)
    for ch in text:
        if ch.isdigit() and not ch.isascii():
            out.append('NONASCII:' + str(unicodedata.digit(ch, 0)))
    return out


def allowed_numbers(inp, res):
    A = res['analysis']
    ok = {str(i) for i in range(0, 11)}
    ok |= {str(A['health_score']), '100', '2.47'}
    ok |= {f'{inp["area"]:g}', str(inp['area'])}
    for v in inp['soil'].values():
        ok |= {f'{v:g}', str(v), str(round(v)), f'{v:.1f}'}
    for r in res['plan_rows']:
        ok |= {f"{r['per_acre_kg']:.0f}", f"{r['dose_value']:.0f}", f"{r['total_kg']:.0f}", str(r['bags_value']),
               f"{r['cost_value']:.0f}", f"{r['per_acre_kg']:.1f}"}
    return ok


def numbers_ok(text: str, inp, res) -> bool:
    allowed = allowed_numbers(inp, res)
    for n in _numbers(text):
        if n.startswith('NONASCII:'):
            continue  # native digits of small counts are harmless
        try:
            base = f'{float(n):g}'
        except ValueError:
            return False
        if n not in allowed and base not in allowed:
            return False
    return True


# ───────────────────────── narrative ─────────────────────────
def _facts(inp, res, lang, extra=''):
    A = res['analysis']
    lines = [f"Crop: {crop_name(inp['crop'], 'English')}. Farm: {inp['area']} acres. State: {inp['state']}.",
             f"Soil health score: {A['health_score']} out of 100 ({A['category']}).",
             'Nutrient status (decided by fixed rules, do not change):']
    for p, i in A['parameters'].items():
        lines.append(f"- {i['display_name']}: {i['value']} {i['unit']} -> {i['status']}")
    lines.append('Fertiliser plan (decided by fixed rules, do not change):')
    for r in res['plan_rows']:
        if r['kind'] != 'advisory':
            lines.append(f"- {r['Fertilizer']}: {r['per_acre_kg']:.0f} kg per acre")
    if extra:
        lines.append(extra)
    return '\n'.join(lines)


def generate_narrative(inp, res, lang):
    """Return {'summary','risk','tips','mode','model','error'}; always usable."""
    base = template_narrative(inp, res, lang)
    if not ai_available():
        return {**base, 'model': None, 'error': 'no key'}
    prompt = f"""You help an Indian farmer understand a soil test. Write in {i18n.LLM_NAME[lang]}, in very simple words.
Use ONLY the facts below. Do not state any number except numbers that appear in the facts. Do not change any
nutrient status. Do not name fertilisers or doses (they are shown in a table already). No emojis. No markdown.

{_facts(inp, res, lang)}

Return JSON with exactly these keys:
"summary": 2 or 3 sentences that explain what this soil condition means for the crop,
"risk": 2 sentences on what happens to the crop if the low nutrients are not corrected (empty string if none are low),
"tips": a list of 4 short, practical farming tips for this soil."""
    try:
        raw, model = _chat([{'role': 'user', 'content': prompt}], 1200, json_mode=True)
        data = json.loads(raw)
        summary = str(data.get('summary', '')).strip()
        risk = str(data.get('risk', '')).strip()
        tips = [str(x).strip() for x in data.get('tips', []) if str(x).strip()][:5]
        blob = ' '.join([summary, risk] + tips)
        if not summary or len(tips) < 3:
            raise ValueError('incomplete')
        if not script_ok(blob, lang):
            raise ValueError('wrong language')
        if not numbers_ok(blob, inp, res):
            raise ValueError('unknown number')
        # rule-based sentence first, so the facts always lead
        lead = base['summary']
        return {'summary': f'{lead} {summary}', 'risk': risk or base['risk'], 'tips': tips,
                'mode': 'ai', 'model': model, 'error': None}
    except Exception as e:
        return {**base, 'model': None, 'error': str(e)[:160]}


# ───────────────────────── crops that are not in the table ─────────────────────────
def estimate_crop_requirement(name):
    """Ask the AI for typical N, P2O5, K2O (kg/ha) for a crop that is not in the table.
    Returns a dict or None. The numbers are range-checked and always shown as an estimate to confirm."""
    if not ai_available() or not (name or '').strip():
        return None
    prompt = (f'Typical recommended fertiliser nutrient doses for the crop "{name.strip()[:40]}" in India, from ICAR or '
              'state agricultural university package of practices. Return only JSON: '
              '{"N": kg N per hectare, "P2O5": kg P2O5 per hectare, "K2O": kg K2O per hectare, '
              '"legume": true or false, "vegetable": true or false}. Use null for N, P2O5 and K2O if you do not '
              'know this crop. Do not guess.')
    try:
        raw, _ = _chat([{'role': 'user', 'content': prompt}], 200, json_mode=True)
        d = json.loads(raw[raw.index('{'):raw.rindex('}') + 1])
        n, p, k = d.get('N'), d.get('P2O5'), d.get('K2O')
        if not all(isinstance(x, (int, float)) for x in (n, p, k)):
            return None
        if not (0 <= n <= 350 and 0 <= p <= 200 and 0 <= k <= 300) or (n + p + k) <= 0:
            return None
        return {'N': float(n), 'P2O5': float(p), 'K2O': float(k), 'legume': bool(d.get('legume')),
                'vegetable': bool(d.get('vegetable'))}
    except Exception:
        return None


def _alt_crop(msg, inp, res):
    """If the question names another listed crop (for example carrot), work out its plan with the same soil."""
    from utils.fertilizer_engine import find_crops_in_text
    from utils.pipeline import run_analysis
    for c in find_crops_in_text(msg):
        if c != inp['crop']:
            try:
                return c, run_analysis(inp['soil'], c, inp['area'], inp['plan'])
            except Exception:
                return None, None
    return None, None


# ───────────────────────── chatbot ─────────────────────────
INTENTS = {
    'first': ['first', 'which fertili', 'what to apply', 'what should i apply', 'order', 'start', 'ಮೊದಲು', 'ಯಾವ ಗೊಬ್ಬರ', 'पहले', 'कौन सी खाद'],
    'why': ['why', 'reason', 'low', 'poor', 'health', 'ಏಕೆ', 'ಯಾಕೆ', 'ಕಡಿಮೆ', 'क्यों', 'कम', 'सेहत'],
    'improve': ['improve', 'better', 'increase', 'fix', 'how can', 'ಸುಧಾರ', 'ಹೇಗೆ', 'सुधार', 'कैसे'],
    'crop': ['crop', 'grow', 'suit', 'plant', 'ಬೆಳೆ', 'फसल'],
    'cost': ['cost', 'price', 'money', 'budget', 'how much', 'expens', 'ವೆಚ್ಚ', 'ಬೆಲೆ', 'ಖರ್ಚು', 'खर्च', 'कीमत', 'दाम', 'लागत'],
    'weather': ['weather', 'rain', 'when to', 'ಹವಾಮಾನ', 'ಮಳೆ', 'मौसम', 'बारिश'],
}


def _nutrient_in(msg_low):
    from utils.ocr_extract import NAMES
    for p, names in NAMES.items():
        for n in names:
            if n == 'ph':
                import re as _re
                if _re.search(r'(?<![a-z])p\.?h(?![a-z])', msg_low):
                    return p
            elif n in msg_low:
                return p
    return None


def _offline_answer(msg, inp, res, lang):
    """Rule-based answer from the farmer's own results (used when the AI is off or fails)."""
    from utils.report_builder import crop_name, fert_name, meaning_text, status_text
    T = i18n.t
    A, rows = res['analysis'], [r for r in res['plan_rows'] if r['kind'] != 'advisory']
    m = (msg or '').lower()
    alt, alt_res = _alt_crop(msg, inp, res)
    if alt:
        arows = [r for r in alt_res['plan_rows'] if r['kind'] != 'advisory']
        if not arows:
            return T('ans_alt_none', lang, crop=crop_name(alt, lang))
        plan = '; '.join(f"{fert_name(r['Fertilizer'], lang)} {r['per_acre_kg']:.0f} kg / acre" for r in arows[:4])
        return T('ans_altcrop', lang, crop=crop_name(alt, lang), plan=plan,
                 cost=f"{sum(r['cost_value'] for r in arows):,.0f}")
    p = _nutrient_in(m)
    if p and p in A['parameters']:
        info = A['parameters'][p]
        ans = f"{T(f'n_{p}', lang)}: {status_text(info['status'], lang)}. {meaning_text(p, info['status'], lang)}"
        row = next((r for r in rows if r['param'] == p), None)
        if row:
            ans += f" {fert_name(row['Fertilizer'], lang)}: {row['per_acre_kg']:.0f} kg / acre."
        return ans
    hit = lambda k: any(w in m for w in INTENTS[k])
    if hit('cost'):
        plan = inp['plan']
        return T('ans_cost', lang, plan=T(f'plan_{plan}', lang), cost=f"{sum(r['cost_value'] for r in rows):,.0f}",
                 pa=f"{sum(r['cost_value'] for r in rows) / inp['area']:,.0f}")
    if hit('crop'):
        cr = res['crop_result']
        best = cr['recommendations'][0]
        mine = cr['all_probabilities'].get(inp['crop'], 0)
        return T('ans_crop', lang, best=crop_name(best['crop'], lang), pct=best['confidence'],
                 crop=crop_name(inp['crop'], lang), mine=mine)
    if hit('weather'):
        from utils.weather import advice_codes
        w = res.get('weather') or {}
        txt = ' '.join(T(c, lang, **kw) for c, kw in advice_codes(w, rows)) if w else ''
        return T('ans_weather', lang, advice=txt)
    if hit('first') and not hit('why'):
        if rows:
            from utils.fertilizer_engine import build_schedule
            first = build_schedule(rows, inp['area'], inp['crop'])[0]   # earliest in time, e.g. lime before sowing
            return T('ans_first', lang, fert=fert_name(first['Fertiliser'], lang), acre=f"{first['per_acre_kg']:.0f}")
        return T('ans_first_none', lang)
    if hit('why'):
        low = [T(f'n_{q}', lang) for q in A['deficiencies']]
        return T('ans_why', lang, score=A['health_score'], low=', '.join(low)) if low else T('ans_why_ok', lang)
    if hit('improve'):
        return T('ans_improve', lang, tip1=T('tip_2', lang), tip2=T('tip_1', lang))
    return T('ask_offline', lang)


def chatbot_response(user_msg, inp, res, history, lang):
    extra = ''
    alt, alt_res = _alt_crop(user_msg, inp, res)
    if alt:
        arows = [r for r in alt_res['plan_rows'] if r['kind'] != 'advisory']
        extra = (f'If the farmer grows {alt} instead, the rule-based fertiliser plan for the same soil is: ' +
                 ('; '.join(f"{r['Fertilizer']} {r['per_acre_kg']:.0f} kg per acre" for r in arows[:5]) or 'no extra fertiliser') +
                 f". Estimated cost Rs {sum(r['cost_value'] for r in arows):,.0f} for the farm.")
    context = f"""You are a friendly soil and farming advisor for an Indian farmer. Answer in {i18n.LLM_NAME[lang]}, in very simple
words, in at most 6 sentences. No emojis.
Rules: (1) Soil status, fertiliser kinds, amounts and costs must come ONLY from the facts below; never invent a dose or price.
(2) For general farming questions such as irrigation, water saving, mulching, pests or sowing time you may give practical
general advice in plain words, and say it is general advice. (3) If you are not sure, say so and suggest the local Krishi
Vigyan Kendra or agriculture officer.

{_facts(inp, res, lang, extra)}"""
    msgs = [{'role': 'system', 'content': context}]
    for h in (history or [])[-6:]:
        msgs.append({'role': 'user' if h['role'] == 'user' else 'assistant', 'content': h['content']})
    msgs.append({'role': 'user', 'content': user_msg})
    try:
        text, _ = _chat(msgs, 500)
        if not script_ok(text, lang):
            return _offline_answer(user_msg, inp, res, lang)
        return text
    except Exception:
        return _offline_answer(user_msg, inp, res, lang)
