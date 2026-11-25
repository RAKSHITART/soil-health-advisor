"""
Crop recommendation with a scikit-learn Random Forest trained on data/soil_samples.csv.

* Real held-out accuracy (80/20 stratified split) and 5-fold CV are reported.
* An input-reliability check flags soil values outside the training range,
  so absurd inputs no longer produce confident answers.
* The user's chosen crop is ranked against all crops.
"""
import os
from functools import lru_cache

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score, train_test_split

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(_BASE, 'data', 'soil_samples.csv')

FEATURES = ['pH', 'Nitrogen', 'Phosphorus', 'Potassium', 'OrganicCarbon',
            'Sulphur', 'Zinc', 'Iron', 'Copper', 'Manganese', 'Boron']
TARGET = 'RecommendedCrop'


@lru_cache(maxsize=1)
def _train():
    df = pd.read_csv(DATA_PATH)
    X, y = df[FEATURES], df[TARGET]
    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42)
    probe = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=1)
    probe.fit(X_tr, y_tr)
    test_acc = float(probe.score(X_te, y_te))
    cv = float(np.mean(cross_val_score(
        RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=1),
        X, y, cv=5)))
    model = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=1)
    model.fit(X, y)
    bounds = {f: (float(df[f].quantile(0.005)), float(df[f].quantile(0.995)))
              for f in FEATURES}
    importance = sorted(zip(FEATURES, model.feature_importances_),
                        key=lambda t: t[1], reverse=True)
    return {
        'model': model, 'test_acc': test_acc, 'cv_acc': cv, 'n': len(df),
        'bounds': bounds, 'importance': importance,
        'classes': list(model.classes_),
    }


def available_crops() -> list:
    return _train()['classes']


def model_info() -> dict:
    t = _train()
    return {'test_accuracy': round(t['test_acc'] * 100, 1),
            'cv_accuracy': round(t['cv_acc'] * 100, 1),
            'n_records': t['n'],
            'feature_importance': [(f, round(float(v), 4)) for f, v in t['importance']]}


def recommend_crops(soil_data: dict, top_n: int = 5, target_crop: str = None) -> dict:
    t = _train()
    row = pd.DataFrame([[float(soil_data.get(f, 0)) for f in FEATURES]], columns=FEATURES)
    proba = t['model'].predict_proba(row)[0]
    ranked = sorted(zip(t['classes'], proba), key=lambda kv: kv[1], reverse=True)

    out_of_range = [f for f in FEATURES
                    if not (t['bounds'][f][0] <= float(soil_data.get(f, 0)) <= t['bounds'][f][1])]
    n_out = len(out_of_range)
    reliability = 'High' if n_out == 0 else ('Medium' if n_out <= 2 else 'Low')

    recs = [{'rank': i + 1, 'crop': c, 'confidence': round(float(p) * 100, 1),
             'source': 'Random Forest (scikit-learn)'}
            for i, (c, p) in enumerate(ranked[:top_n])]

    target = None
    if target_crop:
        for i, (c, p) in enumerate(ranked):
            if c == target_crop:
                target = {'crop': c, 'rank': i + 1, 'of': len(ranked),
                          'suitability': round(float(p) * 100, 1)}
                break

    return {
        'recommendations': recs,
        'all_probabilities': {c: round(float(p) * 100, 1) for c, p in ranked},
        'target': target,
        'reliability': reliability,
        'out_of_range': out_of_range,
        'model_accuracy': round(t['test_acc'] * 100, 1),
        'cv_accuracy': round(t['cv_acc'] * 100, 1),
        'model_type': 'Random Forest (200 trees, scikit-learn)',
        'training_source': f"{t['n']:,}-record schema-compatible dataset (data/soil_samples.csv)",
        'features_used': FEATURES,
        'feature_importance': [(f, round(float(v), 4)) for f, v in t['importance']],
    }
