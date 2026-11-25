import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest

from utils import i18n
from utils import llm_report as L
from utils.crop_recommender import model_info, recommend_crops
from utils.fertilizer_engine import PLAN_KEYS, available_crops, build_schedule, get_recommendations
from utils.input_validation import validate_inputs
from utils.pdf_generator import generate_pdf
from utils.pipeline import run_analysis
from utils.report_builder import build_report, to_text
from utils.soil_analyzer import analyse_soil, get_regional_comparison

HEALTHY = dict(pH=6.8, Nitrogen=200, Phosphorus=40, Potassium=200, OrganicCarbon=0.8, Sulphur=20,
               Zinc=1.5, Iron=10, Copper=1.0, Manganese=8, Boron=0.6)
POOR = dict(pH=5.0, Nitrogen=60, Phosphorus=5, Potassium=60, OrganicCarbon=0.2, Sulphur=5,
            Zinc=0.3, Iron=2, Copper=0.1, Manganese=1, Boron=0.1)
EXCESS = dict(pH=9.2, Nitrogen=500, Phosphorus=200, Potassium=600, OrganicCarbon=2.5, Sulphur=80,
              Zinc=10, Iron=40, Copper=5, Manganese=40, Boron=3)


def inp(soil, crop='Rice', plan='Balanced', area=3.0):
    return dict(farmer='Ramesh', village='Khanna', district='Ludhiana', state='Punjab', area=area, crop=crop,
                plan=plan, soil=soil)


@pytest.mark.parametrize('soil', [HEALTHY, POOR, EXCESS])
@pytest.mark.parametrize('crop', available_crops())
@pytest.mark.parametrize('plan', list(PLAN_KEYS))
def test_full_pipeline(soil, crop, plan):
    r = run_analysis(soil, crop, 2.5, plan, 'Punjab', 'Ludhiana')
    assert 0 <= r['analysis']['health_score'] <= 100
    assert r['projected']['score_after'] >= r['analysis']['health_score']


def test_healthy_gets_maintenance_not_empty():
    assert any(x['Fertilizer'] == 'Urea' for x in run_analysis(HEALTHY, 'Wheat', 1)['plan_rows'])


def test_doses_are_crop_specific():
    a = analyse_soil(POOR)
    urea = lambda c: next(x['dose_value'] for x in get_recommendations(a, c)['balanced_plan'] if x['Fertilizer'] == 'Urea')
    assert urea('Sugarcane') > urea('Rice')


def test_excess_is_skipped_not_fertilised():
    plan = get_recommendations(analyse_soil(EXCESS), 'Rice')['balanced_plan']
    assert not any(x['Fertilizer'] == 'Urea' for x in plan)
    assert any(x['kind'] == 'advisory' for x in plan)


def test_cost_scales_with_area():
    a = analyse_soil(POOR)
    assert get_recommendations(a, 'Rice', 4)['balanced_cost_value'] > 3.9 * get_recommendations(a, 'Rice', 1)['balanced_cost_value']


def test_per_acre_is_per_hectare_over_2_47():
    row = get_recommendations(analyse_soil(POOR), 'Rice', 1)['balanced_plan'][0]
    assert abs(row['per_acre_kg'] - row['dose_value'] / 2.47105) < 0.1


def test_model_is_honest_and_guarded():
    assert 60 < model_info()['test_accuracy'] < 99.5
    assert recommend_crops(EXCESS)['reliability'] == 'Low'
    assert recommend_crops(HEALTHY)['reliability'] == 'High'


def test_regional_fallbacks():
    assert get_regional_comparison('Punjab', 'Ludhiana', HEALTHY)['level'] == 'district'
    assert get_regional_comparison('Karnataka', 'Dharwad', HEALTHY)['level'] == 'state'
    assert not get_regional_comparison('Nowhere', 'X', HEALTHY)['found']


# ── input validation
def test_validation_blocks_bad_input():
    assert validate_inputs('', '', '', 0, dict(HEALTHY))
    assert validate_inputs('A', 'V', 'D', 2, {k: 0 for k in HEALTHY})
    bad = dict(HEALTHY, pH=15)
    assert any('15' in e for e in validate_inputs('A', 'V', 'D', 2, bad))
    assert not validate_inputs('A', 'V', 'D', 2, dict(HEALTHY))


