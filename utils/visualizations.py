"""
Plotly charts for SoilSense. Every chart takes `lang` so titles, nutrient names and status
words match the language the farmer chose. Flat colours, no decoration.
"""
import plotly.graph_objects as go

from utils.i18n import t
from utils.soil_analyzer import FAO_STANDARDS

FONT = 'Segoe UI, Noto Sans, Noto Sans Kannada, Noto Sans Devanagari, sans-serif'
SERIF = 'Georgia, Noto Serif, Noto Serif Kannada, Noto Serif Devanagari, serif'
INK, GREEN = '#2b2118', '#2d5a27'
CAT_COLORS = {'Excellent': '#1e40af', 'Good': '#166534', 'Fair': '#92400e', 'Poor': '#b45309', 'Critical': '#9b1c1c'}
STATUS_COLORS = {'Very Low': '#9b1c1c', 'Low': '#b45309', 'Optimal': '#1f5f2a', 'High': '#1e40af', 'Excessive': '#7c2d12'}


def _base(fig, title, height, **kw):
    fig.update_layout(title=dict(text=title, font=dict(size=17, color=GREEN, family=SERIF)), height=height,
                      paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                      font=dict(family=FONT, color=INK, size=13), margin=dict(t=55, b=40, l=40, r=20), **kw)
    return fig


def _names(analysis, lang):
    return [t(f'n_{p}', lang) for p in analysis['parameters']]


def _pct_of_ideal(p, value):
    s = FAO_STANDARDS.get(p)
    if not s:
        return 100.0
    mid = (s['opt_min'] + s['opt_max']) / 2
    return max(0.0, min(250.0, value / mid * 100)) if mid else 0.0


def gauge_chart(score, category, lang='English'):
    col = CAT_COLORS.get(category, GREEN)
    fig = go.Figure(go.Indicator(
        mode='gauge+number', value=score,
        title={'text': f"{t('ch_gauge', lang)}<br><span style='color:{col}'>{t(f'cat_{category}', lang)}</span>",
               'font': {'size': 16}},
        number={'font': {'size': 46, 'color': col}},
        gauge={'axis': {'range': [0, 100]}, 'bar': {'color': col, 'thickness': 0.3}, 'bgcolor': 'white',
               'borderwidth': 1, 'bordercolor': '#c9d3c4',
               'steps': [{'range': [0, 30], 'color': '#fdecec'}, {'range': [30, 50], 'color': '#fff3e0'},
                         {'range': [50, 70], 'color': '#fffbe6'}, {'range': [70, 85], 'color': '#e8f5e9'},
                         {'range': [85, 100], 'color': '#e8f0fe'}]}))
    fig.update_layout(height=290, margin=dict(t=70, b=10, l=20, r=20), paper_bgcolor='rgba(0,0,0,0)',
                      font=dict(family=FONT, color=INK))
    return fig


def radar_chart(soil_data, analysis, lang='English'):
    params = [p for p in analysis['parameters'] if p in FAO_STANDARDS and p != 'EC']
    names = [t(f'n_{p}', lang) for p in params]
    yours = [_pct_of_ideal(p, analysis['parameters'][p]['value']) for p in params]
    lo = [FAO_STANDARDS[p]['opt_min'] / ((FAO_STANDARDS[p]['opt_min'] + FAO_STANDARDS[p]['opt_max']) / 2) * 100 for p in params]
    hi = [FAO_STANDARDS[p]['opt_max'] / ((FAO_STANDARDS[p]['opt_min'] + FAO_STANDARDS[p]['opt_max']) / 2) * 100 for p in params]
    close = lambda a: a + [a[0]]
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=close(hi), theta=close(names), line=dict(color='#166534', dash='dot', width=1),
                                  fill=None, name='max', showlegend=False))
    fig.add_trace(go.Scatterpolar(r=close(lo), theta=close(names), fill='tonext', fillcolor='rgba(22,101,52,0.15)',
                                  line=dict(color='#166534', dash='dot', width=1), name=t('st_Optimal', lang)))
    fig.add_trace(go.Scatterpolar(r=close(yours), theta=close(names), fill='toself', fillcolor='rgba(30,64,175,0.18)',
                                  line=dict(color='#1e40af', width=2), name=t('rep_soil', lang)))
    fig = _base(fig, t('ch_radar', lang), 420)
    fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 250], ticksuffix='%')),
                      legend=dict(orientation='h', y=-0.1))
    return fig


def status_bar_chart(analysis, lang='English'):
    ps = list(analysis['parameters'])
    stat = [analysis['parameters'][p]['status'] for p in ps]
    vals = [_pct_of_ideal(p, analysis['parameters'][p]['value']) for p in ps]
    fig = go.Figure(go.Bar(x=_names(analysis, lang), y=vals, marker_color=[STATUS_COLORS[s] for s in stat],
                           text=[t(f'st_{s}', lang) for s in stat], textposition='outside',
                           customdata=[f"{analysis['parameters'][p]['value']:g} {analysis['parameters'][p]['unit']}" for p in ps],
                           hovertemplate='%{x}<br>%{customdata}<br>%{y:.0f}%<extra></extra>'))
    fig.add_hline(y=100, line_dash='dot', line_color='#166534')
    fig = _base(fig, t('ch_status', lang), 390, showlegend=False)
    fig.update_layout(yaxis=dict(title='% (100 = ideal)', range=[0, max(vals + [120]) * 1.2]), xaxis_tickangle=-30)
    return fig


