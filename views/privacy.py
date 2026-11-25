import streamlit as st
from utils.ui import contact_line, page_setup

page_setup()
st.title('Privacy policy')
st.markdown(f"""
Last updated: 21 November 2026

SoilSense turns your Soil Health Card values into a report and a fertiliser plan. This page explains what
happens to the information you enter.

**What you enter**
Your name, village, district, state, farm size, crop, soil test values, any question you type in the chat,
and, if you choose to upload one, your Soil Health Card or lab report (photo or PDF).

**How it is used**
The information is used only to build your report on screen and in the files you download. SoilSense has no
user accounts and no database. Nothing you enter is saved by the app after your visit ends.

**Services that receive some of your information**
- **Groq (AI text).** When the AI writer is switched on, your crop, farm size, state, soil values and chat
  questions are sent to Groq to write the explanation. Your name, village and district are not sent.
  If you do not want this, leave the AI key unset (the report is then written from fixed rules).
- **Uploaded reports.** A photo or PDF is read on the server to find the soil values, using local text recognition,
  and is not stored. Only if you tick "let AI read it" is the picture sent to Groq. Soil Health Cards can show your
  name, village and survey number, so use that option only if you are comfortable with it.
- **Open-Meteo (weather).** Your district and state name are sent to look up the weather forecast.
- **Hosting.** The app runs on a hosting provider, which may keep ordinary technical logs such as IP address
  and time of visit. We do not use these logs.

**Cookies and tracking**
SoilSense does not use advertising, analytics or tracking cookies. The web framework may keep a technical
session identifier so the page keeps working during your visit. Because there are no optional cookies,
there is no cookie consent banner.

**Do not enter**
Do not type phone numbers, Aadhaar numbers, bank details or other personal identifiers in any field.

**Your choices**
Close the page to end your session. Downloaded files stay on your device until you delete them.

**Changes**
If this policy changes, the date above changes.

{contact_line()}
""")
