"""Analyse page: type soil values or upload the Soil Health Card, check them, then get the report."""
import csv
import os
import time

import streamlit as st

from utils import fertilizer_engine as FE
from utils import i18n
from utils.crop_recommender import model_info
from utils.i18n import t
from utils.input_validation import validate_inputs
from utils.llm_report import estimate_crop_requirement
from utils.ocr_extract import PARAMS, extract_from_upload, tesseract_ready
from utils.pipeline import run_analysis
from utils.report_builder import crop_name
from utils.ui import divider, hero, page_setup, steps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_REPORTS, COOLDOWN, MAX_UPLOAD = 15, 6, 8 * 1024 * 1024
PLANS = ['Budget', 'Balanced', 'Maximum Yield']
STATES = ['Punjab', 'Haryana', 'Uttar Pradesh', 'Maharashtra', 'Tamil Nadu', 'Karnataka', 'West Bengal', 'Gujarat',
          'Madhya Pradesh', 'Rajasthan', 'Andhra Pradesh', 'Telangana', 'Bihar', 'Odisha', 'Kerala', 'Other']
KEYS = {'pH': 'in_ph', 'Nitrogen': 'in_N', 'Phosphorus': 'in_P', 'Potassium': 'in_K', 'OrganicCarbon': 'in_OC',
        'Sulphur': 'in_S', 'Zinc': 'in_Zn', 'Iron': 'in_Fe', 'Copper': 'in_Cu', 'Manganese': 'in_Mn', 'Boron': 'in_B',
        'EC': 'in_EC'}
OTHER_CROP = '__other__'
DEFAULTS = dict(in_name='', in_village='', in_state='Karnataka', in_district='', in_dtxt='', in_area=2.0,
                in_crop='Rice', in_plan='Balanced', in_ph=0.0, in_N=0.0, in_P=0.0, in_K=0.0, in_OC=0.0, in_S=0.0,
                in_Zn=0.0, in_Fe=0.0, in_Cu=0.0, in_Mn=0.0, in_B=0.0, in_EC=0.0, in_ctext='', in_cN=0.0, in_cP=0.0,
                in_cK=0.0)
EXAMPLES = {
    'Healthy soil, Wheat, Punjab': dict(in_name='Gurpreet Singh', in_village='Khanna', in_state='Punjab', in_district='Ludhiana',
        in_crop='Wheat', in_area=4.0, in_ph=6.9, in_N=210.0, in_P=40.0, in_K=200.0, in_OC=0.85, in_S=20.0, in_Zn=1.4,
        in_Fe=12.0, in_Cu=1.0, in_Mn=8.0, in_B=0.7, in_EC=0.3),
    'Poor acidic soil, Groundnut, Karnataka': dict(in_name='Mallesh Gowda', in_village='Hosahalli', in_state='Karnataka',
        in_district='Bangalore', in_crop='Groundnut', in_area=3.0, in_ph=5.2, in_N=95.0, in_P=14.0, in_K=100.0,
        in_OC=0.35, in_S=7.0, in_Zn=0.4, in_Fe=6.0, in_Cu=0.3, in_Mn=2.5, in_B=0.3, in_EC=0.2),
    'Alkaline soil, Rice, Haryana': dict(in_name='Sunita Devi', in_village='Nissing', in_state='Haryana', in_district='Karnal',
        in_crop='Rice', in_area=5.0, in_ph=8.3, in_N=150.0, in_P=22.0, in_K=170.0, in_OC=0.45, in_S=12.0, in_Zn=0.3,
        in_Fe=3.8, in_Cu=0.9, in_Mn=4.0, in_B=0.45, in_EC=0.9),
    'Too much fertiliser, Cotton, Gujarat': dict(in_name='Bhavesh Patel', in_village='Sanand', in_state='Gujarat',
        in_district='Ahmedabad', in_crop='Cotton', in_area=6.0, in_ph=8.8, in_N=420.0, in_P=90.0, in_K=470.0,
        in_OC=0.6, in_S=45.0, in_Zn=1.2, in_Fe=15.0, in_Cu=1.0, in_Mn=9.0, in_B=1.0, in_EC=2.4),
}


