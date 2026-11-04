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

# 同一人 Master List 多種寫法 → 報價尾碼／staff code（勿用英文首字母 ps）
PERSON_IDENTITY_BY_CODE = {
    'pi': {
        'en': ('Mr. Pi', 'Pi Lap Sun'),
        'zh': ('皮立新',),
        'display': '皮立新',
    },
}


def _normalize_identity_label(s):
    return re.sub(r'\s+', ' ', (s or '').strip().lower())


def person_identity_code(label):
    """任一項目負責人顯示名 → 慣用縮寫 code，無則 None。"""
    raw = (label or '').strip()
    if not raw:
        return None
    key = _normalize_identity_label(raw)
    for code, meta in PERSON_IDENTITY_BY_CODE.items():
        for en in meta.get('en', ()):
            if _normalize_identity_label(en) == key:
                return code
        for zh in meta.get('zh', ()):
            if (zh or '').strip() == raw or _normalize_identity_label(zh) == key:
                return code
    for code, full in PERSON_CODE_NAMES.items():
        if _normalize_identity_label(full) == key:
            return code
    return None


def person_identity_labels(code):
    """同一 identity 在 DB 可能出現的 person_in_charge 字串（去重、保留大小寫）。"""
    code = normalize_person_code(code)
    if not code:
        return []
    meta = PERSON_IDENTITY_BY_CODE.get(code)
    if not meta:
        full = PERSON_CODE_NAMES.get(code)
        return [full] if full else []
    seen = set()
    out = []
    for bucket in ('display', 'en', 'zh'):
        val = meta.get(bucket)
        if isinstance(val, str) and val.strip():
            items = (val,)
        elif isinstance(val, (list, tuple)):
            items = val
        else:
            continue
        for item in items:
            s = (item or '').strip()
            if not s:
                continue
            lk = s.lower()
            if lk in seen:
                continue
            seen.add(lk)
            out.append(s)
    fallback = PERSON_CODE_NAMES.get(code)
    if fallback and fallback.strip().lower() not in seen:
        out.append(fallback.strip())
    return out


def person_identity_pic_key(label):
    """主檔統計分組鍵（合併同一人的不同拼寫）。"""
    code = person_identity_code(label)
    if code:
        return f'identity:{code}'
    return _normalize_identity_label(label)


def person_identity_display_name(code):
    meta = PERSON_IDENTITY_BY_CODE.get(code) or {}
    disp = (meta.get('display') or '').strip()
    if disp:
        return disp
    return PERSON_CODE_NAMES.get(code, code)

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


def _name_matches_canonical(full_name, name_en, name_zh):
    full = (full_name or '').strip().lower()
    if not full:
        return False
    for candidate in (name_en, name_zh):
        c = (candidate or '').strip().lower()
        if c and c == full:
            return True
    return False


def canonical_quotation_suffix(name_en=None, name_zh=None):
    """
    報價編號尾碼慣例（MS/Q001/26/dc 的 dc）。
    優先 PERSON_IDENTITY／PERSON_CODE_NAMES；否則英文雙名取首字母（Dennis Chan→dc）。
    """
    en = (name_en or '').strip()
    zh = (name_zh or '').strip()
    for candidate in (en, zh):
        code = person_identity_code(candidate)
        if code:
            return code
    for code, full in PERSON_CODE_NAMES.items():
        if _name_matches_canonical(full, en, zh):
            return code.lower()
    if en and ' ' in en:
        parts = [p for p in en.split() if p]
        if len(parts) >= 2:
            a, b = parts[0][:1], parts[-1][:1]
            if a.isalpha() and b.isalpha():
                return (a + b).lower()
    return None
