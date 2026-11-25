import streamlit as st
from utils.ui import contact_line, page_setup

page_setup()
st.title('Terms and conditions')
st.markdown(f"""
Last updated: 21 November 2026

By using SoilSense you agree to these terms.

**1. What SoilSense is**
SoilSense gives general soil and fertiliser advice from the values you enter. It is a decision aid, not a
laboratory test and not a replacement for an agriculture officer.

**2. Advice is approximate**
Fertiliser amounts follow standard package-of-practice doses adjusted by soil status. Prices are approximate.
Real needs depend on your field, water, previous crop, season and variety. Confirm with your Krishi Vigyan
Kendra or agriculture officer before you buy or apply fertiliser.

**3. AI text**
Where AI is used it only writes the explanation. Amounts, doses and costs come from fixed rules. AI text can
still contain mistakes. Check anything important.

**4. Your input**
You are responsible for entering values correctly. Wrong input gives wrong advice. The app blocks values that
cannot be real, but it cannot know every mistake.

**5. Acceptable use**
Do not attack, overload or scrape the service. Report limits exist to keep it available for everyone.

**6. No warranty and limit of liability**
The service is provided as it is, without warranty of any kind. To the extent allowed by law, the owners are
not liable for crop loss, cost or damage that results from using the advice.

**7. Third-party data**
Weather comes from Open-Meteo. Reference ranges come from FAO, ICAR and Soil Health Card publications and
belong to their owners.

**8. Governing law**
These terms are governed by the laws of India.

**9. Changes**
We may update these terms. The date above shows the latest version.

{contact_line()}
""")
