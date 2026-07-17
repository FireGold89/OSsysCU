"""
master_ref.py — Master List 編號與項目負責人

報價編號格式：MS/Q1241/24/kp
  - /24 = 年份
  - /kp = 編號尾碼（Excel E 欄，編號慣例；≠ 現時跟進的項目負責人）

項目負責人全名以 Master List「項目負責人」欄為準，可由不同同事跟進同一報價。
"""
import re

# 離線後備（舊資料顯示用，不作 Staff 對照）
PERSON_CODE_NAMES = {
    'jy': 'Joe Yu',
    'dc': 'Dennis Chan',
    'jc': 'Joseph Chung',
    'jw': 'Joson Wong',
    'pi': 'Mr. Pi',
    'ny': 'Neelson Yeung',
    'kp': 'Katie Puk',
    'kl': 'Kelvin Li',
}

_name_map_cache = None


def _staff_name_map():
    global _name_map_cache
    if _name_map_cache is not None:
        return _name_map_cache
    try:
        import database as db
        _name_map_cache = db.get_staff_name_map()
    except Exception:
        _name_map_cache = {}
    return _name_map_cache


def invalidate_staff_name_cache():
    global _name_map_cache
    _name_map_cache = None


def normalize_person_code(val):
    """Excel E 欄 /kp 或 kp → kp（僅存檔，不對應 Staff 縮寫）"""
    if val is None:
        return None
    s = str(val).strip().lstrip('/').lower()
    if not s or not re.match(r'^[a-z]{2,4}$', s):
        return None
    return s


def extract_person_code_from_quotation_no(quotation_no):
    """MS/Q001/26/jy → jy（僅解析編號尾碼，不用於推斷項目負責人）"""
    if not quotation_no:
        return None
    parts = str(quotation_no).strip('/').split('/')
    if len(parts) < 2:
        return None
    last = parts[-1].lower()
    if re.match(r'^\d{2}$', last):
        return None
    return normalize_person_code(last)


def person_display_name(code, fallback=None):
    """舊資料／篩選顯示用；優先 fallback（person_in_charge）"""
    if fallback and str(fallback).strip():
        return str(fallback).strip()
    code = normalize_person_code(code)
    if not code:
        return fallback or '—'
    name = _staff_name_map().get(code)
    if name:
        return name
    return PERSON_CODE_NAMES.get(code, fallback or code.upper())


def enrich_person_fields(rec):
    """以 person_in_charge 為主；person_code 僅保留 Excel 明示的編號尾碼"""
    rec['person_code'] = normalize_person_code(rec.get('person_code'))
    return rec
