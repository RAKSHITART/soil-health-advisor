"""
Agronomic validation layer: every recommendation is cross-checked against
three independent references, computed (not hard-coded):

  1. FAO soil-nutrient classes     (data/fao_standards.csv, used for classification)
  2. Soil Health Card (DAC&FW)     (rating cut-offs below)
  3. ICAR-NBSS&LUP dose tables     (data/fertilizer_data.csv) + crop package of practices

Soil Health Card cut-offs are the commonly published national ratings
(Low / Medium / High); verify against the latest DAC&FW publication.
"""
from utils.fertilizer_engine import CROP_REQ

# param -> (low_below, high_above)   (SHC: Low < a, Medium a-b, High > b)
SHC = {
    'pH':            (6.5, 7.8,  'Acidic', 'Neutral', 'Alkaline'),
    'OrganicCarbon': (0.5, 0.75, 'Low', 'Medium', 'High'),
    'Nitrogen':      (280, 560,  'Low', 'Medium', 'High'),
    'Phosphorus':    (10, 25,    'Low', 'Medium', 'High'),
    'Potassium':     (108, 280,  'Low', 'Medium', 'High'),
}
SHC_DEFICIENT_BELOW = {'Sulphur': 10, 'Zinc': 0.6, 'Iron': 4.5, 'Copper': 0.2,
                       'Manganese': 1.0, 'Boron': 0.5}

REFERENCES = [
    ('ICAR-NBSS&LUP', 'Fertiliser dose tables & nutrient management publications (nbsslup.icar.gov.in)',
     'Micronutrient / sulphur / pH / organic doses; range-check of every dose'),
    ('FAO', 'FAO Soils Portal & World Soil Database (fao.org/soils-portal)',
     'Optimal / deficient ranges for all 11 parameters (classification)'),
    ('Govt. of India', 'Soil Health Card programme: national rating cut-offs (soilhealth.dac.gov.in)',
     'Independent Low/Medium/High rating used for cross-check'),
    ('Crop package of practices', 'ICAR / State Agricultural University recommended N:P2O5:K2O (approx.)',
     'Crop-specific macronutrient dose baseline: confirm with your local KVK'),
    ('Crop model data', 'Schema-compatible synthetic dataset modelled on the UCI/Kaggle crop recommendation data',
     'Training data for the crop-suitability Random Forest (replaceable)'),
]


def shc_class(param: str, value: float) -> str:
    if param == 'EC':   # Soil Health Card: <1 normal, 1 to 3 critical for sensitive crops, >3 injurious
        return 'Normal' if value <= 1 else ('Critical' if value <= 3 else 'Injurious')
    if param in SHC:
        lo, hi, a, b, c = SHC[param]
        return a if value < lo else (c if value > hi else b)
    if param in SHC_DEFICIENT_BELOW:
        return 'Deficient' if value < SHC_DEFICIENT_BELOW[param] else 'Sufficient'
    return 'n/a'


def _fao_bucket(status: str) -> str:
    return {'Very Low': 'low', 'Low': 'low', 'Optimal': 'ok', 'High': 'high', 'Excessive': 'high'}.get(status, 'ok')


def _shc_bucket(label: str) -> str:
    return {'Low': 'low', 'Acidic': 'low', 'Deficient': 'low', 'Medium': 'ok', 'Neutral': 'ok',
            'Sufficient': 'ok', 'High': 'high', 'Alkaline': 'high', 'Normal': 'ok', 'Critical': 'high', 'Injurious': 'high'}.get(label, 'ok')


def cross_check(analysis: dict) -> list:
    """FAO class vs Soil Health Card rating for each parameter."""
    rows = []
    for p, info in analysis['parameters'].items():
        shc = shc_class(p, info['value'])
        agree = _fao_bucket(info['status']) == _shc_bucket(shc)
        rows.append({
            'Parameter': info['display_name'], 'Value': info['value'], 'Unit': info['unit'],
            'FAO class': info['status'], 'Soil Health Card': shc,
            'Agreement': 'Agree' if agree else 'Differ',
        })
    return rows


def validate_plan(analysis: dict, plan_rows: list, crop: str, req: dict = None) -> list:
    """Audit each recommendation against FAO, SHC and ICAR."""
    req = req or CROP_REQ.get(crop, CROP_REQ['Wheat'])
    pkg = {'Nitrogen': float(req['N_kg_ha']), 'Phosphorus': float(req['P2O5_kg_ha']),
           'Potassium': float(req['K2O_kg_ha'])}
    nutrient_pct = {'Urea': 0.46, 'DAP': 0.46, 'SSP': 0.16, 'MOP': 0.60}
    out = []
    for r in plan_rows:
        param = r['param']
        info = analysis['parameters'].get(param)
        if r['kind'] == 'advisory' or not info:
            continue
        fao = f"{info['status']} (optimal {info['fao_optimal']})"
        shc = shc_class(param, info['value'])
        # ICAR / package dose check
        icar_ok, icar_txt = True, 'n/a'
        if r.get('icar_range'):
            lo, hi = r['icar_range']
            icar_ok = lo * 0.999 <= r['dose_value'] <= hi * 1.001
            icar_txt = f'ICAR range {lo:g}-{hi:g} kg/ha'
        elif param in pkg and r['Fertilizer'] in nutrient_pct:
            nutrient = r['dose_value'] * nutrient_pct[r['Fertilizer']]
            ratio = nutrient / pkg[param] if pkg[param] else 0
            icar_ok = 0.3 <= ratio <= 1.6
            icar_txt = f'{nutrient:.0f} kg nutrient = {ratio:.2f}x crop package ({pkg[param]:.0f})'
        out.append({
            'Recommendation': f"{r['Fertilizer']}: {r['Dose (kg/ha)']} kg/ha",
            'FAO check': fao,
            'Soil Health Card': shc,
            'ICAR / package check': ('OK: ' if icar_ok else 'Check: ') + icar_txt,
        })
    return out


def summary(analysis: dict, plan_rows: list, crop: str, req: dict = None) -> dict:
    cc = cross_check(analysis)
    pv = validate_plan(analysis, plan_rows, crop, req)
    n_agree = sum(1 for r in cc if r['Agreement'] == 'Agree')
    n_icar_ok = sum(1 for r in pv if r['ICAR / package check'].startswith('OK'))
    return {'cross_check': cc, 'plan_checks': pv, 'agree': n_agree, 'total': len(cc),
            'icar_ok': n_icar_ok, 'icar_total': len(pv), 'references': REFERENCES}
