"""
Yield improvement predictor.
Estimates current yield potential and post-recommendation yield.
"""

CROP_OPTIMAL = {
    'Rice':      {'pH':(5.5,6.5),'Nitrogen':(120,200),'Phosphorus':(30,60),'Potassium':(150,250),'OrganicCarbon':(0.5,1.2)},
    'Wheat':     {'pH':(6.0,7.5),'Nitrogen':(100,180),'Phosphorus':(25,55),'Potassium':(130,230),'OrganicCarbon':(0.6,1.4)},
    'Maize':     {'pH':(5.8,7.0),'Nitrogen':(130,220),'Phosphorus':(35,65),'Potassium':(140,260),'OrganicCarbon':(0.5,1.3)},
    'Cotton':    {'pH':(6.0,8.0),'Nitrogen':(90,170), 'Phosphorus':(20,50),'Potassium':(120,220),'OrganicCarbon':(0.4,1.1)},
    'Sugarcane': {'pH':(6.0,7.5),'Nitrogen':(150,250),'Phosphorus':(40,70),'Potassium':(160,280),'OrganicCarbon':(0.6,1.5)},
    'Groundnut': {'pH':(5.5,7.0),'Nitrogen':(80,150), 'Phosphorus':(30,60),'Potassium':(100,200),'OrganicCarbon':(0.5,1.2)},
    'Tomato':    {'pH':(5.5,7.0),'Nitrogen':(100,200),'Phosphorus':(35,65),'Potassium':(130,250),'OrganicCarbon':(0.6,1.5)},
    'Potato':    {'pH':(5.0,6.5),'Nitrogen':(110,190),'Phosphorus':(40,70),'Potassium':(140,260),'OrganicCarbon':(0.5,1.3)},
    'Soybean':   {'pH':(6.0,7.2),'Nitrogen':(90,160), 'Phosphorus':(30,55),'Potassium':(120,210),'OrganicCarbon':(0.5,1.2)},
    'Chickpea':  {'pH':(6.0,8.0),'Nitrogen':(80,150), 'Phosphorus':(25,50),'Potassium':(110,200),'OrganicCarbon':(0.4,1.1)},
}

def _index(score: int) -> int:
    """Indicative yield-potential index from soil health score (0-100 -> 40-95%)."""
    return int(round(40 + 0.55 * max(0, min(100, score))))


def predict_yield(soil_data: dict, crop: str, n_deficiencies: int, n_excesses: int,
                  score_now: int = None, score_after: int = None) -> dict:
    """Indicative (heuristic) yield-potential index before/after following the plan.
    Not a field-yield forecast: it tracks the soil health score."""
    optimal = CROP_OPTIMAL.get(crop, CROP_OPTIMAL['Wheat'])
    key_params = ['pH', 'Nitrogen', 'Phosphorus', 'Potassium', 'OrganicCarbon']
    limiting = [p for p in key_params if p in soil_data and p in optimal
                and not (optimal[p][0] <= soil_data[p] <= optimal[p][1])]
    if score_now is None:
        score_now = max(10, 100 - n_deficiencies * 9 - n_excesses * 5)
    if score_after is None:
        score_after = min(100, score_now + n_deficiencies * 8)
    current, improved = _index(score_now), _index(score_after)
    return {
        'current_yield_pct': current,
        'improved_yield_pct': max(improved, current),
        'yield_gain_pct': max(improved, current) - current,
        'key_limiting': limiting,
        'note': 'Indicative index derived from soil health score: not a field-yield forecast.',
    }
