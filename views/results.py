"""Results page: dashboard with charts, soil analysis, fertiliser plan, crops, weather, report, chat, downloads."""
import io
from datetime import datetime

import pandas as pd
import streamlit as st

from utils import fertilizer_engine as FE
from utils.crop_recommender import model_info
from utils.i18n import t
from utils.llm_report import ai_available, chatbot_response, generate_narrative
from utils.pdf_generator import generate_pdf
from utils.report_builder import build_report, crop_name, fert_name, template_narrative, to_text
from utils.ui import GREEN, MUTED, STATUS, divider, hero, html_table, kpis, page_setup, show_df
from utils import visualizations as V
from utils.weather import advice_codes

PLANS = ['Budget', 'Balanced', 'Maximum Yield']
MAX_AI_CALLS, MAX_CHAT = 30, 40
CFG = {'displayModeBar': False}
CAT_COLOR = {'Excellent': '#1e40af', 'Good': '#166534', 'Fair': '#92400e', 'Poor': '#b45309', 'Critical': '#9b1c1c'}

page_setup()
for k, v in dict(res=None, chat=[], n_ai=0, n_chat=0).items():
    st.session_state.setdefault(k, v)
lang = st.session_state.get('lang', 'English')
R = st.session_state.res

if not R:
    hero(t('nav_results', lang), t('no_results', lang))
    if st.button(t('go_analyse', lang), type='primary'):
        st.switch_page('views/home.py')
    st.stop()

inp, res, W = R['inp'], R['res'], R['weather']
plan = inp['plan'] if inp['plan'] in PLANS else 'Balanced'   # never trust stored text
rows = res['fert'][FE.PLAN_KEYS[plan]]
res_view = {**res, 'plan_rows': rows, 'weather': W}
A, CR, PR = res['analysis'], res['crop_result'], res['projected']
best = CR['recommendations'][0]

# narrative (AI text, checked) cached per language
if lang not in R['narr']:
    if st.session_state.n_ai < MAX_AI_CALLS:
        with st.spinner(t('wait', lang)):
            R['narr'][lang] = generate_narrative(inp, res_view, lang)
            if R['narr'][lang]['mode'] == 'ai':
                st.session_state.n_ai += 1
    else:
        R['narr'][lang] = {**template_narrative(inp, res_view, lang), 'model': None, 'error': 'limit'}
narr = R['narr'][lang]
rep = build_report(inp, res_view, lang, narr)

# ─────────────────────────── header, actions, KPIs ───────────────────────────
hero(f"{t('report_for', lang)} {inp['farmer']}",
     f"{inp['village']}, {inp['district']}, {inp['state']}  |  {inp['area']} acres  |  {crop_name(inp['crop'], lang)}",
     compact=True)
b1, b2, _ = st.columns([1, 1, 3])
if b1.button(t('back_edit', lang), width='stretch', key='back'):
    st.switch_page('views/home.py')
if b2.button(t('new_analysis', lang), width='stretch', key='new'):
    st.session_state.res = None
    st.session_state.upload_info = None
    for k in ('in_N', 'in_P', 'in_K', 'in_OC', 'in_S', 'in_Zn', 'in_Fe', 'in_Cu', 'in_Mn', 'in_B'):
        st.session_state[k] = 0.0
    st.switch_page('views/home.py')

tg = CR.get('target')
cc = CAT_COLOR.get(A['category'], GREEN)
kpis([
    (t('kpi_score', lang), A['health_score'], f"{rep['category']}", cc),
    (t('kpi_low', lang), len(A['deficiencies']), ', '.join(t(f'n_{p}', lang) for p in A['deficiencies'][:3]) or '-', '#92400e'),
    (t('kpi_high', lang), len(A['excesses']), ', '.join(t(f'n_{p}', lang) for p in A['excesses'][:3]) or '-', '#1e40af'),
    (t('kpi_crop', lang), crop_name(best['crop'], lang), f"{t('match', lang)} {best['confidence']}%", GREEN),
    (t('kpi_cost', lang), f"Rs {rep['total_cost']:,.0f}", t('per_acre_cost', lang, x=f"{rep['cost_per_acre']:,}"), GREEN),
])
for w in rep.get('warnings', []):
    st.warning(w)
