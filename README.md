# SoilSense

Turns the numbers on a Soil Health Card into a plain-language soil report and a crop-specific fertiliser plan, in
English, Kannada or Hindi.

Built for problem statement PS-A3: AI-Powered Soil Report Interpreter and Fertiliser Recommender.

🚀 **Live Demo:** [Try SoilSense](https://soil-health-advisor-zvq3mcppd6sbuvndmvebdy.streamlit.app/) 

## The problem

Soil Health Cards give farmers a table of numbers (pH, nitrogen, phosphorus, potassium, micronutrients) that most farmers
cannot act on. SoilSense reads those numbers, explains what they mean for the crop the farmer wants to grow, and says
exactly what to apply: which fertiliser, how many kilograms per acre, how many bags, when, and what it costs.

## Features

**Input**
- Type the 12 values from the card, or upload the card (PDF or photo). Values read from an upload are shown in the form
  so the farmer checks and corrects each one before anything is calculated.
- Required-field checks, and values that cannot be real (for example pH 15) are blocked.
- 28 crops in the list, plus any other crop typed in by name.

**Analysis (fixed rules, no AI)**
- Classifies pH, N, P, K, organic carbon, sulphur, zinc, iron, copper, manganese, boron and EC (salinity) using FAO
  classes, and cross-checks each one against the Soil Health Card rating.
- Fertiliser doses from the crop's recommended N, P2O5 and K2O, adjusted by soil status, converted into Urea, DAP or SSP,
  MOP and micronutrient products. Amounts are per acre, for the whole farm, in bags and in rupees, with an application
  schedule. Three plans: lowest cost, balanced, highest yield.
- Nutrients that are already high are skipped, and a salt warning appears when EC is high.

**AI (explanation only)**
- Groq language models write the explanation and answer questions in the farmer's language.
- The AI never decides a status, dose or cost. Its output is checked: valid JSON, correct script, and no number that the
  rule engine did not produce. If a check fails or there is no API key, a fixed-language template is used, so the report
  is always in the chosen language.

**Also**
- Crop suggestions (Random Forest), 7-day weather forecast and the best days to apply fertiliser.
- Chat that answers from the farmer's own results, including "what if I grow carrot".
- Downloads: PDF and text report in the chosen language, fertiliser table (CSV), all tables (Excel).
- Batch page for agriculture officers: analyse many farms from one CSV.
- Privacy policy, terms, glossary in three languages, and a limit on reports per visit.

## How it works

```
type values or upload card
        |
required-field and value checks
        |
FAO classification + Soil Health Card cross-check      (rules)
        |
crop N:P2O5:K2O -> product doses, bags, cost, schedule  (rules)
        |                          |
crop model, weather          AI explanation (checked)
        |                          |
        +------- report in the chosen language -------+
                            |
                PDF / text / CSV / Excel
```

## Tech stack

Python, Streamlit, pandas, scikit-learn, Plotly, fpdf2 (with Noto fonts and text shaping for Kannada and Hindi),
Groq API, Open-Meteo, Tesseract OCR and pypdf for uploads.

## Quick start

```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>
python -m venv venv
venv\Scripts\activate            # macOS and Linux: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env             # Windows: copy .env.example .env
```

Open `.env` and set `GROQ_API_KEY` (free key from https://console.groq.com). Then:

```bash
python check_setup.py            # shows what is wrong with AI, weather or photo reading
streamlit run app.py
```

The app also works without a key; the report then uses fixed templates and the chat answers from your results.

Photo upload needs Tesseract. On Windows install it from https://github.com/UB-Mannheim/tesseract/wiki and tick Kannada
and Hindi under Additional language data. PDFs that contain text need nothing extra.

## Configuration

| Variable | Purpose | Required |
|----------|---------|----------|
| `GROQ_API_KEY` | AI explanation, chat, optional AI photo reading | No |
| `CONTACT_EMAIL` | Shown on the privacy and terms pages | No |

Locally these go in `.env`. On Streamlit Community Cloud they go in Settings, Secrets.

## Deploy

1. Push the repository to GitHub.
2. On https://share.streamlit.io choose Create app, select the repository, branch `main`, main file `app.py`.
3. In Advanced settings choose Python 3.12 and paste your secrets:
   ```toml
   GROQ_API_KEY = "your_key"
   CONTACT_EMAIL = "you@example.com"
   ```
4. Deploy. `packages.txt` installs Tesseract on the server. A `Dockerfile` is also included for Hugging Face Spaces,
   Render, Fly.io or Cloud Run, which you need if you want your own domain.

## Tests

```bash
pip install pytest
pytest -q
```

The tests cover the rule engine, input validation, translations (every phrase in every language), the AI guardrails
(with a simulated Groq), PDF generation in each language, upload reading, and complete runs of the app.

## Data sources and accuracy

- Nutrient classes: FAO Soils Portal. Rating cut-offs: Soil Health Card programme (DAC&FW). Micronutrient, sulphur, lime and
  organic doses: ICAR-NBSS&LUP tables. Crop N, P2O5, K2O: standard package-of-practice values.
- `data/crop_requirements.csv` doses and `data/fertilizer_prices.csv` prices are approximate. Check them against your
  state's package of practices and local prices before relying on them.
- `data/soil_samples.csv`, which trains the crop model, is synthetic (see `scripts/generate_dataset.py`). The model reaches
  about 79 percent held-out accuracy on that data, which says nothing about real fields. Replace the file with real data
  using the same columns and the model retrains. It knows 10 crops; other crops get a plan but no match percentage.
- `data/icar_district_data.csv` holds illustrative district averages, not official figures.
- Kannada and Hindi wording in `utils/i18n.py` should be reviewed by a native speaker before wide use.
- Photo reading was tested on generated cards, not on a large set of real Soil Health Cards. Always check the values it
  reads against the card.

## Limitations

- Advice only. It is not a laboratory report and does not replace an agriculture officer. Confirm doses with your
  Krishi Vigyan Kendra before buying fertiliser.
- Recommendations use the soil values and crop only. They do not account for previous crop, irrigation, variety or
  local rules.
- No user accounts and no saved history. Nothing is stored after the visit ends.

## Project structure

```
app.py                        navigation, language selector, page setup
views/                        analyse, results, batch (officers), glossary, privacy, terms
utils/fertilizer_engine.py    doses, bags, cost, schedule
utils/soil_analyzer.py        FAO classification and score
utils/validation.py           cross-check against Soil Health Card and ICAR ranges
utils/ocr_extract.py          reads values from an uploaded card
utils/input_validation.py     form and value checks
utils/report_builder.py       one report structure for screen, PDF and text
utils/llm_report.py           AI explanation with guardrails, chat, model discovery
utils/i18n.py                 translations
utils/pdf_generator.py        PDF in English, Kannada and Hindi
utils/crop_recommender.py     Random Forest crop model
utils/weather.py              Open-Meteo forecast
data/  assets/  scripts/  tests/  check_setup.py
```

## License

MIT, see `LICENSE`. Noto fonts are under the SIL Open Font License (`assets/fonts/OFL.txt`).