def test_validation_messages_are_localised():
    msg = validate_inputs('', 'V', 'D', 2, dict(HEALTHY), 'Hindi')[0]
    assert 'किसान' in msg


# ── translations
def test_every_code_has_six_languages():
    assert all(len(v) == 6 for v in i18n._T.values())


@pytest.mark.parametrize('soil', [HEALTHY, POOR, EXCESS])
@pytest.mark.parametrize('crop', available_crops())
@pytest.mark.parametrize('plan', list(PLAN_KEYS))
def test_every_engine_code_is_translated(soil, crop, plan):
    for r in run_analysis(soil, crop, 2, plan)['plan_rows']:
        label = r['issue'] if r['issue'].startswith('i_') else f"n_{r['param']}"
        for c in [r['method_code'], r['timing_code'], *r['note_codes'], f"f_{r['Fertilizer']}", label]:
            assert i18n.has(c), c
    for c in available_crops():
        assert i18n.has(f'c_{c}')


@pytest.mark.parametrize('lang', i18n.LANGS[1:])
def test_report_is_in_selected_language(lang):
    r = run_analysis(POOR, 'Rice', 3)
    rep = build_report(inp(POOR), r, lang)
    text = to_text(rep)
    lo, hi = i18n.SCRIPT_RANGE[lang]
    letters = [c for c in text if c.isalpha()]
    share = sum(1 for c in letters if lo <= ord(c) <= hi) / len(letters)
    assert share > 0.5, share
    for english in ('Apply as basal', 'Mix into the soil', 'Very low', 'Your soil'):
        assert english not in text


@pytest.mark.parametrize('lang', i18n.LANGS)
def test_pdf_builds_in_every_language(lang):
    r = run_analysis(POOR, 'Rice', 3)
    pdf = generate_pdf(build_report(inp(POOR), r, lang))
    assert pdf[:4] == b'%PDF' and len(pdf) > 10000


# ── AI guardrails
def test_script_and_number_guards():
    r = run_analysis(POOR, 'Rice', 3)
    assert not L.numbers_ok('Add 999 kg of urea', inp(POOR), r)
    assert L.numbers_ok('The score is 13 and zinc is 0.3', inp(POOR), r)
    assert not L.script_ok('plain english text', 'Hindi')
    assert L.script_ok('मिट्टी की सेहत बहुत कमजोर है', 'Hindi')


def _fake(monkeypatch, payload):
    import json
    monkeypatch.setattr(L, 'ai_available', lambda: True)
    monkeypatch.setattr(L, '_chat', lambda *a, **k: (json.dumps(payload), 'fake-model'))


def test_ai_text_is_accepted_when_valid(monkeypatch):
    _fake(monkeypatch, {'summary': 'मिट्टी में कई पोषक तत्वों की कमी है।', 'risk': 'फसल कमजोर रहेगी।',
                        'tips': ['गोबर की खाद डालें।', 'फसल चक्र अपनाएं।', 'मिट्टी की जांच कराएं।']})
    n = L.generate_narrative(inp(POOR), run_analysis(POOR, 'Rice', 3), 'Hindi')
    assert n['mode'] == 'ai'


def test_ai_text_with_invented_dose_is_rejected(monkeypatch):
    _fake(monkeypatch, {'summary': 'प्रति एकड़ 777 किलो यूरिया डालें।', 'risk': 'x', 'tips': ['a', 'b', 'c']})
    n = L.generate_narrative(inp(POOR), run_analysis(POOR, 'Rice', 3), 'Hindi')
    assert n['mode'] == 'rules'


def test_ai_text_in_wrong_language_is_rejected(monkeypatch):
    _fake(monkeypatch, {'summary': 'The soil is poor and needs care.', 'risk': 'Crop will suffer.',
                        'tips': ['Add manure.', 'Rotate crops.', 'Test soil.']})
    n = L.generate_narrative(inp(POOR), run_analysis(POOR, 'Rice', 3), 'Kannada')
    assert n['mode'] == 'rules'