if rep['plan_rows']:
    steps_html = ''.join(f'<li>{s}</li>' for s in rep['first_steps'])
    st.markdown(f"<div class='box'><b>{t('do_first', lang)}</b><ol>{steps_html}</ol></div>", unsafe_allow_html=True)
else:
    st.markdown(f"<div class='box'>{t('nothing_needed', lang)}</div>", unsafe_allow_html=True)

divider()
tabs = st.tabs([t('tab_overview', lang), t('tab_soil', lang), t('tab_fert', lang), t('tab_crops', lang),
                t('tab_weather', lang), t('tab_report', lang), t('tab_ask', lang), t('tab_down', lang),
                t('tab_details', lang)])


def plan_table(r):
    html_table([t('h_fert', lang), t('h_acre', lang), t('h_farm', lang), t('h_bags', lang), t('h_when', lang),
                t('h_how', lang), t('h_cost', lang)],
               [[x['fert'], x['acre'], x['farm'], x['bags'], x['when'], x['how'], x['cost']] for x in r['plan_rows']])
    st.markdown(f"**{t('h_total', lang)}: Rs {r['total_cost']:,.0f}**  ({t('per_acre_cost', lang, x=format(r['cost_per_acre'], ','))})")


# ── Overview: the dashboard graphs
with tabs[0]:
    c1, c2 = st.columns([1, 1.7])
    c1.plotly_chart(V.gauge_chart(A['health_score'], A['category'], lang), width='stretch', config=CFG)
    c2.plotly_chart(V.radar_chart(inp['soil'], A, lang), width='stretch', config=CFG)
    st.plotly_chart(V.status_bar_chart(A, lang), width='stretch', config=CFG)
    st.plotly_chart(V.deficiency_heatmap(A, lang), width='stretch', config=CFG)
    st.markdown(f"**{t('projected', lang, a=PR['score_after'], b=PR['score_before'])}**")
    st.markdown(f"<div class='note'>{t('projected_note', lang)}</div>", unsafe_allow_html=True)

# ── Soil analysis
with tabs[1]:
    html_table([t('h_param', lang), t('h_value', lang), t('h_status', lang), t('h_meaning', lang)],
               [[r['name'], r['value'], r['status'], r['meaning']] for r in rep['soil_rows']],
               status_col=2, status_keys=[r['status_en'] for r in rep['soil_rows']])

