"""SoilSense: soil health report and fertiliser plan in English, Kannada or Hindi."""
import os
import sys

import streamlit as st

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT, '.env'))
except ImportError:
    pass

st.set_page_config(page_title='SoilSense | Soil report and fertiliser plan',
                   page_icon=os.path.join(ROOT, 'assets', 'favicon.png'),
                   layout='wide', initial_sidebar_state='expanded')

# Hosting secrets -> environment (server side only)
try:
    for _k in ('GROQ_API_KEY', 'CONTACT_EMAIL'):
        if _k in st.secrets and not os.environ.get(_k):
            os.environ[_k] = str(st.secrets[_k])
except Exception:
    pass

# Preflight: if a file was copied to the wrong folder, say exactly which one instead of crashing.
REQUIRED = ['views/home.py', 'views/results.py', 'views/glossary.py', 'views/batch.py', 'views/privacy.py',
            'views/terms.py', 'utils/i18n.py', 'utils/ui.py', 'utils/ocr_extract.py', 'utils/llm_report.py',
            'utils/visualizations.py', 'utils/report_builder.py', 'utils/pdf_generator.py']
missing = [f for f in REQUIRED if not os.path.exists(os.path.join(ROOT, *f.split('/')))]
if missing:
    st.error('Some project files are missing or in the wrong folder.')
    st.write('Project folder: ' + ROOT)
    st.write('Put each of these files at exactly this path inside the project folder:')
    st.code('\n'.join(missing))
    st.write('Common cause: the file was saved in the project root, or its name changed (for example "home (1).py").')
    st.stop()

from utils import i18n
if not hasattr(i18n, 'UI_LANGS'):
    st.error('utils/i18n.py is the old version. Replace it with the new i18n.py and restart.')
    st.stop()
from utils.i18n import t
from utils.ui import brand, divider, page_setup

page_setup()

# ── language: one selector for every page (plain labels, so no stale widget state)
UI = i18n.UI_LANGS
labels = [i18n.NATIVE[x] for x in UI]
current = st.session_state.get('lang', 'English')
with st.sidebar:
    st.markdown(brand(), unsafe_allow_html=True)
    choice = st.radio('Language / ಭಾಷೆ / भाषा', labels, index=UI.index(current) if current in UI else 0,
                      key='lang_choice')
    lang = UI[labels.index(choice)]
    st.session_state.lang = lang
    st.markdown('---')
    st.markdown(f"**{t('sb_title', lang)}**")
    for k in ('sb_1', 'sb_2', 'sb_3'):
        st.markdown(f"<div class='note' style='margin-bottom:.4rem'>{t(k, lang)}</div>", unsafe_allow_html=True)

# Keep the form values alive while another page is open. Streamlit drops a keyed widget's value
# when its page is not shown, so "Back to edit values" would otherwise find an empty form.
FORM_KEYS = ['in_name', 'in_village', 'in_state', 'in_district', 'in_dtxt', 'in_area', 'in_crop', 'in_plan',
             'in_ph', 'in_N', 'in_P', 'in_K', 'in_OC', 'in_S', 'in_Zn', 'in_Fe', 'in_Cu', 'in_Mn', 'in_B', 'in_EC',
             'in_ctext', 'in_cN', 'in_cP', 'in_cK']
for _k in FORM_KEYS:
    if _k in st.session_state:
        st.session_state[_k] = st.session_state[_k]

pages = [
    st.Page('views/home.py', title=t('nav_analyse', lang), url_path='analyse', default=True),
    st.Page('views/results.py', title=t('nav_results', lang), url_path='results'),
    st.Page('views/glossary.py', title=t('nav_glossary', lang), url_path='glossary'),
    st.Page('views/batch.py', title=t('nav_officers', lang), url_path='officers'),
    st.Page('views/privacy.py', title=t('nav_privacy', lang), url_path='privacy'),
    st.Page('views/terms.py', title=t('nav_terms', lang), url_path='terms'),
]
st.navigation(pages, position='top').run()
divider()
st.markdown(f"<div class='note'>{t('disclaimer', lang)}</div>", unsafe_allow_html=True)