def test_no_key_falls_back_to_selected_language(monkeypatch):
    monkeypatch.delenv('GROQ_API_KEY', raising=False)
    n = L.generate_narrative(inp(POOR), run_analysis(POOR, 'Rice', 3), 'Tamil')
    assert n['mode'] == 'rules' and L.script_ok(n['summary'], 'Tamil')


# ── app smoke test (runs the real Streamlit script)
def test_app_runs_and_blocks_empty_form():
    from streamlit.testing.v1 import AppTest
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    at = AppTest.from_file(os.path.join(root, 'app.py'), default_timeout=120).run()
    assert not at.exception
    [b for b in at.button if b.key == 'submit'][0].click()
    at.run()
    assert not at.exception and at.error, 'empty form must show validation errors'


def test_full_flow_in_every_ui_language():
    from streamlit.testing.v1 import AppTest
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    at = AppTest.from_file(os.path.join(root, 'app.py'), default_timeout=180).run()
    [b for b in at.button if b.key == 'ex1'][0].click()
    at.run()
    [b for b in at.button if b.key == 'submit'][0].click()
    at.run()
    assert not at.exception and at.session_state.res is not None
    for native in ('ಕನ್ನಡ', 'हिन्दी', 'English'):
        at.sidebar.radio[0].set_value(native).run()
        assert not at.exception
        assert at.session_state.in_name == 'Mallesh Gowda'


def test_back_to_edit_keeps_the_form_values():
    from streamlit.testing.v1 import AppTest
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    at = AppTest.from_file(os.path.join(root, 'app.py'), default_timeout=180).run()
    [b for b in at.button if b.key == 'ex1'][0].click()
    at.run()
    [b for b in at.button if b.key == 'submit'][0].click()
    at.run()
    [b for b in at.button if b.key == 'back'][0].click()
    at.run()
    assert not at.exception
    assert at.session_state.in_P == 14.0 and at.session_state.in_crop == 'Groundnut'


def test_weather_failure_is_reported_not_hidden(monkeypatch):
    from utils import weather as W
    monkeypatch.setattr(W, '_get', lambda *a, **k: (_ for _ in ()).throw(OSError('network down')))
    w = W.get_weather('Dharwad', 'Karnataka')
    assert w['mock'] is True and 'network down' in w['error'] and len(w['forecast']) == 7


def test_weather_success_parses_and_clears_error(monkeypatch):
    from utils import weather as W
    geo = {'results': [{'latitude': 15.4, 'longitude': 75.0, 'name': 'Dharwad', 'admin1': 'Karnataka', 'country_code': 'IN'}]}
    fc = {'current': {'temperature_2m': 29.1, 'relative_humidity_2m': 66, 'precipitation': 0.0, 'weather_code': 2},
          'daily': {'time': ['2026-11-22'] * 7, 'temperature_2m_max': [31] * 7, 'temperature_2m_min': [19] * 7,
                    'precipitation_sum': [0] * 7, 'precipitation_probability_max': [5] * 7}}
    monkeypatch.setattr(W, '_get', lambda url, **k: geo if 'geocoding' in url else fc)
    w = W.get_weather('Dharwad', 'Karnataka')
    assert w['mock'] is False and w['error'] is None and w['temperature'] == 29.1


def test_ssl_context_builds():
    from utils.weather import _ssl_context
    assert _ssl_context() is not None


# ── Groq model discovery (models get renamed and retired)
class _Mod:
    def __init__(self, i, active=True):
        self.id, self.active = i, active


class _FakeClient:
    def __init__(self, ids, bad=()):
        self._ids, self._bad = ids, set(bad)
        self.models = type('M', (), {'list': lambda s: type('R', (), {'data': [_Mod(i) for i in ids]})()})()
        outer = self
        self.chat = type('C', (), {'completions': type('CC', (), {'create': lambda s, **k: outer._create(**k)})()})()

    def _create(self, model, **k):
        if model in self._bad:
            raise RuntimeError('404 model does not exist')
        msg = type('Msg', (), {'content': f'answer from {model}'})()
        return type('Resp', (), {'choices': [type('Ch', (), {'message': msg})()]})()