# ── Fertiliser plan
with tabs[2]:
    st.markdown(f"<div class='note'>{t('fert_intro', lang, area=inp['area'])}</div>", unsafe_allow_html=True)
    st.subheader(f"{t('your_plan_is', lang)}: {t(f'plan_{plan}', lang)}")
    if rep['plan_rows']:
        plan_table(rep)
        st.markdown(f"<div class='note'>{t('price_note', lang)}</div>", unsafe_allow_html=True)
        for r in rep['plan_rows']:
            if r['notes']:
                st.markdown(f"- **{r['fert']}:** {r['notes']}")
        st.subheader(t('sched', lang))
        sched = FE.build_schedule(rows, inp['area'], inp['crop'])
        html_table([t('h_when', lang), t('h_fert', lang), t('h_acre', lang), t('h_farm', lang), t('h_how', lang)],
                   [[t(s['stage_code'], lang), fert_name(s['Fertiliser'], lang), f"{s['per_acre_kg']:,.0f}",
                     f"{s['For your farm (kg)']:,.0f}", t(s['how_code'], lang)] for s in sched])
        items = [(r['fert'], r['cost_value']) for r in rep['plan_rows'] if r['cost_value'] > 0]
        st.plotly_chart(V.cost_by_fertiliser_chart(items, lang), width='stretch', config=CFG)
    else:
        st.write(t('nothing_needed', lang))
    if rep['skip']:
        st.subheader(t('rep_skip', lang))
        for p in rep['skip']:
            st.markdown(f"- {t('skip_line', lang, p=p)}")
    st.subheader(t('other_plans', lang))
    sub = st.tabs([f"{t(f'plan_{p}', lang)} | Rs {res['fert'][FE.PLAN_KEYS[p].replace('_plan', '') + '_cost_value']:,}"
                   for p in PLANS])
    for p, tab in zip(PLANS, sub):
        with tab:
            r2 = build_report(inp, {**res, 'plan_rows': res['fert'][FE.PLAN_KEYS[p]]}, lang, narr)
            if r2['plan_rows']:
                plan_table(r2)
            else:
                st.write(t('nothing_needed', lang))
    cA, cB = st.columns(2)
    cA.plotly_chart(V.cost_comparison_chart(res['fert'], lang), width='stretch', config=CFG)
    vr = [{'plan': n, 'cost': res['fert'][k + '_cost_value'], 'score_after': res['projections'][n]['score_after']}
          for n, k in (('Budget', 'budget'), ('Balanced', 'balanced'), ('Maximum Yield', 'maximal'))]
    cB.plotly_chart(V.value_chart(vr, lang), width='stretch', config=CFG)
    st.plotly_chart(V.before_after_chart(A, PR['analysis'], lang), width='stretch', config=CFG)

# ── Crops
with tabs[3]:
    st.subheader(t('crops_title', lang))
    if CR['reliability'] != 'High':
        st.warning(t('crops_unreliable', lang))
    if not tg:
        st.info(t('crop_no_model', lang, crop=crop_name(inp['crop'], lang)))
    if tg:
        st.write(t('crops_yours', lang, crop=crop_name(inp['crop'], lang), r=tg['rank'], n=tg['of'], pct=tg['suitability']))
    c1, c2 = st.columns([1, 1.2])
    with c1:
        for r in CR['recommendations'][:3]:
            st.markdown(f"<div class='crop'><b>{crop_name(r['crop'], lang)}</b> &nbsp; {t('match', lang)}: {r['confidence']}%"
                        f"<div class='bar'><div style='width:{min(100, r['confidence'])}%'></div></div></div>",
                        unsafe_allow_html=True)
    c2.plotly_chart(V.crop_suitability_chart(CR['recommendations'], lang, inp['crop']), width='stretch', config=CFG)
    html_table([t('h_crop', lang), t('match', lang)],
               [[crop_name(c, lang), f'{p}%'] for c, p in CR['all_probabilities'].items()])

# ── Weather
with tabs[4]:
    if W['mock']:
        st.warning(t('wx_demo', lang))
        if W.get('error'):
            st.caption(f"Reason: {W['error']}")
        if st.button(t('wx_retry', lang), key='wx_retry'):
            from utils.weather import get_weather
            nw = get_weather(inp['district'], inp['state'], inp['village'])
            R['weather'] = nw
            st.rerun()
    st.caption(f"{W.get('place', inp['district'])}  |  {W['source']}")
    kpis([(t('wx_temp', lang), f"{W['temperature']} C", '', GREEN), (t('wx_hum', lang), f"{W['humidity']}%", '', GREEN),
          (t('wx_rain', lang), f"{W['rainfall_mm']} mm", '', GREEN)])
    for code, kw in advice_codes(W, rows):
        st.markdown(f'- {t(code, lang, **kw)}')
    st.plotly_chart(V.forecast_chart(W['forecast'], lang), width='stretch', config=CFG)
    html_table(['Date', 'Max C', 'Min C', 'Rain mm', 'Rain %'],
               [[d['date'], d['tmax'], d['tmin'], d['rain_mm'], d['rain_prob']] for d in W['forecast']])

