import streamlit as st

from utils import i18n
from utils.ui import hero, page_setup

page_setup()
lang = st.session_state.get('lang', 'English')
hero(i18n.t('g_title', lang), '')
for term in i18n.GLOSSARY_TERMS:
    st.markdown(f"- {i18n.t('g_' + term, lang)}")
