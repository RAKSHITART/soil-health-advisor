"""
Generate data/soil_samples.csv: a SYNTHETIC, schema-stable crop/soil dataset.

2,200 records (220 per crop, 10 crops) sampled around agronomic suitability
profiles with deliberate overlap between crops, so a classifier cannot reach
an unrealistic 100%. Replace data/soil_samples.csv with real data (same
columns) and the app retrains automatically.

Run:  python scripts/generate_dataset.py
"""
import os
import numpy as np
import pandas as pd

FEATURES = ['pH', 'Nitrogen', 'Phosphorus', 'Potassium', 'OrganicCarbon',
            'Sulphur', 'Zinc', 'Iron', 'Copper', 'Manganese', 'Boron']

# (mean, sd) per feature, in FEATURES order
PROFILES = {
    'Rice':      [(6.0,.5),(200,40),(40,10),(180,35),(.85,.20),(20,6),(1.2,.4),(15,4),(1.2,.4),(8,2.5),(.60,.15)],
    'Wheat':     [(7.0,.4),(220,40),(45,10),(200,35),(.70,.15),(18,5),(1.0,.3),(9,3),(1.0,.3),(7,2),(.50,.12)],
    'Maize':     [(6.5,.4),(240,45),(50,12),(190,35),(.80,.20),(22,6),(1.5,.4),(12,3.5),(1.5,.4),(9,2.5),(.70,.15)],
    'Cotton':    [(7.6,.5),(150,35),(30,8),(170,35),(.50,.12),(14,4),(.8,.25),(7,2.5),(.8,.25),(5,1.8),(.90,.20)],
    'Sugarcane': [(7.0,.5),(260,40),(55,10),(240,35),(1.0,.20),(26,6),(1.6,.4),(13,3.5),(1.6,.4),(10,2.5),(.80,.15)],
    'Groundnut': [(6.2,.4),(130,30),(35,8),(140,30),(.55,.12),(28,7),(.9,.3),(8,2.5),(.7,.2),(6,2),(.60,.15)],
    'Tomato':    [(6.3,.4),(190,35),(60,10),(220,35),(1.1,.20),(24,6),(1.8,.4),(14,3.5),(1.4,.4),(8,2.5),(.90,.15)],
    'Potato':    [(5.6,.4),(210,35),(55,10),(250,35),(.90,.20),(20,5),(1.3,.35),(11,3),(1.1,.3),(7,2),(.60,.15)],
    'Soybean':   [(6.6,.4),(120,30),(38,8),(160,30),(.70,.15),(25,6),(1.0,.3),(10,3),(.9,.25),(6,2),(.70,.15)],
    'Chickpea':  [(7.2,.5),(110,30),(32,8),(150,30),(.55,.12),(16,5),(.8,.25),(8,2.5),(.8,.2),(5,1.8),(.55,.12)],
}
LOWER = [3.5, 20, 2, 30, 0.05, 1, 0.05, 0.5, 0.05, 0.3, 0.02]
UPPER = [9.5, 600, 200, 600, 6.0, 100, 20, 100, 20, 50, 10]


def main(n_per_crop: int = 220, seed: int = 42) -> None:
    rng = np.random.default_rng(seed)
    frames = []
    for crop, prof in PROFILES.items():
        cols = {f: rng.normal(m, s, n_per_crop) for f, (m, s) in zip(FEATURES, prof)}
        df = pd.DataFrame(cols)
        df['RecommendedCrop'] = crop
        frames.append(df)
    data = pd.concat(frames, ignore_index=True)
    for f, lo, hi in zip(FEATURES, LOWER, UPPER):
        data[f] = data[f].clip(lo, hi)
    data[FEATURES] = data[FEATURES].round(2)
    data = data.sample(frac=1, random_state=seed).reset_index(drop=True)
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       'data', 'soil_samples.csv')
    data.to_csv(out, index=False)
    print(f'Wrote {len(data)} rows -> {out}')


if __name__ == '__main__':
    main()
