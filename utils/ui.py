"""
SoilSense look and feel: a farm, not a dashboard template.
Palette: soil brown, furrow brown, leaf green, straw and cream. Flat colour, 4 to 6 px corners, no gradients,
no animation, no emoji. The artwork is hand-built SVG (field, sprouts, wheat), not photos.
All text colours pass WCAG AA on their backgrounds.
"""
import base64
import os
from html import escape

import streamlit as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAVICON = os.path.join(ROOT, 'assets', 'favicon.png')

# palette
INK, SOIL, FURROW, CLAY = '#2b2118', '#3e2c20', '#5b3d2a', '#a9744f'
LEAF_D, LEAF, SPROUT = '#2d5a27', '#4f8a3a', '#8bb85a'
STRAW, WHEAT, CREAM, PAPER, LINE = '#efe6c8', '#d9b95b', '#fbf7ea', '#fffdf4', '#d8cba6'
MUTED = '#5a4a3a'
GREEN = LEAF_D
STATUS = {'Very Low': ('#9b1c1c', '#fdecec'), 'Low': ('#92400e', '#fff0d9'), 'Optimal': ('#1f5f2a', '#e6f3e2'),
          'High': ('#1e40af', '#e8f0fe'), 'Excessive': ('#7c2d12', '#fbe9e2')}


# ───────────────────────── artwork (SVG) ─────────────────────────
def _field_svg(w=1200, h=230):
    vx, vy = 600, 150
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMax slice">',
           f'<rect width="{w}" height="{h}" fill="#e6f0dc"/>',
           '<circle cx="1010" cy="62" r="52" fill="#f2c14e" opacity=".28"/><circle cx="1010" cy="62" r="34" fill="#f2c14e"/>',
           '<g fill="#ffffff" opacity=".85"><ellipse cx="260" cy="58" rx="58" ry="14"/><ellipse cx="300" cy="46" rx="36" ry="13"/>'
           '<ellipse cx="760" cy="82" rx="50" ry="11"/><ellipse cx="790" cy="72" rx="30" ry="10"/></g>',
           f'<path d="M0 148 C 150 96 280 96 420 130 S 700 140 860 118 S 1080 104 {w} 132 V {h} H0Z" fill="#bcd6a0"/>',
           f'<path d="M0 160 C 160 126 300 124 460 148 S 780 152 940 140 S 1100 136 {w} 150 V {h} H0Z" fill="#93bb73"/>']
    out.append('<g>' + ''.join(f'<circle cx="{x}" cy="{vy - 4 + (i % 3) * 2}" r="{9 + (i * 7) % 6}" fill="#3f6b34"/>'
                               for i, x in enumerate(range(20, w, 38))) + '</g>')
    out.append(f'<rect x="0" y="{vy}" width="{w}" height="{h - vy}" fill="#5b3d2a"/>')
    n = 26
    xs = [-w * 0.9 + i * (w * 2.8 / n) for i in range(n + 1)]
    for i in range(n):
        out.append(f'<polygon points="{vx},{vy} {xs[i]:.0f},{h} {xs[i + 1]:.0f},{h}" '
                   f'fill="{"#6c4731" if i % 2 == 0 else "#4f3524"}"/>')
    pl = []
    for i in range(0, n, 2):
        xm = (xs[i] + xs[i + 1]) / 2
        for k in range(1, 9):
            f = (k / 8) ** 1.6
            px, py, sz = vx + (xm - vx) * f, vy + (h - vy) * f, 2 + 9 * f
            if -20 < px < w + 20 and py < h + 4:
                pl.append(f'<path d="M{px:.1f} {py:.1f} q{-sz * .9:.1f} {-sz * 1.1:.1f} {-sz * 1.5:.1f} {-sz * .4:.1f} '
                          f'M{px:.1f} {py:.1f} q{sz * .9:.1f} {-sz * 1.1:.1f} {sz * 1.5:.1f} {-sz * .4:.1f}" '
                          f'stroke="#6aa84f" stroke-width="{max(1, sz * .28):.1f}" fill="none" stroke-linecap="round"/>')
    out.append('<g>' + ''.join(pl) + '</g></svg>')
    return ''.join(out)


