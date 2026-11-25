"""
PDF report in the farmer's language (fpdf2 + Noto Sans fonts with text shaping, so Hindi,
Kannada, Tamil, Telugu and Marathi render correctly). Built from utils.report_builder.build_report.
"""
import os
from datetime import datetime

from fpdf import FPDF
from fpdf.fonts import FontFace

from utils import i18n
from utils.i18n import t

FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets', 'fonts')
GREEN = (27, 67, 50)
LIGHT = (243, 246, 241)


class _PDF(FPDF):
    def footer(self):
        self.set_y(-12)
        self.set_font(self.fam, '', 8)
        self.set_text_color(90, 90, 90)
        self.cell(0, 6, f'SoilSense  |  {datetime.now():%d %b %Y}  |  {self.page_no()}', align='C')


def generate_pdf(rep: dict) -> bytes:
    lang = rep['lang']
    fam = i18n.FONT_FILE[lang]
    pdf = _PDF(format='A4')
    pdf.fam = fam
    pdf.set_margins(15, 14, 15)
    pdf.set_auto_page_break(True, 16)
    pdf.add_font(fam, '', os.path.join(FONT_DIR, f'NotoSans{fam}-Regular.ttf'))
    pdf.add_font(fam, 'B', os.path.join(FONT_DIR, f'NotoSans{fam}-Bold.ttf'))
    pdf.set_text_shaping(True)
    pdf.add_page()
    W = pdf.epw

    def h2(text):
        pdf.ln(3)
        pdf.set_font(fam, 'B', 12)
        pdf.set_text_color(*GREEN)
        pdf.multi_cell(W, 7, text, new_x='LMARGIN', new_y='NEXT')
        pdf.set_draw_color(*GREEN)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + W, pdf.get_y())
        pdf.ln(2)
        pdf.set_text_color(25, 25, 25)

    def para(text, size=10):
        pdf.set_font(fam, '', size)
        pdf.multi_cell(W, 5.6, text, new_x='LMARGIN', new_y='NEXT')

    def table(headers, rows, widths):
        pdf.set_font(fam, '', 9)
        pdf.set_text_color(25, 25, 25)
        pdf.set_fill_color(255, 255, 255)
        with pdf.table(col_widths=widths, width=W, line_height=5.2, text_align='LEFT',
                       headings_style=FontFace(emphasis='BOLD', color=(255, 255, 255), fill_color=GREEN),
                       borders_layout='HORIZONTAL_LINES', padding=1.2) as tb:
            hr = tb.row()
            for h in headers:
                hr.cell(h)
            for r in rows:
                row = tb.row()
                for c in r:
                    row.cell(str(c))

    # title bar
    pdf.set_fill_color(*GREEN)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font(fam, 'B', 17)
    pdf.cell(W, 13, rep['title'], fill=True, align='C', new_x='LMARGIN', new_y='NEXT')
    pdf.set_text_color(25, 25, 25)
    pdf.ln(3)

    m = rep['meta']
    pdf.set_font(fam, '', 10)
    pdf.multi_cell(W, 5.8, f"{t('f_name', lang)}: {m['farmer']}    {t('f_village', lang)}: {m['village']}\n"
                           f"{t('f_district', lang)}: {m['district']}, {m['state']}    {t('f_area', lang)}: {m['area']}\n"
                           f"{t('f_crop', lang)}: {m['crop']}    {t('tab_fert', lang)}: {m['plan']}",
                   new_x='LMARGIN', new_y='NEXT')
    pdf.ln(1)
    pdf.set_font(fam, 'B', 13)
    pdf.set_text_color(*GREEN)
    pdf.multi_cell(W, 8, f"{t('soil_health', lang)}: {rep['category']} ({t('score_text', lang, score=rep['score'])})",
                   new_x='LMARGIN', new_y='NEXT')
    pdf.set_text_color(25, 25, 25)

    h2(t('rep_summary', lang))
    para(rep['summary'])

    if rep.get('warnings'):
        h2(t('rep_warn', lang))
        for w in rep['warnings']:
            para('- ' + w, 10)

    h2(t('rep_soil', lang))
    table([t('h_param', lang), t('h_value', lang), t('h_status', lang), t('h_meaning', lang)],
          [[r['name'], r['value'], r['status'], r['meaning']] for r in rep['soil_rows']], (40, 28, 25, 87))

    h2(t('rep_plan', lang))
    if rep['plan_rows']:
        table([t('h_fert', lang), t('h_acre', lang), t('h_farm', lang), t('h_bags', lang), t('h_when', lang),
               t('h_cost', lang)],
              [[r['fert'], r['acre'], r['farm'], r['bags'], r['when'], r['cost']] for r in rep['plan_rows']],
              (36, 20, 22, 24, 56, 22))
        pdf.ln(1)
        pdf.set_font(fam, 'B', 10)
        pdf.multi_cell(W, 6, f"{t('h_total', lang)}: Rs {rep['total_cost']:,.0f}   "
                             f"({t('per_acre_cost', lang, x=format(rep['cost_per_acre'], ','))})",
                       new_x='LMARGIN', new_y='NEXT')
        pdf.set_font(fam, '', 8.5)
        pdf.set_text_color(90, 90, 90)
        pdf.multi_cell(W, 4.8, t('price_note', lang), new_x='LMARGIN', new_y='NEXT')
        pdf.set_text_color(25, 25, 25)
        how = [f"- {r['fert']}: {r['how']}" + (f" ({r['notes']})" if r['notes'] else '') for r in rep['plan_rows']]
        pdf.ln(1)
        pdf.set_font(fam, '', 9)
        for line in how:
            pdf.multi_cell(W, 5, line, new_x='LMARGIN', new_y='NEXT')
    else:
        para(t('nothing_needed', lang))

    if rep['skip']:
        h2(t('rep_skip', lang))
        for p in rep['skip']:
            para('- ' + t('skip_line', lang, p=p), 10)

    if rep['risk']:
        h2(t('rep_risk', lang))
        para(rep['risk'])

    h2(t('rep_tips', lang))
    for tip in rep['tips']:
        para('- ' + tip, 10)

    pdf.ln(4)
    pdf.set_font(fam, '', 8.5)
    pdf.set_text_color(90, 90, 90)
    pdf.multi_cell(W, 4.8, rep['disclaimer'], new_x='LMARGIN', new_y='NEXT')
    return bytes(pdf.output())