# ── Report
with tabs[5]:
    st.markdown(f"<div class='note'>{t('rep_ai' if narr['mode'] == 'ai' else 'rep_rules', lang)}</div>", unsafe_allow_html=True)
    st.subheader(t('rep_summary', lang))
    st.write(rep['summary'])
    st.subheader(t('rep_soil', lang))
    html_table([t('h_param', lang), t('h_value', lang), t('h_status', lang), t('h_meaning', lang)],
               [[r['name'], r['value'], r['status'], r['meaning']] for r in rep['soil_rows']],
               status_col=2, status_keys=[r['status_en'] for r in rep['soil_rows']])
    st.subheader(t('rep_plan', lang))
    if rep['plan_rows']:
        plan_table(rep)
    else:
        st.write(t('nothing_needed', lang))
    if rep['skip']:
        st.subheader(t('rep_skip', lang))
        for p in rep['skip']:
            st.markdown(f"- {t('skip_line', lang, p=p)}")
    if rep['risk']:
        st.subheader(t('rep_risk', lang))
        st.write(rep['risk'])
    st.subheader(t('rep_tips', lang))
    for tip in rep['tips']:
        st.markdown(f'- {tip}')
    st.markdown(f"<div class='note'>{rep['disclaimer']}</div>", unsafe_allow_html=True)


# ── Ask (a fragment: sending a message does not reload the whole page)
@st.fragment
def chat_box():
    st.write(t('ask_intro', lang))
    if not ai_available():
        st.markdown(f"<div class='note'>{t('ai_off', lang)}</div>", unsafe_allow_html=True)
    picked = None
    sc = st.columns(3)
    for i, key in enumerate(['ask_s1', 'ask_s2', 'ask_s3']):
        if sc[i].button(t(key, lang), key=f'sug{i}', width='stretch'):
            picked = t(key, lang)
    for m in st.session_state.chat:
        with st.chat_message('user' if m['role'] == 'user' else 'assistant'):
            st.write(m['content'])
    with st.form('chat_form', clear_on_submit=True):
        q = st.text_input(t('ask_ph', lang), max_chars=300)
        sent = st.form_submit_button(t('ask_send', lang))
    question = picked or (q.strip() if sent and q.strip() else None)
    if question:
        if st.session_state.n_chat >= MAX_CHAT:
            st.warning(t('limit', lang))
            return
        st.session_state.n_chat += 1
        hist = list(st.session_state.chat)
        st.session_state.chat.append({'role': 'user', 'content': question})
        with st.spinner(t('wait', lang)):
            ans = chatbot_response(question, inp, res_view, hist, lang)
        st.session_state.chat.append({'role': 'bot', 'content': ans})
        try:
            st.rerun(scope='fragment')          # only the chat refreshes, not the whole page
        except Exception:
            st.rerun()                           # full-page run: refresh everything


with tabs[6]:
    chat_box()