SPROUT_TILE = ('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="28" viewBox="0 0 64 28">'
               '<rect y="23" width="64" height="5" fill="#6b4a35"/><path d="M14 23V12" stroke="#3f7a32" stroke-width="2" fill="none"/>'
               '<path d="M14 15q-9-1-9-9q9 0 9 9Z" fill="#5a9b43"/><path d="M14 12q9-1 9-9q-9 0-9 9Z" fill="#7bb85a"/>'
               '<path d="M44 23V15" stroke="#3f7a32" stroke-width="2" fill="none"/>'
               '<path d="M44 18q-6-1-6-6q6 0 6 6Z" fill="#5a9b43"/><path d="M44 15q6-1 6-6q-6 0-6 6Z" fill="#7bb85a"/></svg>')

LOGO = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="40" height="40"><rect width="48" height="48" rx="8" fill="#2d5a27"/>'
        '<path d="M14 36C14 20 24 12 36 12C36 26 28 36 14 36Z" fill="#fbf7ea"/><path d="M15 35L31 17" stroke="#2d5a27" stroke-width="2"/></svg>')

ICONS = {   # growth stages: seed, sprout, wheat ear
    'seed': '<svg viewBox="0 0 24 24" width="22" height="22"><path d="M2 20h20" stroke="#6b4a35" stroke-width="3"/>'
            '<ellipse cx="12" cy="14" rx="4" ry="5" fill="#a9744f" stroke="#5b3d2a"/></svg>',
    'sprout': '<svg viewBox="0 0 24 24" width="22" height="22"><path d="M2 21h20" stroke="#6b4a35" stroke-width="3"/>'
              '<path d="M12 21V10" stroke="#3f7a32" stroke-width="2"/><path d="M12 14q-8 0-8-7q8 0 8 7Z" fill="#5a9b43"/>'
              '<path d="M12 11q7 0 7-6q-7 0-7 6Z" fill="#8bb85a"/></svg>',
    'wheat': '<svg viewBox="0 0 24 24" width="22" height="22"><path d="M12 22V6" stroke="#8a6d1f" stroke-width="2"/>'
             '<g fill="#d9b95b" stroke="#8a6d1f" stroke-width=".6"><ellipse cx="9.5" cy="9" rx="2" ry="3.2" transform="rotate(-25 9.5 9)"/>'
             '<ellipse cx="14.5" cy="9" rx="2" ry="3.2" transform="rotate(25 14.5 9)"/>'
             '<ellipse cx="9.5" cy="14" rx="2" ry="3.2" transform="rotate(-25 9.5 14)"/>'
             '<ellipse cx="14.5" cy="14" rx="2" ry="3.2" transform="rotate(25 14.5 14)"/><ellipse cx="12" cy="4.5" rx="1.8" ry="3"/></g></svg>',
}


def _uri(svg):
    return 'data:image/svg+xml;base64,' + base64.b64encode(svg.encode()).decode()


SERIF = "Georgia, 'Noto Serif', 'Noto Serif Kannada', 'Noto Serif Devanagari', 'Times New Roman', serif"

