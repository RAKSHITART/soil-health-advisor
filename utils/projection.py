"""
What-if projection: if the farmer follows a plan, what would the soil look like
and how much does the health score improve? Only parameters actually treated by
the plan are improved (so the Budget plan projects a smaller gain).
"""
from utils.soil_analyzer import analyse_soil, FAO_STANDARDS


def project_after_plan(soil_data: dict, analysis: dict, plan_rows: list) -> dict:
    treated = {r['param'] for r in plan_rows if r.get('kind') != 'advisory' and r['dose_value'] > 0}
    projected = dict(soil_data)
    for p in treated:
        if p not in FAO_STANDARDS or p not in soil_data:
            continue
        s = FAO_STANDARDS[p]
        status = analysis['parameters'][p]['status']
        if status in ('Very Low', 'Low'):
            projected[p] = round(min(s['opt_min'] * 1.15, s['opt_max']), 2)
        elif status in ('High', 'Excessive') and p == 'pH':
            projected[p] = round(min(max(s['opt_max'] - 0.2, s['opt_min']), s['opt_max']), 2)
    after = analyse_soil(projected)
    return {'projected_data': projected, 'analysis': after,
            'score_before': analysis['health_score'], 'score_after': after['health_score'],
            'gain': after['health_score'] - analysis['health_score'], 'treated': sorted(treated)}