def deficiency_heatmap(analysis, lang='English'):
    score = {'Very Low': 1, 'Low': 2, 'Optimal': 4, 'High': 3, 'Excessive': 1}
    ps = list(analysis['parameters'])
    stat = [analysis['parameters'][p]['status'] for p in ps]
    fig = go.Figure(go.Bar(x=_names(analysis, lang), y=[1] * len(ps), marker_color=[STATUS_COLORS[s] for s in stat],
                           text=[t(f'st_{s}', lang) for s in stat], textposition='inside',
                           textfont=dict(color='white', size=13), hovertemplate='%{x}: %{text}<extra></extra>'))
    fig = _base(fig, t('ch_heat', lang), 230, showlegend=False)
    fig.update_layout(yaxis=dict(visible=False), xaxis_tickangle=-30, bargap=0.05)
    return fig


def crop_suitability_chart(crop_recs, lang='English', target=None):
    if not crop_recs:
        return go.Figure()
    rows = list(crop_recs)[::-1]
    cols = [GREEN if r['crop'] != target else '#b45309' for r in rows]
    fig = go.Figure(go.Bar(x=[r['confidence'] for r in rows], y=[t(f"c_{r['crop']}", lang) for r in rows],
                           orientation='h', marker_color=cols, text=[f"{r['confidence']}%" for r in rows],
                           textposition='outside'))
    fig = _base(fig, t('ch_crops', lang), 320, showlegend=False)
    fig.update_layout(xaxis=dict(range=[0, 100]))
    return fig


def cost_comparison_chart(fert_result, lang='English'):
    plans = ['Budget', 'Balanced', 'Maximum Yield']
    vals = [fert_result.get('budget_cost_value', 0), fert_result.get('balanced_cost_value', 0),
            fert_result.get('maximal_cost_value', 0)]
    fig = go.Figure(go.Bar(x=[t(f'plan_{p}', lang) for p in plans], y=vals,
                           marker_color=['#166534', '#1e40af', '#b45309'],
                           text=[f'Rs {v:,.0f}' for v in vals], textposition='outside'))
    fig = _base(fig, t('ch_plans', lang), 330, showlegend=False)
    fig.update_layout(yaxis=dict(range=[0, max(vals + [1]) * 1.2]))
    return fig


def value_chart(rows, lang='English'):
    colors = {'Budget': '#166534', 'Balanced': '#1e40af', 'Maximum Yield': '#b45309'}
    fig = go.Figure()
    for r in rows:
        fig.add_trace(go.Scatter(x=[r['cost']], y=[r['score_after']], mode='markers+text',
                                 text=[t(f"plan_{r['plan']}", lang)], textposition='top center',
                                 marker=dict(size=20, color=colors.get(r['plan'], GREEN)), showlegend=False))
    fig = _base(fig, t('ch_value', lang), 330)
    fig.update_layout(xaxis_title='Rs', yaxis=dict(title=t('kpi_score', lang), range=[0, 110]))
    return fig


def before_after_chart(before, after, lang='English'):
    names = _names(before, lang)
    b = [before['parameters'][p]['score'] * 10 for p in before['parameters']]
    a = [after['parameters'][p]['score'] * 10 for p in before['parameters']]
    fig = go.Figure()
    fig.add_bar(x=names, y=b, name=t('wx_now', lang), marker_color='#b45309')
    fig.add_bar(x=names, y=a, name=t('tab_fert', lang), marker_color='#166534')
    fig = _base(fig, t('ch_after', lang), 360, barmode='group')
    fig.update_layout(xaxis_tickangle=-30, legend=dict(orientation='h', y=1.12), yaxis=dict(range=[0, 110]))
    return fig


def importance_chart(importance, lang='English'):
    imp = importance[:8][::-1]
    fig = go.Figure(go.Bar(x=[v for _, v in imp], y=[t(f'n_{f}', lang) for f, _ in imp], orientation='h',
                           marker_color=GREEN))
    return _base(fig, 'Feature importance', 320, showlegend=False)


def forecast_chart(forecast, lang='English'):
    dates = [d['date'][-5:] if '-' in d['date'] else d['date'] for d in forecast]
    fig = go.Figure()
    fig.add_bar(x=dates, y=[d['rain_mm'] for d in forecast], name=t('wx_rain', lang) + ' (mm)', marker_color='#1e40af',
                yaxis='y2', opacity=0.5)
    fig.add_trace(go.Scatter(x=dates, y=[d['tmax'] for d in forecast], name='Max C', line=dict(color='#b45309')))
    fig.add_trace(go.Scatter(x=dates, y=[d['tmin'] for d in forecast], name='Min C', line=dict(color='#166534')))
    fig = _base(fig, t('ch_forecast', lang), 330)
    fig.update_layout(yaxis=dict(title='C'), yaxis2=dict(title='mm', overlaying='y', side='right'),
                      legend=dict(orientation='h', y=1.12))
    return fig


def cost_by_fertiliser_chart(items, lang='English'):
    items = sorted(items, key=lambda x: x[1])
    fig = go.Figure(go.Bar(x=[v for _, v in items], y=[k for k, _ in items], orientation='h', marker_color=GREEN,
                           text=[f'Rs {v:,.0f}' for _, v in items], textposition='outside'))
    fig = _base(fig, t('cost_chart', lang), max(260, 46 * len(items) + 90), showlegend=False)
    fig.update_layout(margin=dict(l=10, r=70, t=55, b=30))
    return fig
