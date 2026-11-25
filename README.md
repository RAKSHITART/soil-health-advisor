# SoilSense

Soil Health Card values in. A soil report and a fertiliser plan out, in English, Kannada or Hindi.
Built for problem statement PS-A3: AI-Powered Soil Report Interpreter and Fertiliser Recommender.

## What it does

* **Two ways to give soil values:** type them, or upload the Soil Health Card or lab report (PDF or photo). The values that are
  read appear in the normal form so you can check and correct every one before anything is calculated.
* Checks that farm details are filled in and blocks values that cannot be real (for example pH 15).
* Classifies 12 values (pH, N, P, K, organic carbon, sulphur, zinc, iron, copper, manganese, boron and EC salinity)
  with fixed agronomy rules (FAO classes) and cross-checks them with the Soil Health Card ratings.
* Works out fertiliser doses with fixed rules for 28 crops, or for any other crop you type in: crop N:P2O5:K2O adjusted by
  soil status, converted to Urea, DAP or SSP, MOP and micronutrients. Amounts are shown per acre, for the whole farm, in
  bags and in rupees, with an application schedule and Budget, Balanced and Highest-yield plans.
* The AI only writes the explanation. Its output is checked (valid JSON, correct script, no invented numbers). If a check
  fails or there is no key, a fixed-language template is used, so the report is always in the chosen language.
* Crop suggestions (Random Forest), 7-day weather with the best days to apply fertiliser, and a chat that answers from the
  farmer's own soil data, including "what if I grow carrot".
* Downloads: PDF and text report in the chosen language, fertiliser table (CSV), all tables (Excel).
* Batch page for officers: upload many farms in one CSV.

```
type or upload -> check values -> required-field and value checks -> rule-based classification
  -> rule-based doses, bags, cost -> crop model, weather -> AI explanation (checked)
  -> report in the chosen language -> PDF / text / CSV / Excel
```

## Run locally

```bash
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # then put your key in .env: GROQ_API_KEY=...
python check_setup.py                                 # tells you what is wrong with AI, weather or photo reading
streamlit run app.py
pytest -q
```

The `.env` file must be named exactly `.env` (not `.env.txt`). The app works without a key, but the AI chat and the
AI-written text stay off. Groq renames models often, so the app asks Groq which models your key can use.

Reading photos of soil cards offline needs Tesseract (Windows: https://github.com/UB-Mannheim/tesseract/wiki, tick Kannada
and Hindi). PDFs with text need nothing extra. On Streamlit Cloud, `packages.txt` installs it.

## Deploy

Streamlit Community Cloud: push to GitHub, create the app with main file `app.py`, then add `GROQ_API_KEY` (and optionally
`CONTACT_EMAIL`) under Settings, Secrets. A `Dockerfile` is included for Hugging Face Spaces, Render, Fly.io or Cloud Run
(needed for a custom domain). See `LAUNCH_CHECKLIST.md`.

## Data notes

* `data/soil_samples.csv` is synthetic (`scripts/generate_dataset.py`) with the columns a real dataset would have. Replace it
  with real data and the model retrains. The model knows 10 crops; other crops get a fertiliser plan but no match percentage.
* `data/icar_district_data.csv` holds illustrative district averages. Use a Soil Health Card portal export for official values.
* Crop doses (`data/crop_requirements.csv`) and fertiliser prices are approximate and editable. Check them against your
  state's package of practices.
* Kannada and Hindi wording in `utils/i18n.py` should be reviewed by a native speaker before a public launch.
* Fonts: Noto Sans (SIL Open Font License, see `assets/fonts/OFL.txt`).

## Layout

```
app.py                       navigation, language selector, page setup
views/                       home (Analyse), results, batch, glossary, privacy, terms
utils/fertilizer_engine.py   dose, bags, cost, schedule (no LLM)
utils/soil_analyzer.py       FAO classification and score
utils/ocr_extract.py         reads values from an uploaded card (PDF text, OCR, optional AI vision)
utils/input_validation.py    form and value checks
utils/report_builder.py      one report structure for screen, PDF and text
utils/llm_report.py          AI explanation with guardrails, chat, model discovery
utils/i18n.py                translations (English, Kannada, Hindi)
utils/pdf_generator.py       PDF with shaped Kannada and Hindi text
utils/ui.py                  farm look and feel
data/  assets/  scripts/  tests/  check_setup.py
```
