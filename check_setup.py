"""
Run this once to see what is wrong with AI or weather on YOUR computer:

    python check_setup.py

It checks the .env file, the Groq key, the internet route to Groq and Open-Meteo, and photo reading (OCR).
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
ok = lambda m: print('  OK    ' + m)
bad = lambda m: print('  FIX   ' + m)

print('\n1. The .env file')
env = os.path.join(ROOT, '.env')
if os.path.exists(env):
    ok('found ' + env)
elif os.path.exists(env + '.txt'):
    bad('the file is named ".env.txt". Rename it to exactly ".env" (turn on "File name extensions" in Explorer).')
else:
    bad('no .env file. Create a file named .env in ' + ROOT + ' with one line:  GROQ_API_KEY=your_key_here')
try:
    from dotenv import load_dotenv
    load_dotenv(env)
except Exception:
    bad('python-dotenv is not installed. Run: pip install -r requirements.txt')

print('\n2. Groq key (AI chat and AI-written report)')
key = os.environ.get('GROQ_API_KEY', '').strip()
if not key or key.startswith('your_'):
    bad('GROQ_API_KEY is empty or still the placeholder. Put the real key in .env (no quotes, no spaces) and restart.')
else:
    ok(f'key found ({key[:4]}...{key[-3:]}, {len(key)} characters)')
    try:
        from utils import llm_report as L
        models = L.list_models()
        if models:
            ok('models available to your key: ' + ', '.join(models[:8]) + (' ...' if len(models) > 8 else ''))
            ok('app will use: ' + L.text_models()[0] + ' (falls back to the next ones if it fails)')
            vm = L.vision_models()
            ok('photo-reading AI model: ' + (vm[0] if vm else 'none found (the AI photo option will not work)'))
        else:
            bad('could not list models. Check the key and the internet connection.')
        text, used = L._chat([{'role': 'user', 'content': 'Reply with the word OK.'}], 20)
        ok(f'Groq answered with {used}: {text[:20]}')
    except Exception as e:
        bad(f'Groq call failed: {type(e).__name__}: {str(e)[:200]}')
        print('        401 = wrong key. 403/404 = this key has no access to the model. Timeout = internet, firewall, VPN or proxy.')

print('\n3. Live weather (Open-Meteo)')
try:
    from utils.weather import get_weather
    w = get_weather('Dharwad', 'Karnataka')
    if w['mock']:
        bad('weather failed: ' + str(w.get('error')))
        print('        "CERTIFICATE_VERIFY_FAILED" = run: pip install --upgrade certifi')
        print('        "timed out" / "getaddrinfo failed" = no internet, or a firewall or proxy blocks api.open-meteo.com')
    else:
        ok(f"{w['place']}: {w['temperature']} C, {w['description']}")
except Exception as e:
    bad(f'{type(e).__name__}: {e}')

print('\n4. Photo reading (OCR) for uploaded soil cards')
try:
    from utils.ocr_extract import tesseract_ready
    if tesseract_ready():
        import pytesseract
        ok('Tesseract found, languages: ' + ', '.join(pytesseract.get_languages(config='')))
    else:
        bad('Tesseract is not installed. PDFs with text and the "let AI read it" option still work. To read photos offline, install Tesseract from https://github.com/UB-Mannheim/tesseract/wiki and tick Kannada and Hindi under Additional language data.')
except Exception as e:
    bad(f'{type(e).__name__}: {e}')
print()
