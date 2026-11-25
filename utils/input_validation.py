"""Validate farmer input before any analysis runs. Returns localised error messages."""
from utils import i18n

# Hard limits: a value outside these cannot come from a real soil test.
LIMITS = {'pH': (3.0, 10.0), 'Nitrogen': (0, 1000), 'Phosphorus': (0, 500), 'Potassium': (0, 1500),
          'OrganicCarbon': (0, 10), 'Sulphur': (0, 500), 'Zinc': (0, 50), 'Iron': (0, 500),
          'Copper': (0, 50), 'Manganese': (0, 500), 'Boron': (0, 20), 'EC': (0, 40)}


def validate_inputs(farmer: str, village: str, district: str, area: float, soil: dict, lang='English') -> list:
    errors = []
    if not (farmer or '').strip():
        errors.append(i18n.t('v_name', lang))
    if not (village or '').strip():
        errors.append(i18n.t('v_village', lang))
    if not (district or '').strip() or district.strip() == '-':
        errors.append(i18n.t('v_district', lang))
    if not area or area <= 0:
        errors.append(i18n.t('v_area', lang))
    if all((v or 0) == 0 for v in soil.values()):
        errors.append(i18n.t('v_zero', lang))
        return errors
    for p, (lo, hi) in LIMITS.items():
        v = soil.get(p)
        if v is None:
            continue
        if p == 'pH':
            if not (lo <= v <= hi):
                errors.append(i18n.t('v_ph', lang, v=v, lo=lo, hi=hi))
        elif v < 0 or v > hi:
            errors.append(i18n.t('v_range', lang, p=i18n.t(f'n_{p}', lang), v=v))
    return errors
