"""
Crop-aware fertiliser recommendation engine (deterministic rules, no LLM).

Method (Soil Health Card style, nutrient based):
  1. Start from the crop's recommended N : P2O5 : K2O (data/crop_requirements.csv).
  2. Adjust each macronutrient by its soil status:
        Very Low x1.25 | Low x1.10 | Optimal x1.00 | High x0.50 | Excessive skip
  3. Convert nutrient need to products: P via DAP (SSP in the Budget plan), the N in
     DAP is deducted, the remaining N comes from urea, K from MOP.
  4. Micronutrient, sulphur, pH and organic doses come from the ICAR table
     (data/fertilizer_data.csv), scaled by severity.
  5. Quantities, bags and costs are worked out for the farm area.
Rows carry language-neutral codes (method, timing, notes); utils/i18n.py turns them into text.
"""
import csv
import os

from utils import i18n

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACRE_PER_HA = 2.47105

MACRO_MULT = {'Very Low': 1.25, 'Low': 1.10, 'Optimal': 1.0, 'High': 0.5, 'Excessive': 0.0}
MICRO_PARAMS = {'Zinc': 'Zinc Sulphate', 'Boron': 'Borax', 'Iron': 'Ferrous Sulphate',
                'Manganese': 'Manganese Sulphate', 'Copper': 'Copper Sulphate'}
PLAN_KEYS = {'Budget': 'budget_plan', 'Balanced': 'balanced_plan', 'Maximum Yield': 'maximal_plan'}

# ICAR table text -> language-neutral codes
METHOD_CODE = {'Basal or foliar 0.5%': 'M_BASAL_FOLIAR_05', 'Basal or foliar 0.1-0.2%': 'M_BASAL_FOLIAR_01',
               'Soil or foliar spray 1%': 'M_SOIL_FOLIAR_1', 'Soil or foliar spray 0.5%': 'M_SOIL_FOLIAR_05',
               'Soil application': 'M_SOIL', 'Soil incorporation': 'M_SOIL', 'Deep incorporation': 'M_DEEP'}
TIMING_CODE = {'Pre-sowing or early growth': 'T_PRESOW_EARLY', 'Pre-sowing or flowering': 'T_PRESOW_FLOWER',
               'Basal or at chlorosis appearance': 'T_CHLOROSIS', 'Basal or early growth stage': 'T_SOWING_EARLY',
               'Pre-sowing': 'T_PRESOW', 'Pre-sowing; oxidises slowly': 'T_PRESOW_SLOW'}


