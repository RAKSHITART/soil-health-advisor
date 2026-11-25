"""
Read soil test values from an uploaded Soil Health Card or lab report (PDF or photo).

Order of attempts:
  1. PDF with a text layer      -> read the text directly (exact, no guessing)
  2. Photo or scanned PDF       -> local OCR (Tesseract: English, Kannada, Hindi)
  3. Optional, only if the user ticks the box -> Groq vision model reads the picture

Whatever is found is shown to the farmer in the normal input form to CHECK and fix before
anything is calculated. Values outside what a real soil test can give are dropped.
"""
import base64
import io
import json
import re
import shutil

from utils.input_validation import LIMITS

PARAMS = ['pH', 'Nitrogen', 'Phosphorus', 'Potassium', 'OrganicCarbon', 'Sulphur',
          'Zinc', 'Iron', 'Copper', 'Manganese', 'Boron', 'EC']

# Long names (any language) can match anywhere in a line.
NAMES = {
    'pH': ['soil ph', 'ph value', 'पीएच', 'ಪಿಎಚ್', 'ph'],
    'Nitrogen': ['nitrogen', 'नाइट्रोजन', 'नत्रजन', 'ಸಾರಜನಕ'],
    'Phosphorus': ['phosphorus', 'phosphorous', 'phosphate', 'फॉस्फोरस', 'फास्फोरस', 'ರಂಜಕ'],
    'Potassium': ['potassium', 'potash', 'पोटैशियम', 'पोटाश', 'ಪೊಟ್ಯಾಶ್', 'ಪೊಟ್ಯಾಷಿಯಂ'],
    'OrganicCarbon': ['organic carbon', 'organic c', 'जैविक कार्बन', 'ಸಾವಯವ ಇಂಗಾಲ'],
    'Sulphur': ['sulphur', 'sulfur', 'गंधक', 'सल्फर', 'ಗಂಧಕ'],
    'Zinc': ['zinc', 'जिंक', 'जस्ता', 'ಸತು', 'ಜಿಂಕ್'],
    'Iron': ['iron', 'आयरन', 'लोहा', 'ಕಬ್ಬಿಣ'],
    'Copper': ['copper', 'कॉपर', 'तांबा', 'ತಾಮ್ರ'],
    'Manganese': ['manganese', 'मैंगनीज', 'ಮ್ಯಾಂಗನೀಸ್'],
    'Boron': ['boron', 'बोरॉन', 'ಬೋರಾನ್'],
    'EC': ['electrical conductivity', 'conductivity', 'विद्युत चालकता', 'ವಿದ್ಯುತ್ ವಾಹಕತೆ', 'ec'],
}
# Short symbols are only trusted inside brackets, e.g. "(N)".
SYMBOLS = {'Nitrogen': 'N', 'Phosphorus': 'P', 'Potassium': 'K', 'OrganicCarbon': 'OC', 'Sulphur': 'S',
           'Zinc': 'Zn', 'Iron': 'Fe', 'Copper': 'Cu', 'Manganese': 'Mn', 'Boron': 'B'}
NUM = re.compile(r'(?<![\w.])(\d{1,4}(?:[.,]\d{1,3})?)(?![\w])')


def _to_float(s: str):
    try:
        return float(s.replace(',', '.'))
    except ValueError:
        return None


def parse_soil_text(text: str) -> dict:
    """Return {'values': {param: float}, 'where': {param: line}} found in the text."""
    values, where = {}, {}
    lines = [re.sub(r'\s+', ' ', ln).strip() for ln in text.replace('|', ' ').splitlines()]
    lines = [ln for ln in lines if ln]
    for idx, line in enumerate(lines):
        low = line.lower()
        for p in PARAMS:
            if p in values:
                continue
            pos = None
            for name in NAMES[p]:
                if name == 'ph':
                    m = re.search(r'(?<![a-z])p\.?h(?![a-z])', low)
                elif name == 'ec':
                    m = re.search(r'(?<![a-z])ec(?![a-z])', low)
                else:
                    m = re.search(re.escape(name), low)
                if m:
                    pos = m.end()
                    break
            if pos is None and p in SYMBOLS:
                m = re.search(r'\(\s*' + re.escape(SYMBOLS[p]) + r'\s*\)', line)
                if m and not any(n in low for n in sum((NAMES[q] for q in PARAMS if q != p), [])):
                    pos = m.end()
            if pos is None:
                continue
            tail = re.sub(r'\([^)]*\)', ' ', line[pos:])           # drop "(N)" style brackets
            nums = [_to_float(x) for x in NUM.findall(tail)]
            nums = [x for x in nums if x is not None]
            if not nums and idx + 1 < len(lines):                    # value on the next line
                nums = [_to_float(x) for x in NUM.findall(lines[idx + 1])][:1]
                nums = [x for x in nums if x is not None]
            if nums:
                values[p] = nums[0]
                where[p] = line
    clean = {}
    for p, v in values.items():
        lo, hi = LIMITS[p]
        if lo <= v <= hi:
            clean[p] = v
    return {'values': clean, 'where': {p: where[p] for p in clean}, 'dropped': [p for p in values if p not in clean]}