@st.cache_data
def _districts():
    out = {}
    with open(os.path.join(ROOT, 'data', 'icar_district_data.csv'), newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            out.setdefault(r['State'], []).append(r['District'])
    return out


@st.cache_resource(show_spinner=False)
def _warm():
    return model_info()


@st.cache_resource(show_spinner=False)
def _wx_store():
    return {}


def _weather(district, state, village='', force=False):
    """Cache live forecasts for 30 minutes. Failed lookups are never cached, so the next try is fresh."""
    from utils.weather import get_weather
    store, key = _wx_store(), (district.lower(), state.lower())
    hit = store.get(key)
    if hit and not force and time.time() - hit[0] < 1800:
        return hit[1]
    w = get_weather(district, state, village)
    if not w['mock']:
        store[key] = (time.time(), w)
    return w


def _load_example(name):
    for k, v in EXAMPLES[name].items():
        st.session_state[k] = v
    st.session_state.in_ctext = ''
    st.session_state.upload_info = None


def _resolve_crop():
    """Return (crop name, requirement or None, source, error code). Source: table, farmer or ai."""
    s = st.session_state
    if s.in_crop != OTHER_CROP:
        return s.in_crop, None, 'table', None
    name = s.in_ctext.strip()
    if not name:
        return '', None, 'table', 'v_cropname'
    listed = FE.match_crop(name)                       # typed "carrot" or "gajar": use the table
    if listed:
        return listed, None, 'table', None
    n, p, k = float(s.in_cN), float(s.in_cP), float(s.in_cK)
    if n + p + k > 0:
        return name, FE.custom_requirement(n, p, k), 'farmer', None
    est = estimate_crop_requirement(name)
    if est:
        return name, FE.custom_requirement(est['N'], est['P2O5'], est['K2O'], est['legume'], est['vegetable']), 'ai', None
    return name, None, 'table', 'v_crop_unknown'


def _inputs():
    s = st.session_state
    soil = {p: float(s[k]) for p, k in KEYS.items()}
    return dict(farmer=s.in_name.strip(), village=s.in_village.strip(), state=s.in_state,
                district=(s.in_dtxt.strip() if s.in_district == '' else s.in_district), area=float(s.in_area),
                crop=s.in_crop, plan=s.in_plan, soil=soil, crop_req=None, crop_source='table')


def _pick(label, options, current, texts):
    """Selectbox with translated texts; returns the underlying option (no format_func state)."""
    i = options.index(current) if current in options else 0
    return options[texts.index(st.selectbox(label, texts, index=i))]


page_setup()
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)
for k, v in dict(res=None, n_reports=0, last_run=0.0, upload_info=None).items():
    st.session_state.setdefault(k, v)
_warm()
lang = st.session_state.get('lang', 'English')

hero('SoilSense', t('tagline', lang))
steps([t('step_1', lang), t('step_2', lang), t('step_3', lang)], 0 if st.session_state.upload_info is None else 1)

left, right = st.columns([2.3, 1], gap='large')

# ─────────────────────────── right: what you get + examples ───────────────────────────
with right:
    items = ''.join(f"<li>{t(f'gets_{i}', lang)}</li>" for i in range(1, 7))
    st.markdown(f"<div class='panel'><b>{t('gets_title', lang)}</b><ul>{items}</ul></div>", unsafe_allow_html=True)
    st.markdown(f"**{t('examples', lang)}**")
    for i, name in enumerate(EXAMPLES):
        st.button(name, key=f'ex{i}', on_click=_load_example, args=(name,), width='stretch')
    if st.session_state.res:
        st.markdown('---')
        if st.button(t('nav_results', lang), type='primary', width='stretch', key='to_res'):
            st.switch_page('views/results.py')