def _read(name):
    with open(os.path.join(_BASE, 'data', name), newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def _load():
    prices = {r['Fertilizer']: r for r in _read('fertilizer_prices.csv')}
    reqs = {r['Crop']: r for r in _read('crop_requirements.csv')}
    icar = {r['FertilizerName']: r for r in _read('fertilizer_data.csv')}
    return prices, reqs, icar


PRICES, CROP_REQ, ICAR = _load()


def available_crops():
    return list(CROP_REQ.keys())


# Names people actually use for the listed crops (English, Hindi and Kannada names come from i18n).
ALIASES = {
    'paddy': 'Rice', 'dhan': 'Rice', 'corn': 'Maize', 'makka': 'Maize', 'gram': 'Chickpea', 'bengal gram': 'Chickpea',
    'chana': 'Chickpea', 'kadle': 'Chickpea', 'peanut': 'Groundnut', 'moongphali': 'Groundnut',
    'finger millet': 'Ragi', 'nachni': 'Ragi', 'sorghum': 'Jowar', 'pearl millet': 'Bajra', 'millet': 'Bajra',
    'til': 'Sesame', 'gingelly': 'Sesame', 'rapeseed': 'Mustard', 'sarson': 'Mustard', 'tur': 'Pigeon pea',
    'toor': 'Pigeon pea', 'arhar': 'Pigeon pea', 'red gram': 'Pigeon pea', 'moong': 'Green gram', 'mung': 'Green gram',
    'urad': 'Black gram', 'pyaz': 'Onion', 'mirchi': 'Chilli', 'chili': 'Chilli', 'chilly': 'Chilli',
    'eggplant': 'Brinjal', 'baingan': 'Brinjal', 'bhindi': 'Okra', 'lady finger': 'Okra', 'ladies finger': 'Okra',
    'gobi': 'Cauliflower', 'patta gobi': 'Cabbage', 'gajar': 'Carrot', 'haldi': 'Turmeric', 'aloo': 'Potato',
    'tamatar': 'Tomato', 'kapas': 'Cotton', 'ganna': 'Sugarcane', 'gehu': 'Wheat', 'soya': 'Soybean',
}


def _plain(name: str) -> str:
    import re
    return re.sub(r'\(.*?\)', '', name).strip().lower()


def _crop_names():
    """canonical crop -> all names (English, aliases, Hindi, Kannada) in lower case."""
    out = {c: {c.lower()} for c in CROP_REQ}
    for a, c in ALIASES.items():
        if c in out:
            out[c].add(a)
    for c in CROP_REQ:
        row = i18n._T.get(f'c_{c}')
        if row:
            out[c] |= {_plain(row[1]), _plain(row[2])}
            for part in row[1].replace('(', ' ').replace(')', ' ').split():
                if len(part) > 2:
                    out[c].add(part.lower())
    return out


def match_crop(text: str):
    """Return the listed crop a typed name refers to (any language), or None."""
    t = (text or '').strip().lower()
    if not t:
        return None
    for c, names in _crop_names().items():
        if t in names:
            return c
    return None


def find_crops_in_text(text: str) -> list:
    """Listed crops mentioned in a sentence, in order of appearance."""
    import re
    low = (text or '').lower()
    hits = []
    for c, names in _crop_names().items():
        pos = None
        for n in names:
            if not n:
                continue
            m = re.search(r'(?<![a-z])' + re.escape(n) + r'(?![a-z])', low) if n.isascii() else None
            if m is None and not n.isascii() and n in low:
                pos = low.index(n) if pos is None else min(pos, low.index(n))
            elif m:
                pos = m.start() if pos is None else min(pos, m.start())
        if pos is not None:
            hits.append((pos, c))
    return [c for _, c in sorted(hits)]


def custom_requirement(n, p, k, legume=False, vegetable=False, source='farmer'):
    """Build a crop requirement for a crop that is not in the table (kg nutrient per hectare)."""
    return {'N_kg_ha': str(float(n)), 'P2O5_kg_ha': str(float(p)), 'K2O_kg_ha': str(float(k)),
            'Duration_days': '120', 'Legume': '1' if legume else '0', 'Vegetable': '1' if vegetable else '0',
            'Source': source}


def _range(s):
    nums = [float(x) for x in s.replace('–', '-').replace('kg/ha', '').split('-') if x.strip()]
    return (nums[0], nums[-1]) if nums else (0.0, 0.0)


def _row(param, issue, status, fert, dose, area_ac, method, timing, source,
         notes=(), icar_range=None, kind='fertiliser'):
    """dose is kg of product per hectare."""
    ha = area_ac / ACRE_PER_HA
    p = PRICES.get(fert, {})
    price = float(p.get('PriceINRPerKg', 0) or 0)
    bag = float(p.get('BagKg', 50) or 50)
    total_kg = dose * ha
    bags = round(total_kg / bag, 1) if dose > 0 else 0
    return {
        'param': param, 'issue': issue, 'Status': status, 'Fertilizer': fert, 'kind': kind,
        'dose_value': round(dose, 1), 'per_acre_kg': round(dose / ACRE_PER_HA, 1),
        'total_kg': round(total_kg, 1), 'bags_value': bags, 'bag_kg': bag,
        'method_code': method, 'timing_code': timing, 'note_codes': list(notes),
        'cost_value': round(total_kg * price, 2), 'cost_per_acre': round(dose * price / ACRE_PER_HA),
        'Source': source, 'icar_range': icar_range,
        # English text for tables, tests and fallbacks
        'Nutrient Deficiency': issue_text(param, issue, 'English'),
        'Dose (kg/ha)': f'{dose:,.0f}', 'Total for farm (kg)': round(total_kg, 1),
        'Bags': (f'{bags} x {bag:.0f} kg' if dose > 0 else '-'),
        'Application Method': i18n.en(method), 'Timing': i18n.en(timing),
        'Est. Cost': f'Rs {total_kg * price:,.0f}',
        'Note': ' '.join(i18n.en(n) for n in notes),
    }


def issue_text(param, issue, lang):
    """Label for the 'what this fixes' column."""
    if issue in ('i_acid', 'i_alk', 'i_foliar'):
        return i18n.t(issue, lang)
    return i18n.t(f'n_{param}', lang)


def _advisory(param, status, macro):
    r = _row(param, param, status, 'No application', 0, 1, 'M_NONE', 'M_NONE', 'FAO / SHC thresholds',
             notes=['N_ADV_MACRO' if macro else 'N_ADV_MICRO'], kind='advisory')
    r['cost_value'] = 0.0
    r['Est. Cost'] = 'Rs 0'
    r['cost_per_acre'] = 0
    return r


def _crop_req(crop):
    return CROP_REQ.get(crop) or CROP_REQ['Wheat']


def _plan(analysis, crop, area_ac, plan, req=None):
    P = analysis['parameters']
    st = lambda k: P.get(k, {}).get('status', 'Optimal')
    req = req or _crop_req(crop)
    is_legume = req['Legume'] == '1'
    is_veg = req['Vegetable'] == '1'
    boost = 1.10 if plan == 'Maximum Yield' else 1.0
    rows = []
    need = {'N': float(req['N_kg_ha']) * MACRO_MULT[st('Nitrogen')] * boost,
            'P2O5': float(req['P2O5_kg_ha']) * MACRO_MULT[st('Phosphorus')] * boost,
            'K2O': float(req['K2O_kg_ha']) * MACRO_MULT[st('Potassium')] * boost}
    src = 'ICAR / SAU package of practices, adjusted by soil status'

    n_credit = 0.0
    if need['P2O5'] > 0:
        if plan == 'Budget':
            rows.append(_row('Phosphorus', 'Phosphorus', st('Phosphorus'), 'SSP', need['P2O5'] / 0.16, area_ac,
                             'M_BASAL_BAND', 'T_SOWING_PLOUGH', src, notes=['N_SSP']))
        else:
            dap = need['P2O5'] / 0.46
            n_credit = dap * 0.18
            rows.append(_row('Phosphorus', 'Phosphorus', st('Phosphorus'), 'DAP', dap, area_ac,
                             'M_BASAL', 'T_SOWING_PLOUGH', src, notes=['N_DAP']))
    elif st('Phosphorus') in ('High', 'Excessive'):
        rows.append(_advisory('Phosphorus', st('Phosphorus'), True))

    n_left = max(0.0, need['N'] - n_credit)
    if n_left > 0:
        rows.append(_row('Nitrogen', 'Nitrogen', st('Nitrogen'), 'Urea', n_left / 0.46, area_ac,
                         'M_TOPDRESS', 'T_ALL_SOWING' if is_legume else 'T_SPLIT', src, notes=['N_UREA']))
    elif st('Nitrogen') in ('High', 'Excessive'):
        rows.append(_advisory('Nitrogen', st('Nitrogen'), True))

    if need['K2O'] > 0:
        rows.append(_row('Potassium', 'Potassium', st('Potassium'), 'MOP', need['K2O'] / 0.60, area_ac,
                         'M_BASAL', 'T_SOWING', src))
    elif st('Potassium') in ('High', 'Excessive'):
        rows.append(_advisory('Potassium', st('Potassium'), True))

    if st('Sulphur') in ('Very Low', 'Low') and plan != 'Budget':
        rows.append(_row('Sulphur', 'Sulphur', st('Sulphur'), 'Gypsum', 400 if st('Sulphur') == 'Very Low' else 200,
                         area_ac, 'M_SOIL', 'T_PRESOW', 'ICAR-NBSS&LUP',
                         icar_range=_range(ICAR['Gypsum']['DoseKgHa'])))
    elif st('Sulphur') in ('High', 'Excessive'):
        rows.append(_advisory('Sulphur', st('Sulphur'), True))

    for param, fert in MICRO_PARAMS.items():
        s = st(param)
        if s in ('High', 'Excessive'):
            rows.append(_advisory(param, s, False))
            continue
        if s not in ('Very Low', 'Low') or (plan == 'Budget' and s != 'Very Low'):
            continue
        lo, hi = _range(ICAR[fert]['DoseKgHa'])
        crops = ICAR[fert]['CropType']
        notes = [] if (crop in crops or 'All' in crops) else ['N_GENERAL']
        if param == 'Boron':
            notes.append('N_BORON')
        rows.append(_row(param, param, s, fert, hi if s == 'Very Low' else lo, area_ac,
                         METHOD_CODE.get(ICAR[fert]['ApplicationMethod'], 'M_SOIL'),
                         TIMING_CODE.get(ICAR[fert]['Timing'], 'T_PRESOW'),
                         'ICAR-NBSS&LUP', notes=notes, icar_range=(lo, hi)))

    s_oc = st('OrganicCarbon')
    if s_oc in ('Very Low', 'Low'):
        if plan == 'Maximum Yield':
            rows.append(_row('OrganicCarbon', 'OrganicCarbon', s_oc, 'Vermicompost', 2000, area_ac, 'M_SOIL', 'T_2_3W',
                             'ICAR / Organic Farming Guidelines', icar_range=_range(ICAR['Vermicompost']['DoseKgHa'])))
        else:
            rows.append(_row('OrganicCarbon', 'OrganicCarbon', s_oc, 'FYM', 5000, area_ac, 'M_SOIL', 'T_3_4W',
                             'ICAR / Organic Farming Guidelines', icar_range=_range(ICAR['FYM']['DoseKgHa'])))

    s_ph = st('pH')
    if s_ph in ('Very Low', 'Low'):
        rows.append(_row('pH', 'i_acid', s_ph, 'Lime', 2000 if s_ph == 'Very Low' else 1000, area_ac, 'M_DEEP',
                         'T_2_4W', 'FAO / ICAR', notes=['N_RETEST'], icar_range=_range(ICAR['Lime']['DoseKgHa'])))
    elif s_ph in ('High', 'Excessive'):
        if plan == 'Budget':
            rows.append(_row('pH', 'i_alk', s_ph, 'Gypsum', 500, area_ac, 'M_SOIL_LEACH', 'T_PRESOW', 'FAO / ICAR',
                             notes=['N_SODIC']))
        else:
            rows.append(_row('pH', 'i_alk', s_ph, 'Elemental Sulphur', 400 if s_ph == 'Excessive' else 200, area_ac,
                             'M_SOIL', 'T_PRESOW_SLOW', 'FAO / ICAR',
                             icar_range=_range(ICAR['Elemental Sulphur']['DoseKgHa'])))

    if plan == 'Maximum Yield' and is_veg:
        rows.append(_row('Foliar', 'i_foliar', 'Boost', 'NPK 19-19-19', 8, area_ac, 'M_FOLIAR_3X', 'T_FLOWER',
                         'ICAR-NBSS&LUP', notes=['N_FOLIAR']))
    return rows


def get_recommendations(analysis: dict, crop: str = 'Wheat', farm_area_acres: float = 1.0, req: dict = None) -> dict:
    plans = {k: _plan(analysis, crop, farm_area_acres, k, req) for k in PLAN_KEYS}
    out = {'budget_plan': plans['Budget'], 'balanced_plan': plans['Balanced'], 'maximal_plan': plans['Maximum Yield'],
           'all_recommendations': plans['Balanced'], 'crop': crop, 'farm_area_acres': farm_area_acres,
           'source': 'ICAR-NBSS&LUP dose tables + crop package of practices',
           'validated_against': ['ICAR-NBSS&LUP', 'FAO Soils Portal', 'Soil Health Card (DAC&FW)']}
    for k, name in (('budget', 'Budget'), ('balanced', 'Balanced'), ('maximal', 'Maximum Yield')):
        total = sum(r['cost_value'] for r in plans[name])
        out[f'{k}_cost_value'] = round(total)
        out[f'{k}_cost'] = f'Rs {total:,.0f}'
        out[f'{k}_cost_per_acre'] = round(total / farm_area_acres) if farm_area_acres else 0
    return out


def build_schedule(plan_rows: list, area_ac: float, crop: str) -> list:
    """Turn a plan into a when-to-apply schedule (language-neutral codes)."""
    ha = area_ac / ACRE_PER_HA
    order = ['S_BEFORE', 'S_SOWING', 'S_30', 'S_60', 'S_LATER']
    buckets = {k: [] for k in order}
    for r in plan_rows:
        if r['kind'] == 'advisory' or r['dose_value'] <= 0:
            continue
        t, d, f = r['timing_code'], r['dose_value'], r['Fertilizer']
        if t == 'T_SPLIT':
            buckets['S_30'].append((f, d / 2, 'M_TOPDRESS_MOIST'))
            buckets['S_60'].append((f, d / 2, 'M_TOPDRESS_MOIST'))
        elif t in ('T_2_4W', 'T_2_3W', 'T_3_4W'):
            buckets['S_BEFORE'].append((f, d, r['method_code']))
        elif t in ('T_FLOWER', 'T_PRESOW_FLOWER'):
            buckets['S_LATER'].append((f, d, r['method_code']))
        else:
            buckets['S_SOWING'].append((f, d, r['method_code']))
    return [{'stage_code': s, 'When': i18n.en(s), 'Fertiliser': f, 'per_acre_kg': round(d / ACRE_PER_HA, 1),
             'Per hectare (kg)': round(d), 'For your farm (kg)': round(d * ha, 1),
             'how_code': m, 'How': i18n.en(m)}
            for s in order for f, d, m in buckets[s]]