def test_model_discovery_prefers_best_and_skips_non_chat(monkeypatch):
    ids = ['whisper-large-v3', 'llama-3.1-8b-instant', 'meta-llama/llama-guard-4-12b', 'openai/gpt-oss-120b',
           'llama-3.3-70b-versatile', 'meta-llama/llama-4-scout-17b-16e-instruct']
    c = _FakeClient(ids)
    L._MODEL_CACHE.clear()
    monkeypatch.setenv('GROQ_API_KEY', 'gsk_test')
    assert L.text_models(c)[0] == 'llama-3.3-70b-versatile'
    assert not any('whisper' in m or 'guard' in m for m in L.text_models(c))
    assert L.vision_models(c)[0].startswith('meta-llama/llama-4-scout')


def test_chat_falls_through_a_retired_model(monkeypatch):
    c = _FakeClient(['llama-3.3-70b-versatile', 'openai/gpt-oss-120b'], bad=['llama-3.3-70b-versatile'])
    L._MODEL_CACHE.clear()
    monkeypatch.setenv('GROQ_API_KEY', 'gsk_test')
    monkeypatch.setattr(L, '_client', lambda: c)
    text, used = L._chat([{'role': 'user', 'content': 'hi'}], 10)
    assert used == 'openai/gpt-oss-120b' and 'answer from' in text


def test_model_list_failure_uses_fallback_names(monkeypatch):
    c = _FakeClient([])
    L._MODEL_CACHE.clear()
    monkeypatch.setenv('GROQ_API_KEY', 'gsk_test2')
    assert L.text_models(c) == L.FALLBACK_MODELS


def test_empty_reply_from_thinking_model_falls_through_and_think_tags_are_stripped(monkeypatch):
    calls = []

    class C(_FakeClient):
        def _create(self, model, **k):
            calls.append((model, k.get('reasoning_effort')))
            text = '' if 'gpt-oss' in model else '<think>hidden thoughts</think>final answer'
            msg = type('Msg', (), {'content': text})()
            return type('Resp', (), {'choices': [type('Ch', (), {'message': msg})()]})()

    c = C(['openai/gpt-oss-120b', 'qwen/qwen3.8-27b'])
    L._MODEL_CACHE.clear()
    monkeypatch.setenv('GROQ_API_KEY', 'gsk_test3')
    monkeypatch.setattr(L, '_client', lambda: c)
    text, used = L._chat([{'role': 'user', 'content': 'hi'}], 20)
    assert text == 'final answer' and used.startswith('qwen')
    assert calls[0] == ('openai/gpt-oss-120b', 'low')      # thinking kept short


# ── EC (salinity), more crops, crops that are not in the table
def test_ec_is_classified_and_warns():
    a = analyse_soil(dict(HEALTHY, EC=0.4))
    assert a['parameters']['EC']['status'] == 'Optimal'
    assert analyse_soil(dict(HEALTHY, EC=1.6))['parameters']['EC']['status'] == 'High'
    assert analyse_soil(dict(HEALTHY, EC=3.5))['parameters']['EC']['status'] == 'Excessive'
    r = run_analysis(dict(HEALTHY, EC=3.5), 'Wheat', 2)
    for lang in ('English', 'Kannada', 'Hindi'):
        rep = build_report(inp(dict(HEALTHY, EC=3.5), 'Wheat'), r, lang)
        assert rep['warnings'] and any(row['name'] == i18n.t('n_EC', lang) for row in rep['soil_rows'])
        assert generate_pdf(rep)[:4] == b'%PDF'


def test_carrot_and_other_listed_crops_have_plans():
    assert len(available_crops()) >= 25 and 'Carrot' in available_crops()
    r = run_analysis(dict(HEALTHY, OrganicCarbon=0.4), 'Carrot', 2)
    assert any(x['Fertilizer'] == 'Urea' for x in r['plan_rows'])


