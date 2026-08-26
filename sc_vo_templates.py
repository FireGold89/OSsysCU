"""分判 VO / 扣款 / 中期糧款計算書標準行項目目錄（DB 可編輯，內建為種子）"""

from __future__ import annotations

# ── 內建種子：首次建庫寫入 sc_vo_template_catalog ────────────────────────────
VO_TEMPLATES: list[dict] = [
    {
        'code': 'vo_general',
        'record_type': 'vo',
        'ref_no': 'VO',
        'description': '後加/更改工程',
        'cert_label': None,
        'group_name': 'vo',
    },
    {
        'code': 'vo_material',
        'record_type': 'vo',
        'ref_no': 'MAT',
        'description': 'Material On Site',
        'cert_label': 'C. Material On Site',
        'group_name': 'vo',
    },
]

DEDUCTION_TEMPLATES: list[dict] = [
    {
        'code': 'ded_penalty',
        'record_type': 'deduction',
        'ref_no': 'PN',
        'description': '罰款',
        'cert_label': '減: 罰款',
        'group_name': 'deduction',
    },
    {
        'code': 'ded_contra',
        'record_type': 'deduction',
        'ref_no': 'CC',
        'description': 'Contra Charge',
        'cert_label': '減: Contra Charge',
        'group_name': 'deduction',
    },
    {
        'code': 'ded_backcharge',
        'record_type': 'deduction',
        'ref_no': 'BC',
        'description': 'Backcharge',
        'cert_label': '減: Backcharge',
        'group_name': 'deduction',
    },
    {
        'code': 'ded_advance_offset',
        'record_type': 'deduction',
        'ref_no': 'ADV',
        'description': '預付款對沖',
        'cert_label': '減: 預付款對沖',
        'group_name': 'deduction',
    },
]

CERT_STANDARD_LINES: list[dict] = [
    {
        'code': 'add_cp_fm',
        'cert_label': '加: CP & FM Service :',
        'direction': 'add',
        'group_name': 'standard',
    },
    {
        'code': 'ded_fin_charge',
        'cert_label': '減: Finance Charge on Advance Payment',
        'direction': 'ded',
        'group_name': 'standard',
    },
    {
        'code': 'ded_tax',
        'cert_label': '減: 徵稅 (0.68%)',
        'direction': 'ded',
        'group_name': 'standard',
    },
    {
        'code': 'ded_insurance',
        'cert_label': '減: 代支工程保險 (CAR+EC)',
        'direction': 'ded',
        'group_name': 'standard',
    },
    {
        'code': 'ded_waste',
        'cert_label': '減: 代支廢物傾倒費',
        'direction': 'ded',
        'group_name': 'standard',
    },
    {
        'code': 'ded_rounding',
        'cert_label': '減: Rounding ',
        'direction': 'ded',
        'group_name': 'standard',
    },
]

_RETENTION_LINE = {
    'code': 'retention',
    'cert_label': '減:保固金',
    'direction': 'ded',
    'group_name': 'system',
    'auto': True,
}

_catalog_cache: list[dict] | None = None


def invalidate_template_cache():
    global _catalog_cache
    _catalog_cache = None


def default_catalog_seed_rows() -> list[dict]:
    """database 種子用"""
    rows = []
    order = 0
    for t in VO_TEMPLATES:
        rows.append({
            **t,
            'source': 'sc_vo',
            'sort_order': order,
            'is_builtin': 1,
            'is_active': 1,
        })
        order += 1
    order = 0
    for t in DEDUCTION_TEMPLATES:
        rows.append({
            **t,
            'source': 'sc_vo',
            'sort_order': order,
            'is_builtin': 1,
            'is_active': 1,
        })
        order += 1
    order = 0
    for t in CERT_STANDARD_LINES:
        rows.append({
            **t,
            'source': 'cert_standard',
            'record_type': t['direction'],
            'description': t.get('description') or t['cert_label'],
            'sort_order': order,
            'is_builtin': 1,
            'is_active': 1,
        })
        order += 1
    rows.append({
        **_RETENTION_LINE,
        'source': 'system',
        'record_type': 'system',
        'description': _RETENTION_LINE['cert_label'],
        'sort_order': 0,
        'is_builtin': 1,
        'is_active': 1,
    })
    return rows