# ── Download
with tabs[7]:
    st.markdown(f"<div class='note'>{t('dl_note', lang)}</div>", unsafe_allow_html=True)
    stamp = datetime.now().strftime('%Y%m%d')
    key = (lang, plan, narr['mode'])
    if key not in R['pdf']:
        R['pdf'][key] = generate_pdf(rep)
    plan_df = pd.DataFrame([{t('h_fert', lang): r['fert'], t('h_acre', lang): r['acre'], t('h_farm', lang): r['farm'],
                             t('h_bags', lang): r['bags'], t('h_when', lang): r['when'], t('h_how', lang): r['how'],
                             t('h_cost', lang): r['cost']} for r in rep['plan_rows']])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine='openpyxl') as xw:
        pd.DataFrame([{t('h_param', lang): r['name'], t('h_value', lang): r['value'], t('h_status', lang): r['status'],
                       t('h_meaning', lang): r['meaning']} for r in rep['soil_rows']]).to_excel(xw, sheet_name='Soil', index=False)
        (plan_df if len(plan_df) else pd.DataFrame({'-': []})).to_excel(xw, sheet_name='Fertiliser', index=False)
        pd.DataFrame([{t('h_crop', lang): crop_name(c, lang), t('match', lang): p}
                      for c, p in CR['all_probabilities'].items()]).to_excel(xw, sheet_name='Crops', index=False)
    d1, d2 = st.columns(2)
    d1.download_button(t('dl_pdf', lang), R['pdf'][key], f'soil-report-{stamp}.pdf', 'application/pdf', type='primary',
                       width='stretch', on_click='ignore')
    d2.download_button(t('dl_txt', lang), to_text(rep).encode('utf-8'), f'soil-report-{stamp}.txt', 'text/plain',
                       width='stretch', on_click='ignore')
    d3, d4 = st.columns(2)
    d3.download_button(t('dl_csv', lang), plan_df.to_csv(index=False).encode('utf-8-sig'), f'fertiliser-plan-{stamp}.csv',
                       'text/csv', width='stretch', on_click='ignore')
    d4.download_button(t('dl_xlsx', lang), buf.getvalue(), f'soil-analysis-{stamp}.xlsx',
                       'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', width='stretch',
                       on_click='ignore')

# ── Details (officers, students; English)
with tabs[8]:
    st.caption('For agriculture officers and students. This tab is in English.')
    Vd = res['validation']
    st.markdown(f"**AI status:** {t('ai_on' if ai_available() else 'ai_off', 'English')}")
    with st.expander('Soil analysis (FAO classes and optimal ranges)', expanded=True):
        show_df(pd.DataFrame([{'Parameter': i['display_name'], 'Value': i['value'], 'Unit': i['unit'],
                               'Status': i['status'], 'Optimal range': i['fao_optimal'], 'Reference': i['fao_ref']}
                              for i in A['parameters'].values()]))
    with st.expander('Validation against references'):
        st.write(f"FAO class and Soil Health Card rating agree on {Vd['agree']} of {Vd['total']} parameters. "
                 f"{Vd['icar_ok']} of {Vd['icar_total']} recommended doses are inside ICAR or crop-package ranges.")
        show_df(pd.DataFrame(Vd['cross_check']))
        if Vd['plan_checks']:
            show_df(pd.DataFrame(Vd['plan_checks']))
        st.caption('Nitrogen often differs: the Soil Health Card uses alkaline permanganate nitrogen (280 to 560 kg/ha is '
                   'medium) while the FAO table here uses broader class limits. The app classifies with the FAO table.')
        for src, title, rel in Vd['references']:
            st.markdown(f'- **{src}:** {title}. {rel}.')
    with st.expander('Regional comparison'):
        reg = res['regional']
        if reg.get('found') and reg['deviations']:
            if reg['level'] == 'state':
                st.caption('District not in the reference file, so the state average is used. Reference values are '
                           'illustrative; replace data/icar_district_data.csv with a Soil Health Card portal export.')
            show_df(pd.DataFrame([{'Parameter': p, 'Your value': d['user'], 'Reference average': d['regional_avg'],
                                   'Difference': f"{d['pct_diff']:+.1f}%"} for p, d in reg['deviations'].items()]))
        else:
            st.write('No reference data for this state.')
    with st.expander('Crop model'):
        mi = model_info()
        st.write(f"{CR['model_type']}. Held-out accuracy {mi['test_accuracy']}%, 5-fold cross-validation "
                 f"{mi['cv_accuracy']}%. Training data: {CR['training_source']}.")
        st.plotly_chart(V.importance_chart(CR['feature_importance'], 'English'), width='stretch', config=CFG)
        st.caption('The training file is synthetic (see README). Replace data/soil_samples.csv with real data using '
                   'the same columns and the model retrains.')
