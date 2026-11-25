"""Single entry-point that runs the full analysis (used by the app, batch mode and tests)."""
from utils.crop_recommender import recommend_crops
from utils.fertilizer_engine import PLAN_KEYS, build_schedule, get_recommendations
from utils.projection import project_after_plan
from utils.soil_analyzer import analyse_soil, get_regional_comparison
from utils.validation import summary as validation_summary
from utils.yield_predictor import predict_yield

PARAMS = ['pH', 'Nitrogen', 'Phosphorus', 'Potassium', 'OrganicCarbon', 'Sulphur',
          'Zinc', 'Iron', 'Copper', 'Manganese', 'Boron', 'EC']


def run_analysis(soil_data: dict, crop: str, farm_area: float, plan_name: str = 'Balanced',
                 state: str = '', district: str = '', req: dict = None) -> dict:
    analysis = analyse_soil(soil_data)
    crop_result = recommend_crops(soil_data, target_crop=crop)
    fert = get_recommendations(analysis, crop, farm_area, req)
    plan_rows = fert[PLAN_KEYS[plan_name]]
    proj = {n: project_after_plan(soil_data, analysis, fert[k]) for n, k in PLAN_KEYS.items()}
    chosen = proj[plan_name]
    yield_data = predict_yield(soil_data, crop, len(analysis['deficiencies']), len(analysis['excesses']),
                               analysis['health_score'], chosen['score_after'])
    return {
        'analysis': analysis, 'crop_result': crop_result, 'fert': fert, 'plan_name': plan_name,
        'plan_rows': plan_rows, 'projections': proj, 'projected': chosen, 'yield': yield_data,
        'regional': get_regional_comparison(state, district, soil_data) if state else {'found': False},
        'validation': validation_summary(analysis, plan_rows, crop, req),
        'schedule': build_schedule(plan_rows, farm_area, crop),
    }
