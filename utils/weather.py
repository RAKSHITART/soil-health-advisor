"""
Live weather + 7-day forecast using Open-Meteo (free, no API key).
Falls back to clearly-labelled demo data if offline.
Also finds the best fertiliser-application windows (dry days).
"""
import hashlib
import json
import random
import urllib.parse
import urllib.request

WMO = {0: 'Clear sky', 1: 'Mainly clear', 2: 'Partly cloudy', 3: 'Overcast',
       45: 'Fog', 48: 'Fog', 51: 'Light drizzle', 53: 'Drizzle', 55: 'Heavy drizzle',
       61: 'Light rain', 63: 'Rain', 65: 'Heavy rain', 71: 'Light snow', 73: 'Snow',
       80: 'Rain showers', 81: 'Rain showers', 82: 'Violent showers',
       95: 'Thunderstorm', 96: 'Thunderstorm', 99: 'Thunderstorm'}


def _ssl_context():
    """Use certifi's certificate list. Python on Windows often fails with CERTIFICATE_VERIFY_FAILED otherwise."""
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _get(url, timeout=12):
    req = urllib.request.Request(url, headers={'User-Agent': 'SoilSense/1.0'})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as r:
        return json.loads(r.read().decode('utf-8'))


def _geocode(district, state):
    q = urllib.parse.urlencode({'name': district, 'count': 10, 'language': 'en', 'format': 'json'})
    data = _get(f'https://geocoding-api.open-meteo.com/v1/search?{q}')
    results = [r for r in data.get('results', []) if r.get('country_code') == 'IN']
    if not results:
        return None
    for r in results:
        if state and state.lower() in (r.get('admin1') or '').lower():
            return r
    return results[0]


def parse_forecast(data: dict, place: str) -> dict:
    cur = data.get('current', {})
    daily = data.get('daily', {})
    days = []
    for i, d in enumerate(daily.get('time', [])):
        days.append({
            'date': d,
            'tmax': daily['temperature_2m_max'][i],
            'tmin': daily['temperature_2m_min'][i],
            'rain_mm': daily['precipitation_sum'][i] or 0.0,
            'rain_prob': (daily.get('precipitation_probability_max') or [None] * 99)[i] or 0,
        })
    return {
        'temperature': cur.get('temperature_2m'),
        'humidity': cur.get('relative_humidity_2m'),
        'description': WMO.get(cur.get('weather_code'), 'N/A'),
        'rainfall_mm': cur.get('precipitation', 0) or 0,
        'forecast': days,
        'place': place,
        'source': 'Open-Meteo (live)',
        'mock': False,
    }


def get_weather(district: str, state: str, village: str = '') -> dict:
    """Live forecast from Open-Meteo. On failure returns clearly labelled sample data plus the reason in 'error'."""
    err = None
    try:
        geo = None
        for q in (district, f'{district} {state}', village):
            q = (q or '').strip()
            if not q or q == '-':
                continue
            geo = _geocode(q, state)
            if geo:
                break
        if geo:
            q = urllib.parse.urlencode({
                'latitude': geo['latitude'], 'longitude': geo['longitude'],
                'current': 'temperature_2m,relative_humidity_2m,precipitation,weather_code',
                'daily': 'temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max',
                'timezone': 'auto', 'forecast_days': 7,
            })
            data = _get(f'https://api.open-meteo.com/v1/forecast?{q}')
            out = parse_forecast(data, f"{geo.get('name')}, {geo.get('admin1', '')}")
            out['error'] = None
            return out
        err = f'Place "{district}" was not found. Try a nearby town name in the district field.'
    except Exception as e:  # network, certificate, timeout, bad response
        err = f'{type(e).__name__}: {str(e)[:160]}'
    m = _mock(district)
    m['error'] = err
    return m


def _mock(district: str) -> dict:
    rng = random.Random(int(hashlib.md5(district.encode()).hexdigest(), 16) % 1000)
    days = [{'date': f'Day {i + 1}', 'tmax': round(rng.uniform(28, 36), 1),
             'tmin': round(rng.uniform(18, 24), 1), 'rain_mm': round(rng.choice([0, 0, 0, 2, 8]), 1),
             'rain_prob': rng.choice([10, 20, 30, 60])} for i in range(7)]
    return {'temperature': round(rng.uniform(24, 34), 1), 'humidity': rng.randint(45, 80),
            'description': 'Demo data', 'rainfall_mm': 0.0, 'forecast': days,
            'place': district, 'source': 'Demo data (offline: live weather unavailable)', 'mock': True}


def best_application_days(weather: dict) -> list:
    """Dry days (<2 mm and <40% rain chance, not scorching) are good for fertiliser."""
    good = []
    for d in weather.get('forecast', []):
        if d['rain_mm'] < 2 and d['rain_prob'] < 40 and d['tmax'] < 37:
            good.append(d['date'])
    return good


def advice_codes(weather: dict, fert_rows: list) -> list:
    """Language-neutral weather advice: list of (i18n code, kwargs)."""
    fc = weather.get('forecast', [])
    temp = weather.get('temperature') or 28
    next3 = sum(d['rain_mm'] for d in fc[:3])
    has_urea = any(r.get('Fertilizer') == 'Urea' for r in fert_rows)
    out = []
    if next3 > 15:
        out.append(('wx_heavy', {}))
    if temp > 35:
        out.append(('wx_hot', {}))
    if has_urea:
        out.append(('wx_urea', {}))
    days = best_application_days(weather)
    out.append(('wx_best', {'days': ', '.join(days[:4])}) if days else ('wx_nodry', {}))
    return out


# kept for English-only callers and tests
def get_weather_advice(weather: dict, fert_recs: list) -> str:
    from utils import i18n
    return '\n\n'.join(i18n.en(c, **kw) for c, kw in advice_codes(weather, fert_recs))
