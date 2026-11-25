"""For agriculture officers and FPOs: analyse many farms from one CSV."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import fertilizer_engine as FE
from utils.input_validation import LIMITS
from utils.pipeline import PARAMS, run_analysis
from utils.ui import page_setup, show_df

page_setup()
st.title('Batch analysis')
st.markdown('<div class="sub">For agriculture officers and farmer groups. One row per farm. Each farm gets a soil '
            'health score, its shortages, the best-suited crop and the cost of the balanced fertiliser plan.</div>',
            unsafe_allow_html=True)

COLS = ['Farmer', 'Village', 'District', 'State', 'Crop', 'Area_acres'] + PARAMS   # EC is optional in uploads
SAMPLE = pd.DataFrame([
    ['Gurpreet Singh', 'Khanna', 'Ludhiana', 'Punjab', 'Wheat', 4, 6.9, 210, 40, 200, 0.85, 20, 1.4, 12, 1.0, 8, 0.7, 0.3],
    ['Mallesh Gowda', 'Hosahalli', 'Bangalore', 'Karnataka', 'Groundnut', 3, 5.2, 95, 14, 100, 0.35, 7, 0.4, 6, 0.3, 2.5, 0.3, 0.2],
    ['Sunita Devi', 'Nissing', 'Karnal', 'Haryana', 'Rice', 5, 8.3, 150, 22, 170, 0.45, 12, 0.3, 3.8, 0.9, 4, 0.45, 0.9],
    ['Bhavesh Patel', 'Sanand', 'Ahmedabad', 'Gujarat', 'Cotton', 6, 8.8, 420, 90, 470, 0.6, 45, 1.2, 15, 1.0, 9, 1.0, 2.4],
], columns=COLS)

c1, c2 = st.columns([1, 2])
c1.download_button('Download CSV template', SAMPLE.to_csv(index=False).encode('utf-8'), 'soil-batch-template.csv',
                   'text/csv', width='stretch')
up = c2.file_uploader('Upload your CSV', type=['csv'])
use_demo = st.checkbox('Use the template rows as a demo')

df = None
if up is not None:
    if up.size > 2_000_000:
        st.error('The file is larger than 2 MB. Split it and upload again.')
    else:
        try:
            df = pd.read_csv(up)
        except Exception as e:
            st.error(f'Could not read the CSV: {e}')
elif use_demo:
    df = SAMPLE
if df is None:
    st.stop()

df.columns = [c.strip() for c in df.columns]
missing = [c for c in PARAMS + ['Crop'] if c not in df.columns and c != 'EC']
if missing:
    st.error('Missing column(s): ' + ', '.join(missing))
    st.stop()
if len(df) > 500:
    st.warning('Only the first 500 rows are analysed.')
    df = df.head(500)

crops_ok = set(FE.available_crops())
out = []
for i, r in df.iterrows():
    who = str(r.get('Farmer', f'Row {i + 1}'))
    try:
        soil = {p: (float(r[p]) if p in df.columns and pd.notna(r[p]) else 0.0) for p in PARAMS}
        for p, (lo, hi) in LIMITS.items():
            if not (lo <= soil[p] <= hi):
                raise ValueError(f'{p} value {soil[p]:g} is outside the possible range {lo} to {hi}')
        crop = FE.match_crop(str(r['Crop']))
        if not crop:
            raise ValueError(f'unknown crop "{r["Crop"]}"')
        area = float(r['Area_acres']) if 'Area_acres' in df.columns and pd.notna(r['Area_acres']) else 1.0
        res = run_analysis(soil, crop, area, 'Balanced')
        A = res['analysis']
        main = [f"{x['Fertilizer']} {x['per_acre_kg']:.0f} kg/acre" for x in res['plan_rows'] if x['kind'] != 'advisory'][:3]
        out.append({'Farmer': who, 'Village': r.get('Village', ''), 'District': r.get('District', ''), 'Crop': crop,
                    'Score': A['health_score'], 'Category': A['category'],
                    'Low': ', '.join(A['deficiencies']) or 'none', 'High': ', '.join(A['excesses']) or 'none',
                    'Best crop': res['crop_result']['recommendations'][0]['crop'],
                    'Plan cost (Rs)': res['fert']['balanced_cost_value'],
                    'Cost per acre (Rs)': res['fert']['balanced_cost_per_acre'],
                    'Main fertilisers': '; '.join(main)})
    except Exception as e:
        out.append({'Farmer': who, 'Category': f'Not analysed: {e}'})

res_df = pd.DataFrame(out)
ok = res_df.dropna(subset=['Score']) if 'Score' in res_df else res_df.iloc[0:0]
if ok.empty:
    st.error('No rows could be analysed.')
    show_df(res_df)
    st.stop()

k = st.columns(4)
k[0].metric('Farms analysed', len(ok))
k[1].metric('Average score', f"{ok['Score'].mean():.0f} of 100")
k[2].metric('Score below 50', int((ok['Score'] < 50).sum()))
k[3].metric('Total plan cost', f"Rs {ok['Plan cost (Rs)'].sum():,.0f}")

counts = {}
for s in ok['Low']:
    for p in str(s).split(', '):
        if p and p != 'none':
            counts[p] = counts.get(p, 0) + 1
if counts:
    srt = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    fig = go.Figure(go.Bar(x=[a for a, _ in srt], y=[b for _, b in srt], marker_color='#1b4332'))
    fig.update_layout(title='Most common shortages across these farms', yaxis_title='Farms', height=320,
                      paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig, width='stretch')
show_df(res_df)
st.download_button('Download results (CSV)', res_df.to_csv(index=False).encode('utf-8-sig'), 'soil-batch-results.csv',
                   'text/csv')