CSS = f"""
<style>
html, body, [class*="css"], .stApp {{ font-size: 16px; color: {INK}; }}
.stApp {{ background: {CREAM}; }}
#MainMenu, footer {{ visibility: hidden; height: 0; }}
[data-testid="stHeader"] {{ background: {CREAM}; border-bottom: 1px solid {LINE}; }}
.block-container {{ max-width: 1180px; padding-top: 1rem; padding-bottom: 2rem; }}
[data-testid="stSidebar"] {{ background: {STRAW}; border-right: 2px solid {LINE}; }}
h1, h2, h3, h4 {{ font-family: {SERIF}; color: {LEAF_D}; letter-spacing: 0; }}
h3 {{ font-size: 1.2rem !important; margin-top: 1.1rem; padding-bottom: .25rem; border-bottom: 2px solid {LINE}; }}
label p {{ font-size: .95rem !important; font-weight: 600; color: {INK}; }}
.stTextInput input, .stNumberInput input, [data-baseweb="select"] > div, textarea {{
  background: {PAPER} !important; border-color: #bfae85 !important; }}
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {{
  border-radius: 4px; font-weight: 600; border: 1.5px solid {LEAF_D}; background: {PAPER}; color: {LEAF_D};
  box-shadow: none; transition: none; }}
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {{
  background: {LEAF_D}; color: #fff8e1; border-color: {LEAF_D}; }}
.stButton > button:hover, .stDownloadButton > button:hover {{ transform: none; box-shadow: none; border-color: {SOIL}; }}
.stTabs [data-baseweb="tab-list"] {{ border-bottom: 2px solid {LINE}; gap: .2rem; }}
.stTabs [data-baseweb="tab"] {{ font-weight: 600; padding: .6rem .9rem; color: {MUTED}; }}
.stTabs [aria-selected="true"] {{ color: {LEAF_D}; }}
.stTabs [data-baseweb="tab-highlight"] {{ background-color: {LEAF_D}; height: 3px; }}
[data-testid="stExpander"] {{ background: {PAPER}; border: 1px solid {LINE}; border-radius: 6px; }}
[data-testid="stAlert"] {{ border-radius: 4px; }}

/* masthead: text on paper, field art below */
.mast {{ border: 1px solid {LINE}; border-radius: 6px; overflow: hidden; background: {PAPER}; margin-bottom: 1rem; }}
.mast-text {{ display: flex; gap: .9rem; align-items: center; padding: .9rem 1.2rem .6rem; background: {PAPER}; }}
.mast-text .t {{ font-family: {SERIF}; font-size: 1.75rem; font-weight: 700; color: {LEAF_D}; line-height: 1.15; }}
.mast-text .s {{ color: {MUTED}; font-size: 1rem; margin-top: .15rem; }}
.mast-art {{ height: 112px; background: url({_uri(_field_svg())}) center bottom / cover no-repeat; border-top: 1px solid {LINE}; }}
.mast.compact .mast-art {{ height: 64px; }}
.mast.compact .mast-text .t {{ font-size: 1.4rem; }}
.divider {{ height: 28px; margin: .8rem 0 .4rem; background: url({_uri(SPROUT_TILE)}) repeat-x left bottom; }}

.steps {{ display: flex; gap: .5rem; margin: 0 0 1rem; }}
.step {{ flex: 1; display: flex; align-items: center; gap: .5rem; border: 1px solid {LINE}; border-radius: 6px;
  padding: .45rem .8rem; color: {MUTED}; font-size: .92rem; background: {PAPER}; }}
.step.on {{ border: 2px solid {LEAF_D}; background: #eef5e4; color: {LEAF_D}; font-weight: 700; }}

.kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: .7rem; margin: .6rem 0 1rem; }}
.kpi {{ border: 1px solid {LINE}; border-left: 6px solid {CLAY}; border-radius: 4px 6px 6px 4px; padding: .65rem .9rem; background: {PAPER}; }}
.kpi .l {{ font-size: .8rem; color: {MUTED}; font-weight: 700; }}
.kpi .v {{ font-family: {SERIF}; font-size: 1.7rem; font-weight: 700; line-height: 1.25; }}
.kpi .s {{ font-size: .85rem; color: {MUTED}; }}
.box {{ border: 1px solid {LINE}; border-left: 6px solid {LEAF_D}; background: #f1f6e8; padding: .8rem 1.2rem; border-radius: 4px 6px 6px 4px; margin: .6rem 0 1rem; }}
.box ol {{ margin: .3rem 0 0 1.2rem; padding: 0; }}
.panel {{ border: 1px solid {LINE}; border-radius: 6px; padding: .9rem 1.1rem; background: {STRAW}; }}
.panel ul {{ margin: .4rem 0 0 1.1rem; padding: 0; }}
.panel li {{ margin: .3rem 0; }}
.note {{ color: {MUTED}; font-size: .9rem; }}
.wrap {{ overflow-x: auto; margin: .4rem 0 1rem; border: 1px solid {LINE}; border-radius: 6px; }}
table.tbl {{ width: 100%; border-collapse: collapse; font-size: .95rem; background: {PAPER}; }}
table.tbl th {{ background: {FURROW}; color: #fff8e1; text-align: left; padding: .55rem .7rem; font-weight: 600; }}
table.tbl td {{ border-bottom: 1px solid {LINE}; padding: .5rem .7rem; vertical-align: top; }}
table.tbl tr:nth-child(even) td {{ background: #faf5e3; }}
.chip {{ display: inline-block; padding: .05rem .45rem; border-radius: 3px; font-weight: 700; border: 1px solid currentColor; }}
.crop {{ border: 1px solid {LINE}; border-left: 6px solid {LEAF}; padding: .7rem 1rem; margin: .5rem 0; border-radius: 4px 6px 6px 4px; background: {PAPER}; }}
.crop b {{ font-family: {SERIF}; font-size: 1.15rem; }}
.bar {{ height: 8px; background: #e7dfc3; border-radius: 2px; margin-top: .4rem; }}
.bar > div {{ height: 8px; background: {LEAF}; border-radius: 2px; }}
.brand {{ display: flex; align-items: center; gap: .6rem; margin-bottom: .4rem; }}
.brand .n {{ font-family: {SERIF}; font-size: 1.3rem; font-weight: 700; color: {LEAF_D}; }}
@media (max-width: 760px) {{ .steps {{ flex-direction: column; }} .mast-text .t {{ font-size: 1.35rem; }} .mast-art {{ height: 80px; }} }}
</style>
"""


