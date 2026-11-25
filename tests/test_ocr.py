import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest

from utils.ocr_extract import extract_from_upload, parse_soil_text, tesseract_ready

CARD = """SOIL HEALTH CARD
S.No Parameter Test Value Unit Rating
1 pH 6.8 Neutral
2 EC (Electrical Conductivity) 0.32 dS/m Normal
3 Organic Carbon (OC) 0.48 % Low
4 Available Nitrogen (N) 215 kg/ha Low
5 Available Phosphorus (P) 28.4 kg/ha High
6 Available Potassium (K) 190 kg/ha Medium
7 Available Sulphur (S) 9.5 ppm Low
8 Available Zinc (Zn) 0.45 ppm Deficient
9 Available Boron (B) 0.38 ppm Deficient
10 Available Iron (Fe) 7.2 ppm Sufficient
11 Available Manganese (Mn) 3.1 ppm Sufficient
12 Available Copper (Cu) 1.05 ppm Sufficient"""
EXPECT = {'pH': 6.8, 'OrganicCarbon': 0.48, 'Nitrogen': 215.0, 'Phosphorus': 28.4, 'Potassium': 190.0, 'Sulphur': 9.5,
          'Zinc': 0.45, 'Boron': 0.38, 'Iron': 7.2, 'Manganese': 3.1, 'Copper': 1.05, 'EC': 0.32}


def test_parser_reads_all_twelve_values_including_ec():
    assert parse_soil_text(CARD)['values'] == EXPECT


def test_parser_drops_impossible_values():
    r = parse_soil_text('pH 15.0\nAvailable Nitrogen (N) 215 kg/ha')
    assert 'pH' not in r['values'] and r['values']['Nitrogen'] == 215.0 and 'pH' in r['dropped']


def test_parser_reads_hindi_and_kannada_names():
    r = parse_soil_text('नाइट्रोजन 180 किलो\nಸಾರಜನಕ 150\nजिंक 0.5\nಪಿಎಚ್ 6.5')
    assert r['values']['Zinc'] == 0.5 and r['values']['pH'] == 6.5 and r['values']['Nitrogen'] in (180.0, 150.0)


def test_text_pdf_is_read_exactly():
    from fpdf import FPDF
    p = FPDF()
    p.add_page()
    p.set_font('Helvetica', size=12)
    for ln in CARD.split('\n'):
        p.cell(0, 8, ln, new_x='LMARGIN', new_y='NEXT')
    out = extract_from_upload('card.pdf', bytes(p.output()))
    assert out['source'] == 'pdf text' and out['values'] == EXPECT


@pytest.mark.skipif(not tesseract_ready(), reason='tesseract not installed')
def test_photo_is_read_by_ocr():
    from PIL import Image, ImageDraw, ImageFont
    font = None
    for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'C:/Windows/Fonts/arial.ttf',
              os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'fonts', 'NotoSansDevanagari-Regular.ttf')):
        if os.path.exists(f):
            font = ImageFont.truetype(f, 30)
            break
    im = Image.new('RGB', (1100, 900), 'white')
    d = ImageDraw.Draw(im)
    for i, ln in enumerate(CARD.split('\n')):
        d.text((40, 30 + i * 60), ln, font=font, fill='black')
    buf = io.BytesIO()
    im.save(buf, 'PNG')
    out = extract_from_upload('card.png', buf.getvalue())
    assert out['source'] == 'ocr' and len(out['values']) >= 10
    for k, v in out['values'].items():
        assert v == EXPECT[k]


def test_unreadable_file_never_raises():
    assert extract_from_upload('x.png', b'not an image')['values'] == {}
    assert extract_from_upload('x.pdf', b'%PDF-broken')['values'] == {}