# ─────────────────────────── left: input ───────────────────────────
with left:
    st.subheader(t('method_label', lang))
    tab_type, tab_up = st.tabs([t('method_manual', lang), t('method_upload', lang)])
    with tab_type:
        st.markdown(f"<div class='note'>{t('type_hint', lang)}</div>", unsafe_allow_html=True)
    with tab_up:
        up = st.file_uploader(t('up_label', lang), type=['png', 'jpg', 'jpeg', 'pdf'], key='upfile')
        from utils.llm_report import vision_models
        vision_ok = bool(vision_models())
        vision = st.checkbox(t('up_vision', lang), key='allow_vision') if vision_ok else False
        if st.button(t('up_read', lang), disabled=up is None, key='readbtn'):
            if up.size > MAX_UPLOAD:
                st.error(t('up_size', lang))
            else:
                with st.spinner(t('up_reading', lang)):
                    out = extract_from_upload(up.name, up.getvalue(), allow_vision=vision)
                for p, v in out['values'].items():
                    st.session_state[KEYS[p]] = float(v)
                st.session_state.upload_info = out
                st.rerun()
        info = st.session_state.upload_info
        if info is not None:
            n = len(info['values'])
            if n == 0:
                st.warning(t('up_none', lang) + (' ' + t('up_no_ocr', lang) if 'no_ocr' in info['notes'] else ''))
            else:
                st.success(t('up_found', lang, n=n, src=info['source']))
                miss = [t(f'n_{p}', lang) for p in PARAMS if p not in info['values']]
                if miss:
                    st.warning(t('up_missing', lang, x=', '.join(miss)))
        if not tesseract_ready() and not vision_ok:
            st.info(t('up_no_photo', lang))

    divider()
    st.subheader(t('sec_farm', lang))
    c1, c2 = st.columns(2)
    c1.text_input(t('f_name', lang), key='in_name')
    c2.text_input(t('f_village', lang), key='in_village')
    c1.selectbox(t('f_state', lang), STATES, key='in_state')
    known = _districts().get(st.session_state.in_state, [])
    other = t('f_district_other', lang)
    cur = st.session_state.in_district if st.session_state.in_district in known else ''
    pick = c2.selectbox(t('f_district', lang), known + [other], index=known.index(cur) if cur in known else len(known))
    st.session_state.in_district = '' if pick == other else pick
    if st.session_state.in_district == '':
        c2.text_input(t('f_district_type', lang), key='in_dtxt')
    c1.number_input(t('f_area', lang), 0.1, 500.0, step=0.5, key='in_area')
    crops = FE.available_crops()
    with c2:
        st.session_state.in_crop = _pick(t('f_crop', lang), crops + [OTHER_CROP], st.session_state.in_crop,
                                         [crop_name(c, lang) for c in crops] + [t('f_crop_other', lang)])
    if st.session_state.in_crop == OTHER_CROP:
        st.text_input(t('f_crop_name', lang), key='in_ctext')
        st.markdown(f"<div class='note'>{t('crop_doses_hint', lang)}</div>", unsafe_allow_html=True)
        d1, d2, d3 = st.columns(3)
        d1.number_input('N (kg/ha)', 0.0, 400.0, step=5.0, key='in_cN')
        d2.number_input('P2O5 (kg/ha)', 0.0, 250.0, step=5.0, key='in_cP')
        d3.number_input('K2O (kg/ha)', 0.0, 400.0, step=5.0, key='in_cK')

    st.subheader(t('sec_soil', lang))
    st.markdown(f"<div class='note'>{t('soil_hint', lang)} {t('confirm_note', lang)}</div>", unsafe_allow_html=True)
    a, b = st.columns(2)
    a.number_input(t('p_pH', lang), 0.0, 14.0, step=0.1, format='%.1f', key='in_ph')
    a.number_input(t('p_Nitrogen', lang), 0.0, 1500.0, step=1.0, format='%.0f', key='in_N')
    a.number_input(t('p_Phosphorus', lang), 0.0, 600.0, step=1.0, format='%.1f', key='in_P')
    a.number_input(t('p_Potassium', lang), 0.0, 2000.0, step=1.0, format='%.0f', key='in_K')
    a.number_input(t('p_OrganicCarbon', lang), 0.0, 15.0, step=0.01, format='%.2f', key='in_OC')
    a.number_input(t('p_Sulphur', lang), 0.0, 600.0, step=0.5, format='%.1f', key='in_S')
    b.number_input(t('p_Zinc', lang), 0.0, 60.0, step=0.05, format='%.2f', key='in_Zn')
    b.number_input(t('p_Iron', lang), 0.0, 600.0, step=0.1, format='%.1f', key='in_Fe')
    b.number_input(t('p_Copper', lang), 0.0, 60.0, step=0.05, format='%.2f', key='in_Cu')
    b.number_input(t('p_Manganese', lang), 0.0, 600.0, step=0.1, format='%.1f', key='in_Mn')
    b.number_input(t('p_Boron', lang), 0.0, 25.0, step=0.05, format='%.2f', key='in_B')
    b.number_input(t('p_EC', lang), 0.0, 40.0, step=0.05, format='%.2f', key='in_EC')
    zero = [t(f'n_{p}', lang) for p, k in KEYS.items() if float(st.session_state[k]) == 0]
    st.markdown(f"<div class='note'>{t('values_n', lang, n=len(KEYS) - len(zero))}"
                + (f" | {t('values_zero', lang, x=', '.join(zero))}" if zero else '') + '</div>', unsafe_allow_html=True)

    st.subheader(t('sec_plan', lang))
    texts = [t(f'plan_{p}', lang) for p in PLANS]
    st.session_state.in_plan = PLANS[texts.index(st.radio(
        t('sec_plan', lang), texts, index=PLANS.index(st.session_state.in_plan), horizontal=True,
        label_visibility='collapsed'))]
    st.markdown(f"<div class='note'>{t('plan_help', lang)}</div>", unsafe_allow_html=True)
    go_btn = st.button(t('submit', lang), type='primary', width='stretch', key='submit')

if go_btn:
    inp = _inputs()
    errors = validate_inputs(inp['farmer'], inp['village'], inp['district'], inp['area'], inp['soil'], lang)
    if not errors:
        with st.spinner(t('wait', lang)):
            crop, req, src, err = _resolve_crop()
        if err:
            errors.append(t(err, lang, c=crop))
        else:
            inp.update(crop=crop, crop_req=req, crop_source=src)
    now = time.time()
    if not errors and st.session_state.n_reports >= MAX_REPORTS:
        errors = [t('limit', lang)]
    elif not errors and now - st.session_state.last_run < COOLDOWN:
        errors = [t('cooldown', lang, s=int(COOLDOWN - (now - st.session_state.last_run)) + 1)]
    if errors:
        with left:
            st.error(t('fix_errors', lang) + '\n\n' + '\n'.join(f'- {e}' for e in errors))
    else:
        with st.spinner(t('wait', lang)):
            res = run_analysis(inp['soil'], inp['crop'], inp['area'], inp['plan'], inp['state'], inp['district'], inp['crop_req'])
            weather = _weather(inp['district'], inp['state'], inp['village'])
        st.session_state.res = dict(inp=inp, res=res, weather=weather, narr={}, pdf={})
        st.session_state.chat = []
        st.session_state.n_reports += 1
        st.session_state.last_run = now
        st.switch_page('views/results.py')
