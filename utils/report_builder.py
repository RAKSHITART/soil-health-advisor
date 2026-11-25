"""
Builds one structured, localised report from the rule-engine results.
The same structure feeds the screen, the PDF and the text download, so they never disagree.
Facts (statuses, doses, costs) come only from the rule engine. The AI writes only the
explanatory narrative, and that narrative is checked before it is used (see llm_report).
"""
from utils import i18n
from utils.i18n import t

PARAM_ORDER = ['pH', 'Nitrogen', 'Phosphorus', 'Potassium', 'OrganicCarbon', 'Sulphur',
               'Zinc', 'Iron', 'Copper', 'Manganese', 'Boron', 'EC']


def status_text(status, lang):
    return t(f'st_{status}', lang)


def meaning_text(param, status, lang):
    if param == 'EC':
        return t('mean_EC_ok' if status in ('Optimal', 'Low', 'Very Low') else
                 ('mean_EC_high' if status == 'High' else 'mean_EC_Excessive'), lang)
    if param == 'pH' and status in ('Very Low', 'Low'):
        return t('mean_pH_low', lang)
    if param == 'pH' and status in ('High', 'Excessive'):
        return t('mean_pH_high', lang)
    return t(f'mean_{status}', lang)


def crop_name(crop, lang):
    code = f'c_{crop}'
    return t(code, lang) if i18n.has(code) else crop      # a crop typed by the farmer keeps its own name


def fert_name(fert, lang):
    return t(f'f_{fert}', lang)


def qty_bags(row):
    if row['dose_value'] <= 0:
        return '-'
    if row['bag_kg'] >= 1000:
        return f"{row['total_kg'] / 1000:.1f} t"
    return f"{row['bags_value']} x {row['bag_kg']:.0f} kg"


def localise_plan(rows, lang):
    out = []
    for r in rows:
        if r['kind'] == 'advisory':
            continue
        out.append({
            'issue': i18n.t(r['issue'], lang) if r['issue'].startswith('i_') else t(f"n_{r['param']}", lang),
            'fert': fert_name(r['Fertilizer'], lang),
            'acre': f"{r['per_acre_kg']:,.0f}", 'farm': f"{r['total_kg']:,.0f}", 'bags': qty_bags(r),
            'when': t(r['timing_code'], lang), 'how': t(r['method_code'], lang),
            'cost': f"{r['cost_value']:,.0f}", 'cost_value': r['cost_value'],
            'notes': ' '.join(t(n, lang) for n in r['note_codes']),
        })
    return out


def skip_list(rows, lang):
    return [t(f"n_{r['param']}", lang) for r in rows if r['kind'] == 'advisory']


def template_narrative(inp, res, lang):
    A = res['analysis']
    P = A['parameters']
    low = [t(f'n_{p}', lang) for p in A['deficiencies']]
    high = [t(f'n_{p}', lang) for p in A['excesses']]
    parts = [t('sum_tpl', lang, cat=t(f"cat_{A['category']}", lang), score=A['health_score'],
               crop=crop_name(inp['crop'], lang), area=inp['area'], n_low=len(low), n_high=len(high))]
    if low:
        parts.append(t('low_list', lang, x=', '.join(low)))
    if high:
        parts.append(t('high_list', lang, x=', '.join(high)))
    return {'summary': ' '.join(parts), 'risk': t('risk_tpl', lang) if low else '',
            'tips': [t(f'tip_{i}', lang) for i in range(1, 6)], 'mode': 'rules'}


def build_report(inp, res, lang, narrative=None):
    """Return a dict with every part of the report, already in the chosen language."""
    A = res['analysis']
    narr = narrative or template_narrative(inp, res, lang)
    soil_rows = []
    for p in PARAM_ORDER:
        if p in A['parameters']:
            info = A['parameters'][p]
            soil_rows.append({'name': t(f'n_{p}', lang), 'value': f"{info['value']:g} {info['unit']}".strip(),
                              'status': status_text(info['status'], lang), 'status_en': info['status'],
                              'meaning': meaning_text(p, info['status'], lang)})
    warnings = []
    ec = A['parameters'].get('EC')
    if ec and ec['status'] in ('High', 'Excessive'):
        warnings.append(t('salt_warn', lang))
    if inp.get('crop_source') in ('farmer', 'ai'):
        warnings.append(t('crop_custom_warn', lang, crop=crop_name(inp['crop'], lang), src=t(f"src_{inp['crop_source']}", lang)))
    plan = localise_plan(res['plan_rows'], lang)
    total = sum(r['cost_value'] for r in plan)
    first = []
    for r in plan[:3]:
        first.append(f"{r['fert']}: {r['acre']} kg / acre")
    return {
        'lang': lang,
        'title': t('res_title', lang),
        'meta': {'farmer': inp['farmer'], 'village': inp['village'], 'district': inp['district'],
                 'state': inp['state'], 'area': inp['area'], 'crop': crop_name(inp['crop'], lang),
                 'plan': t(f"plan_{inp['plan']}", lang)},
        'score': A['health_score'], 'category': t(f"cat_{A['category']}", lang),
        'summary': narr['summary'], 'risk': narr.get('risk', ''), 'tips': narr['tips'], 'warnings': warnings,
        'narrative_mode': narr.get('mode', 'rules'),
        'soil_rows': soil_rows, 'plan_rows': plan, 'skip': skip_list(res['plan_rows'], lang),
        'total_cost': total, 'cost_per_acre': round(total / inp['area']) if inp['area'] else 0,
        'first_steps': first, 'disclaimer': t('disclaimer', lang),
    }


def to_text(rep):
    L = lang = rep['lang']
    m = rep['meta']
    out = [rep['title'], '=' * 40,
           f"{t('f_name', lang)}: {m['farmer']}", f"{t('f_village', lang)}: {m['village']}",
           f"{t('f_district', lang)}: {m['district']}, {m['state']}", f"{t('f_area', lang)}: {m['area']}",
           f"{t('f_crop', lang)}: {m['crop']}", f"{t('soil_health', lang)}: {rep['category']} "
           f"({t('score_text', lang, score=rep['score'])})", '',
           t('rep_summary', lang).upper(), rep['summary']]
    if rep.get('warnings'):
        out += ['', t('rep_warn', lang).upper()] + [f'- {w}' for w in rep['warnings']]
    out += ['', t('rep_soil', lang).upper()]
    for r in rep['soil_rows']:
        out.append(f"- {r['name']}: {r['value']} | {r['status']} | {r['meaning']}")
    out += ['', t('rep_plan', lang).upper()]
    for i, r in enumerate(rep['plan_rows'], 1):
        out.append(f"{i}. " + t('dose_line', lang, fert=r['fert'], acre=r['acre'], farm=r['farm'], bags=r['bags'],
                                when=r['when'], how=r['how'], cost=r['cost']))
        if r['notes']:
            out.append(f"   {r['notes']}")
    out.append(f"{t('h_total', lang)}: Rs {rep['total_cost']:,.0f} "
               f"({t('per_acre_cost', lang, x=f'{rep['cost_per_acre']:,}')})")
    if rep['skip']:
        out += ['', t('rep_skip', lang).upper()]
        out += [f"- {t('skip_line', lang, p=p)}" for p in rep['skip']]
    if rep['risk']:
        out += ['', t('rep_risk', lang).upper(), rep['risk']]
    out += ['', t('rep_tips', lang).upper()] + [f'- {x}' for x in rep['tips']]
    out += ['', rep['disclaimer']]
    return '\n'.join(out)