def _load_catalog() -> list[dict]:
    global _catalog_cache
    if _catalog_cache is not None:
        return _catalog_cache
    try:
        import database as db
        db.seed_sc_vo_template_catalog()
        _catalog_cache = db.list_sc_vo_template_catalog(active_only=False)
    except Exception:
        _catalog_cache = _fallback_catalog()
    return _catalog_cache


def _fallback_catalog() -> list[dict]:
    out = []
    for row in default_catalog_seed_rows():
        out.append(_row_to_api(row))
    return out


def _row_to_api(row: dict) -> dict:
    """DB / seed row → API 形狀（相容舊前端）"""
    source = row.get('source') or 'sc_vo'
    api = {
        'code': row['code'],
        'source': source,
        'ref_no': row.get('ref_no'),
        'description': row.get('description'),
        'cert_label': row.get('cert_label'),
        'group': row.get('group_name') or row.get('group'),
        'sort_order': row.get('sort_order') or 0,
        'is_builtin': bool(row.get('is_builtin')),
        'is_active': bool(row.get('is_active', 1)),
    }
    if source == 'cert_standard':
        api['direction'] = row.get('direction') or row.get('record_type')
        api['record_type'] = api['direction']
    elif source == 'system':
        api['record_type'] = 'system'
        api['direction'] = row.get('direction')
        api['auto'] = True
    else:
        api['record_type'] = row.get('record_type') or 'deduction'
    return api


def _active_rows() -> list[dict]:
    return [
        _row_to_api(r) for r in _load_catalog()
        if r.get('is_active', 1) and r.get('source') != 'system'
    ] + [
        _row_to_api(r) for r in _load_catalog()
        if r.get('is_active', 1) and r.get('source') == 'system'
    ]


def all_templates() -> list[dict]:
    """API 用：完整啟用目錄"""
    seen = set()
    out = []
    for row in sorted(_active_rows(), key=lambda r: (r.get('source', ''), r.get('sort_order', 0), r.get('code', ''))):
        if row['code'] in seen:
            continue
        seen.add(row['code'])
        out.append(row)
    return out


def list_all_templates(include_inactive: bool = False) -> list[dict]:
    """管理 UI：含停用"""
    rows = _load_catalog()
    if not include_inactive:
        rows = [r for r in rows if r.get('is_active', 1)]
    return sorted(
        [_row_to_api(r) for r in rows if r.get('source') != 'system'],
        key=lambda r: (r.get('source', ''), r.get('sort_order', 0), r.get('code', '')),
    )


def get_cert_standard_lines() -> list[dict]:
    return [t for t in all_templates() if t.get('source') == 'cert_standard']


def get_template(code: str | None) -> dict | None:
    if not code:
        return None
    for row in _load_catalog():
        if row.get('code') == code and row.get('is_active', 1):
            return _row_to_api(row)
    return None


def cert_label_for_record(record: dict) -> str | None:
    """sc_vo_record → 計算書行標籤"""
    code = record.get('line_code')
    if code:
        tpl = get_template(code)
        if tpl and tpl.get('cert_label'):
            return tpl['cert_label']
    rt = record.get('record_type')
    desc = (record.get('description') or record.get('ref_no') or '').strip()
    if rt == 'deduction':
        if desc.startswith('減:') or desc.startswith('加:'):
            return desc
        return f'減: {desc}' if desc else '減: 扣款'
    return None


def normalize_standard_amount(code: str, amount: float) -> float:
    """標準行金額：加項正數、減項負數"""
    tpl = get_template(code)
    if not tpl:
        return amount
    direction = tpl.get('direction')
    if direction == 'add':
        return abs(amount)
    if direction == 'ded':
        return -abs(amount) if amount else 0.0
    return amount