def page_setup():
    st.markdown(CSS, unsafe_allow_html=True)


def hero(title, sub='', compact=False):
    st.markdown(f'<div class="mast{" compact" if compact else ""}"><div class="mast-text">{LOGO}<div>'
                f'<div class="t">{escape(title)}</div><div class="s">{escape(sub)}</div></div></div>'
                f'<div class="mast-art"></div></div>', unsafe_allow_html=True)


def brand():
    return f'<div class="brand">{LOGO}<div class="n">SoilSense</div></div>'


def divider():
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)


def steps(labels, active):
    icons = ['seed', 'sprout', 'wheat']
    items = ''.join(f'<div class="step{" on" if i == active else ""}">{ICONS[icons[i % 3]]}<span>{i + 1}. {escape(l)}</span></div>'
                    for i, l in enumerate(labels))
    st.markdown(f'<div class="steps">{items}</div>', unsafe_allow_html=True)


def kpis(items):
    """items: list of (label, value, sub, colour)."""
    cells = ''.join(f'<div class="kpi"><div class="l">{escape(str(l))}</div>'
                    f'<div class="v" style="color:{c}">{escape(str(v))}</div><div class="s">{escape(str(s))}</div></div>'
                    for l, v, s, c in items)
    st.markdown(f'<div class="kpis">{cells}</div>', unsafe_allow_html=True)


def html_table(headers, rows, status_col=None, status_keys=None):
    th = ''.join(f'<th>{escape(str(h))}</th>' for h in headers)
    body = ''
    for i, r in enumerate(rows):
        tds = ''
        for j, c in enumerate(r):
            if status_col is not None and j == status_col and status_keys:
                fg, bg = STATUS.get(status_keys[i], (INK, '#fff'))
                tds += f'<td><span class="chip" style="color:{fg};background:{bg}">{escape(str(c))}</span></td>'
            else:
                tds += f'<td>{escape(str(c))}</td>'
        body += f'<tr>{tds}</tr>'
    st.markdown(f'<div class="wrap"><table class="tbl"><tr>{th}</tr>{body}</table></div>', unsafe_allow_html=True)


def show_df(df, **kw):
    st.dataframe(df, width='stretch', hide_index=True, height=min(36 * (len(df) + 1) + 4, 1400), **kw)


def contact_line():
    mail = os.environ.get('CONTACT_EMAIL', '').strip()
    try:
        mail = mail or str(st.secrets.get('CONTACT_EMAIL', '')).strip()
    except Exception:
        pass
    return f'Contact: {mail}' if mail else 'Contact: open an issue in the project repository.'
