"""
Rule-based soil analysis engine.
Validates against FAO Soil Standards (fao_standards.csv).
References: FAO Soils Portal, ICAR-NBSS&LUP, Soil Health Card Programme.
"""
import os
import csv

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _load_fao_standards() -> dict:
    path = os.path.join(_BASE, "data", "fao_standards.csv")
    standards = {}
    try:
        with open(path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                standards[row['Parameter']] = {
                    'very_low': float(row['VeryLow_max']),
                    'low':      float(row['Low_max']),
                    'opt_min':  float(row['Optimal_min']),
                    'opt_max':  float(row['Optimal_max']),
                    'high':     float(row['High_min']),
                    'excess':   float(row['Excessive_min']),
                    'unit':     row['Unit'],
                    'ref':      row['FAO_Reference'],
                }
    except Exception:
        pass
    return standards

FAO_STANDARDS = _load_fao_standards()

UNITS = {
    'pH': '', 'Nitrogen': 'kg/ha', 'Phosphorus': 'kg/ha', 'Potassium': 'kg/ha',
    'OrganicCarbon': '%', 'Sulphur': 'ppm', 'Zinc': 'ppm', 'Iron': 'ppm',
    'Copper': 'ppm', 'Manganese': 'ppm', 'Boron': 'ppm', 'EC': 'dS/m',
}

DISPLAY_NAMES = {
    'pH': 'pH', 'Nitrogen': 'Nitrogen (N)', 'Phosphorus': 'Phosphorus (P)',
    'Potassium': 'Potassium (K)', 'OrganicCarbon': 'Organic Carbon',
    'Sulphur': 'Sulphur (S)', 'Zinc': 'Zinc (Zn)', 'Iron': 'Iron (Fe)',
    'Copper': 'Copper (Cu)', 'Manganese': 'Manganese (Mn)', 'Boron': 'Boron (B)', 'EC': 'Electrical conductivity (EC)',
}

SMART_OBSERVATIONS = {
    'pH': {
        'Very Low':  'Soil is strongly acidic: aluminium and manganese toxicity likely; most nutrients unavailable.',
        'Low':       'Soil is moderately acidic: phosphorus fixation reduces availability; lime application recommended.',
        'Optimal':   'pH is in the ideal range (6.0-7.5): optimal nutrient availability for most crops.',
        'High':      'Soil is moderately alkaline: micronutrient deficiencies (Zn, Fe, Mn) likely.',
        'Excessive': 'Soil is highly alkaline: severe micronutrient lockout; gypsum or sulphur required urgently.',
    },
    'Nitrogen': {
        'Very Low':  'Critical N deficiency: expect severe yellowing (chlorosis), stunted growth, and 40-60% yield loss.',
        'Low':       'Nitrogen is below optimal: crop will show pale leaves; early N application essential.',
        'Optimal':   'Nitrogen level is adequate for healthy vegetative growth and grain development.',
        'High':      'Excess nitrogen: promotes excessive vegetative growth; lodging and pest risk increase.',
        'Excessive': 'Very high N: risk of nitrate pollution, salt damage, and reduced grain quality.',
    },
    'Phosphorus': {
        'Very Low':  'Critical P deficiency: root development severely impaired; purple discolouration on leaves likely.',
        'Low':       'Phosphorus below optimal: reduced root development and crop productivity expected.',
        'Optimal':   'Phosphorus is adequate: good root growth and energy transfer expected.',
        'High':      'High phosphorus: may induce zinc and iron deficiency; reduce P application.',
        'Excessive': 'Excessive P: environmental runoff risk; micronutrient antagonism likely.',
    },
    'Potassium': {
        'Very Low':  'Critical K deficiency: expect poor grain filling, weak stems, and disease susceptibility.',
        'Low':       'Potassium is low: reduced drought tolerance and crop quality; MOP application needed.',
        'Optimal':   'Potassium is adequate: good water regulation and disease resistance expected.',
        'High':      'High potassium: may reduce magnesium and calcium uptake.',
        'Excessive': 'Excessive K: salt stress possible; nutrient imbalance with Mg and Ca.',
    },
    'OrganicCarbon': {
        'Very Low':  'Critically low organic carbon: poor soil structure, water retention, and microbial activity.',
        'Low':       'Organic carbon is low: soil health and nutrient cycling impaired; add organic matter.',
        'Optimal':   'Organic carbon is adequate: good soil biology and structure expected.',
        'High':      'Good organic carbon level: excellent soil health and fertility.',
        'Excessive': 'Very high organic carbon: excellent condition; maintain with minimal tillage.',
    },
    'Sulphur': {
        'Very Low':  'Critical sulphur deficiency: protein synthesis disrupted; young leaves turn yellow.',
        'Low':       'Sulphur is below optimal: crop quality and protein content will be reduced.',
        'Optimal':   'Sulphur level is adequate: good protein and oil synthesis expected.',
        'High':      'Sulphur is on the higher side: monitor; usually not harmful at this level.',
        'Excessive': 'Excessive sulphur: soil acidification and toxicity risk in sensitive crops.',
    },
    'Zinc': {
        'Very Low':  'Critical Zn deficiency: khaira disease (rice), white bud (maize): severe yield loss.',
        'Low':       'Zinc is deficient: shortened internodes, small leaves; zinc sulphate needed.',
        'Optimal':   'Zinc level is adequate: normal enzyme activity and grain development.',
        'High':      'Zinc is high: may reduce iron and manganese uptake.',
        'Excessive': 'Excessive zinc: phytotoxic; reduces germination and root growth.',
    },
    'Iron': {
        'Very Low':  'Critical Fe deficiency: severe interveinal chlorosis, especially in alkaline soils.',
        'Low':       'Iron is below optimal: interveinal chlorosis likely in young leaves.',
        'Optimal':   'Iron level is adequate: good chlorophyll synthesis expected.',
        'High':      'Iron is elevated: bronze disease in rice possible.',
        'Excessive': 'Excessive iron: toxicity in flooded conditions; reduce waterlogging.',
    },
    'Copper': {
        'Very Low':  'Critical Cu deficiency: wilting of new leaves, poor grain set in wheat and rice.',
        'Low':       'Copper is deficient: reduced lignin synthesis; plant structure weakened.',
        'Optimal':   'Copper level is adequate: normal enzyme function expected.',
        'High':      'Copper is high: may inhibit root growth.',
        'Excessive': 'Excessive copper: phytotoxic; inhibits seed germination and root elongation.',
    },
    'Manganese': {
        'Very Low':  'Critical Mn deficiency: grey speck in oats, marsh spot in peas; reduced photosynthesis.',
        'Low':       'Manganese is deficient: interveinal chlorosis in younger leaves.',
        'Optimal':   'Manganese level is adequate: good photosynthesis and nitrogen metabolism.',
        'High':      'Manganese is elevated: potential for toxicity in acidic conditions.',
        'Excessive': 'Excessive manganese: toxicity symptoms: brown spots on leaves, reduced growth.',
    },
    'EC': {
        'Very Low':  'Salt level is very low.',
        'Low':       'Salt level is low.',
        'Optimal':   'Salt level is safe for most crops.',
        'High':      'Salt level is a little high: sensitive crops (beans, carrot, onion) can suffer during germination.',
        'Excessive': 'Soil is saline: most crops will be damaged. Flush salts with good-quality water, improve drainage and choose salt-tolerant crops.',
    },
    'Boron': {
        'Very Low':  'Critical B deficiency: death of growing points, hollow stem, poor pod set.',
        'Low':       'Boron is deficient: poor pollination and fruit/seed development.',
        'Optimal':   'Boron level is adequate: good reproductive growth expected.',
        'High':      'Boron is high: marginal leaf scorch in sensitive crops.',
        'Excessive': 'Excessive boron: severe toxicity; leaf burn, reduced yield.',
    },
}

def classify_parameter(param: str, value: float) -> dict:
    s = FAO_STANDARDS.get(param)
    if not s:
        return {'status': 'Unknown', 'color': '#888', 'score': 5}
    if value <= s['very_low']:
        return {'status': 'Very Low',  'color': '#c62828', 'score': 1}
    if value < s['opt_min']:
        return {'status': 'Low',       'color': '#e65100', 'score': 3}
    if value <= s['opt_max']:
        return {'status': 'Optimal',   'color': '#2e7d32', 'score': 10}
    if value < s['excess']:
        return {'status': 'High',      'color': '#1565c0', 'score': 6}
    return     {'status': 'Excessive', 'color': '#880e4f', 'score': 2}

def analyse_soil(data: dict) -> dict:
    results = {}
    total_score = 0
    max_score = 0
    deficiencies = []
    excesses = []

    for param, value in data.items():
        if param not in FAO_STANDARDS:
            continue
        cl = classify_parameter(param, value)
        obs = SMART_OBSERVATIONS.get(param, {}).get(cl['status'], '')
        fao_ref = FAO_STANDARDS[param]['ref']
        results[param] = {
            'value':        value,
            'unit':         UNITS.get(param, ''),
            'display_name': DISPLAY_NAMES.get(param, param),
            'status':       cl['status'],
            'color':        cl['color'],
            'score':        cl['score'],
            'observation':  obs,
            'fao_ref':      fao_ref,
            'fao_optimal':  f"{FAO_STANDARDS[param]['opt_min']} - {FAO_STANDARDS[param]['opt_max']}",
        }
        total_score += cl['score']
        max_score   += 10
        if cl['status'] in ('Very Low', 'Low'):
            deficiencies.append(param)
        elif cl['status'] in ('High', 'Excessive'):
            excesses.append(param)

    health_score = int((total_score / max_score) * 100) if max_score else 50
    if health_score >= 85:   category = 'Excellent'
    elif health_score >= 70: category = 'Good'
    elif health_score >= 50: category = 'Fair'
    elif health_score >= 30: category = 'Poor'
    else:                    category = 'Critical'

    return {
        'parameters':   results,
        'health_score': health_score,
        'category':     category,
        'deficiencies': deficiencies,
        'excesses':     excesses,
    }

def get_regional_comparison(state: str, district: str, soil_data: dict) -> dict:
    """Compare soil values with ICAR reference averages.
    Exact district match first; otherwise the mean of that state's districts
    (clearly labelled); otherwise not found."""
    path = os.path.join(_BASE, "data", "icar_district_data.csv")
    try:
        with open(path, newline='', encoding='utf-8') as f:
            rows = list(csv.DictReader(f))
    except Exception:
        return {'found': False, 'deviations': {}}

    cols = ['pH_avg', 'N_avg', 'P_avg', 'K_avg', 'OC_avg', 'S_avg', 'Zn_avg',
            'Fe_avg', 'Cu_avg', 'Mn_avg', 'B_avg']
    exact = [r for r in rows if r['District'].strip().lower() == district.strip().lower()
             and r['State'].strip().lower() == state.strip().lower()]
    in_state = [r for r in rows if r['State'].strip().lower() == state.strip().lower()]
    if exact:
        regional, level, label = exact[0], 'district', exact[0]['District']
    elif in_state:
        regional = {c: sum(float(r[c]) for r in in_state) / len(in_state) for c in cols}
        level, label = 'state', f'{state} (state average)'
    else:
        return {'found': False, 'deviations': {}}

    param_map = {
        'pH': 'pH_avg', 'Nitrogen': 'N_avg', 'Phosphorus': 'P_avg',
        'Potassium': 'K_avg', 'OrganicCarbon': 'OC_avg', 'Sulphur': 'S_avg',
        'Zinc': 'Zn_avg', 'Iron': 'Fe_avg', 'Copper': 'Cu_avg',
        'Manganese': 'Mn_avg', 'Boron': 'B_avg',
    }
    deviations = {}
    for param, col in param_map.items():
        if param in soil_data:
            try:
                rv, uv = float(regional[col]), float(soil_data[param])
                pct = ((uv - rv) / rv) * 100 if rv else 0.0
                deviations[param] = {'user': uv, 'regional_avg': round(rv, 2),
                                     'pct_diff': round(pct, 1),
                                     'direction': 'above' if pct > 0 else 'below'}
            except Exception:
                pass
    return {'found': True, 'level': level, 'state': state, 'district': label,
            'deviations': deviations}