def test_crop_name_matching_in_three_languages():
    from utils.fertilizer_engine import find_crops_in_text, match_crop
    assert match_crop('carrot') == match_crop('ಗಜ್ಜರಿ') == match_crop('गाजर') == 'Carrot'
    assert find_crops_in_text('I want to grow carrot, what should I do') == ['Carrot']
    assert match_crop('dragon fruit') is None


def test_chat_answers_about_another_crop_from_the_rules():
    from utils.llm_report import chatbot_response
    i = inp(HEALTHY, 'Wheat')
    r = run_analysis(HEALTHY, 'Wheat', 3)
    for q, lang in (('I want to grow carrot what should I do', 'English'), ('ನಾನು ಗಜ್ಜರಿ ಬೆಳೆಯಬಹುದೇ', 'Kannada'),
                    ('मैं गाजर उगाना चाहता हूं', 'Hindi')):
        ans = chatbot_response(q, i, r, [], lang)
        assert 'kg' in ans and 'Rs' in ans or 'रु' in ans or 'ರೂ' in ans


def test_custom_crop_requirement_is_used():
    from utils.fertilizer_engine import custom_requirement
    r = run_analysis(POOR, 'Dragon fruit', 2, req=custom_requirement(100, 50, 50))
    assert r['plan_rows'] and r['crop_result']['target'] is None


def test_ai_crop_estimate_is_range_checked(monkeypatch):
    import json
    monkeypatch.setattr(L, 'ai_available', lambda: True)
    monkeypatch.setattr(L, '_chat', lambda *a, **k: (json.dumps({'N': 90, 'P2O5': 50, 'K2O': 60, 'legume': False,
                                                                  'vegetable': True}), 'm'))
    assert L.estimate_crop_requirement('dragon fruit')['N'] == 90.0
    monkeypatch.setattr(L, '_chat', lambda *a, **k: (json.dumps({'N': 9000, 'P2O5': 50, 'K2O': 60}), 'm'))
    assert L.estimate_crop_requirement('x') is None
    monkeypatch.setattr(L, '_chat', lambda *a, **k: (json.dumps({'N': None, 'P2O5': None, 'K2O': None}), 'm'))
    assert L.estimate_crop_requirement('x') is None


def _run_form(at, **vals):
    for k, v in vals.items():
        at.session_state[k] = v
    at.run()
    [b for b in at.button if b.key == 'submit'][0].click()
    at.run()


def test_other_crop_flows_in_the_app(monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.delenv('GROQ_API_KEY', raising=False)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    base = dict(in_name='A', in_village='V', in_district='Bangalore', in_state='Karnataka', in_ph=6.5, in_N=150.0,
                in_P=30.0, in_K=150.0, in_OC=0.5, in_S=10.0, in_Zn=0.7, in_Fe=6.0, in_Cu=1.0, in_Mn=4.0, in_B=0.5,
                in_EC=0.3, in_crop='__other__')
    # typed name that is in the table
    at = AppTest.from_file(os.path.join(root, 'app.py'), default_timeout=180).run()
    at.session_state['in_state'] = 'Karnataka'
    at.run()
    _run_form(at, in_ctext='carrot', **base)
    assert not at.exception and at.session_state.res['inp']['crop'] == 'Carrot' and at.session_state.res['inp']['crop_source'] == 'table'
    # a crop that is not in the table, with doses typed by the farmer
    at = AppTest.from_file(os.path.join(root, 'app.py'), default_timeout=180).run()
    at.session_state['in_state'] = 'Karnataka'
    at.run()
    _run_form(at, in_ctext='Dragon fruit', in_cN=90.0, in_cP=50.0, in_cK=60.0, **base)
    assert not at.exception and at.session_state.res['inp']['crop_source'] == 'farmer'
    # unknown crop, no doses, no AI: a clear error, no crash
    at = AppTest.from_file(os.path.join(root, 'app.py'), default_timeout=180).run()
    at.session_state['in_state'] = 'Karnataka'
    at.run()
    _run_form(at, in_ctext='Dragon fruit', in_cN=0.0, in_cP=0.0, in_cK=0.0, **base)
    assert not at.exception and at.error and 'Dragon fruit' in at.error[0].value