# ───────────────────────── readers ─────────────────────────
def pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
        r = PdfReader(io.BytesIO(data))
        return '\n'.join((pg.extract_text() or '') for pg in r.pages[:4])
    except Exception:
        return ''


def pdf_to_images(data: bytes, max_pages=2):
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(data)
        return [pdf[i].render(scale=2.2).to_pil() for i in range(min(len(pdf), max_pages))]
    except Exception:
        return []


def tesseract_ready() -> bool:
    try:
        import pytesseract  # noqa: F401
    except ImportError:
        return False
    if shutil.which('tesseract'):
        return True
    import os
    for p in (r'C:\Program Files\Tesseract-OCR\tesseract.exe', r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe'):
        if os.path.exists(p):
            import pytesseract
            pytesseract.pytesseract.tesseract_cmd = p
            return True
    return False


def ocr_image(img) -> str:
    import pytesseract
    from PIL import ImageOps
    g = ImageOps.autocontrast(img.convert('L'))
    if max(g.size) < 1600:
        g = g.resize((g.width * 2, g.height * 2))
    langs = pytesseract.get_languages(config='')
    use = '+'.join(x for x in ('eng', 'kan', 'hin') if x in langs) or 'eng'
    out = []
    for psm in (6, 4):                                   # table-like layouts
        out.append(pytesseract.image_to_string(g, lang=use, config=f'--psm {psm}'))
    return '\n'.join(out)


def _best(*parsed):
    return max(parsed, key=lambda r: len(r['values']))


def _jpeg_b64(img, limit=1800) -> str:
    img = img.convert('RGB')
    if max(img.size) > limit:
        r = limit / max(img.size)
        img = img.resize((int(img.width * r), int(img.height * r)))
    buf = io.BytesIO()
    img.save(buf, 'JPEG', quality=88)
    return base64.b64encode(buf.getvalue()).decode()




def vision_extract(img):
    """Ask a Groq vision model to read the table. Returns parsed dict or None."""
    from utils.llm_report import _client, vision_models
    client = _client()
    if client is None:
        return None
    prompt = ('This is an Indian Soil Health Card or soil lab report. Read the soil TEST VALUES (not the ratings or '
              'recommendations). Return only JSON with these keys and numeric values, using null when a value is not '
              f'visible: {json.dumps({p: None for p in PARAMS})}. Units: N, P, K in kg/ha; organic carbon in %; '
              'S, Zn, Fe, Cu, Mn, B in ppm. Copy numbers exactly. Do not guess.')
    content = [{'type': 'text', 'text': prompt},
               {'type': 'image_url', 'image_url': {'url': 'data:image/jpeg;base64,' + _jpeg_b64(img)}}]
    for m in (vision_models(client) or ['meta-llama/llama-4-scout-17b-16e-instruct']):
        try:
            r = client.chat.completions.create(model=m, temperature=0, max_tokens=500,
                                               messages=[{'role': 'user', 'content': content}])
            raw = r.choices[0].message.content
            blob = re.search(r'\{.*\}', raw, re.S)
            data = json.loads(blob.group(0)) if blob else {}
            vals = {}
            for p in PARAMS:
                v = data.get(p)
                if isinstance(v, (int, float)) and LIMITS[p][0] <= v <= LIMITS[p][1]:
                    vals[p] = float(v)
            return {'values': vals, 'where': {p: 'read by AI vision' for p in vals}, 'dropped': []}
        except Exception:
            continue
    return None


def extract_from_upload(name: str, data: bytes, allow_vision: bool = False) -> dict:
    """Return {'values', 'source', 'notes'}; never raises."""
    notes, tried = [], []
    name = (name or '').lower()
    try:
        images = []
        best = {'values': {}, 'where': {}, 'dropped': []}
        source = 'none'
        if name.endswith('.pdf'):
            txt = pdf_text(data)
            r = parse_soil_text(txt)
            tried.append(('pdf text', r))
            if len(r['values']) >= 6:
                return {'values': r['values'], 'source': 'pdf text', 'notes': notes, 'where': r['where']}
            images = pdf_to_images(data)
            if not images:
                notes.append('no_render')
        else:
            from PIL import Image
            images = [Image.open(io.BytesIO(data))]
        if images and tesseract_ready():
            text = '\n'.join(ocr_image(im) for im in images)
            r = parse_soil_text(text)
            tried.append(('ocr', r))
        elif images:
            notes.append('no_ocr')
        for src, r in tried:
            if len(r['values']) > len(best['values']):
                best, source = r, src
        if allow_vision and images and len(best['values']) < 8:
            v = vision_extract(images[0])
            if v and len(v['values']) > len(best['values']):
                best, source = v, 'ai vision'
            elif v is None:
                notes.append('no_vision')
        return {'values': best['values'], 'source': source, 'notes': notes, 'where': best.get('where', {})}
    except Exception as e:
        return {'values': {}, 'source': 'error', 'notes': ['error:' + str(e)[:120]], 'where': {}}
