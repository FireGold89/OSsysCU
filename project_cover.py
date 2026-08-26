"""
project_cover.py — Cover Page / Summary 工程項目主檔

對齊 QS 優化第一期 Excel：
  第2頁 Summary、第4頁工程項目表格、第5頁註冊及更新、第6頁 Cover Page
"""
import re

# projects 表 Cover Page 增量欄位（migration 用）
PROJECT_COVER_MIGRATIONS = [
    ('account_code', 'TEXT'),
    ('mp_contract_code', 'TEXT'),
    ('job_no', 'TEXT'),
    ('work_type', 'TEXT'),
    ('category_l1_code', 'TEXT'),
    ('category_l2_code', 'TEXT'),
    ('tender_sum', 'REAL DEFAULT 0'),
    ('anticipated_profit_pct', 'REAL'),
    ('main_contract_commencement_date', 'TEXT'),
    ('project_completion_date', 'TEXT'),
    ('pc_cert_date', 'TEXT'),
    ('mp_commencement_date', 'TEXT'),
    ('extended_completion_date', 'TEXT'),
    ('dlp_period_months', 'INTEGER'),
    ('project_manager', 'TEXT'),
    ('qs_in_charge', 'TEXT'),
    ('construction_period_days', 'INTEGER'),
    ('retention_pct', 'REAL'),
    ('retention_max_pct', 'REAL'),
    ('retention_max_amount', 'REAL'),
    ('retention_release_mode', 'TEXT'),
    ('retention_release_date', 'TEXT'),
    ('retention_release_date_first', 'TEXT'),
    ('retention_release_date_second', 'TEXT'),
    ('dlp_cert_date', 'TEXT'),
    ('mp_fac_signed_date', 'TEXT'),
    ('material_other_expenses', 'REAL'),
    ('final_subcontract_sum', 'REAL'),
    ('sc_fac_signed_date', 'TEXT'),
    ('client_secondary', 'TEXT'),
    ('supplemental_contract_amount', 'REAL DEFAULT 0'),
    ('doc_library_url', 'TEXT'),
]

PROJECT_COVER_WRITABLE = [name for name, _ in PROJECT_COVER_MIGRATIONS]

RETENTION_RELEASE_MODES = ('na', 'one_off', 'first_half', 'second_half', 'two_half', 'multi')


def retention_release_label(project):
    """依已填日期組合退還方式標籤（支援多項並存）。"""
    mode = (project.get('retention_release_mode') or 'na').lower()
    parts = []
    if project.get('retention_release_date'):
        parts.append('一次性退還保證金')
    if project.get('retention_release_date_first'):
        parts.append('退還第一期保證金')
    if project.get('retention_release_date_second'):
        parts.append('退還第二期保證金')
    if parts:
        return '、'.join(parts)
    if mode == 'one_off':
        return '一次性退還保證金'
    if mode == 'first_half':
        return '退還第一期保證金'
    if mode == 'second_half':
        return '退還第二期保證金'
    if mode == 'two_half':
        return '退還第一及第二期保證金'
    if mode == 'multi':
        return '多項退還'
    return '不適用'


def _pct_number(val):
    """0.05 → 5；5 → 5"""
    if val is None or val == '':
        return None
    try:
        v = float(val)
    except (TypeError, ValueError):
        return None
    if 0 < abs(v) <= 1:
        return v * 100
    return v


def format_retention_pct(val):
    n = _pct_number(val)
    if n is None:
        return None
    text = f'{n:.4f}'.rstrip('0').rstrip('.')
    return f'{text}%'


def _retention_release_active(project):
    mode = (project.get('retention_release_mode') or 'na').lower()
    if mode != 'na':
        return True
    return any(project.get(k) for k in (
        'retention_release_date',
        'retention_release_date_first',
        'retention_release_date_second',
    ))


def _retention_two_period(project):
    mode = (project.get('retention_release_mode') or 'na').lower()
    if mode in ('first_half', 'second_half', 'two_half', 'multi'):
        return True
    d_first = project.get('retention_release_date_first')
    d_second = project.get('retention_release_date_second')
    if d_first or d_second:
        return True
    return False


def retention_installment_pct_display(project, part):
    """part: one_off | first | second"""
    total = project.get('retention_pct')
    n_total = _pct_number(total)
    if n_total is None:
        return None
    if part == 'one_off':
        return format_retention_pct(total)
    if _retention_two_period(project):
        half = n_total / 2
        text = f'{half:.4f}'.rstrip('0').rstrip('.')
        return f'{text}%'
    return format_retention_pct(total)


def _retention_row_note(project, part):
    notes = []
    pct = retention_installment_pct_display(project, part)
    if pct:
        notes.append(pct)
    if part == 'one_off':
        max_pct = format_retention_pct(project.get('retention_max_pct'))
        if max_pct:
            notes.append(f'上限 {max_pct}')
        amt = project.get('retention_max_amount')
        if amt not in (None, '', 0):
            try:
                notes.append(f'上限 HK${float(amt):,.0f}')
            except (TypeError, ValueError):
                pass
    return ' · '.join(notes)


def build_fac_retention_rows(project):
    """Cover Page 保固金退還 → FAC 關鍵日期列（對齊 QS，非寫死 %）"""
    if not _retention_release_active(project):
        return []
    mode = (project.get('retention_release_mode') or 'na').lower()
    rows = []

    def add(key, label, label_en, date_field, part):
        date_val = project.get(date_field)
        show = bool(date_val)
        if not show:
            if key == 'one_off' and mode == 'one_off':
                show = True
            elif key == 'first' and mode in ('first_half', 'two_half', 'multi'):
                show = True
            elif key == 'second' and mode in ('second_half', 'two_half', 'multi'):
                show = True
        if not show:
            return
        rows.append({
            'key': key,
            'label': label,
            'label_en': label_en,
            'date': date_val,
            'note': _retention_row_note(project, part),
        })

    add('one_off', '一次性退還保證金', 'Release of Retention (One-off)',
        'retention_release_date', 'one_off')
    add('first', '退還第一期保證金', 'Release of First Half Retention',
        'retention_release_date_first', 'first')
    add('second', '退還第二期保證金', 'Release of Second Half Retention',
        'retention_release_date_second', 'second')
    return rows


def retention_dlp_pending_hint(project):
    """保修期列提示：第二期保固金尚未填日期時（不含寫死 %）。"""
    if not _retention_release_active(project):
        return None
    if project.get('retention_release_date_second'):
        return None
    mode = (project.get('retention_release_mode') or 'na').lower()
    expects_second = mode in ('second_half', 'two_half', 'multi')
    if not expects_second and project.get('retention_release_date_first') and _retention_two_period(project):
        expects_second = True
    if not expects_second:
        return None
    months = project.get('dlp_period_months')
    if months:
        return f'第二期保固金通常於保修期屆滿退還（約 {int(months)} 個月；請填退還第二期日期）'
    return '第二期保固金通常於保修期屆滿退還（請填退還第二期日期）'


PROJECT_DOC_CATEGORIES = {
    'attachment1_main_contract': '附件1 — 主合約',
    'attachment1_loa': '附件1 — LOA',
    'attachment1_signoff': '附件1 — 投標合同會簽表',
    'attachment1_email': '附件1 — 電郵記錄',
    'attachment1_related': '附件1 — 相關文件',
    'attachment3_sot_sor': '附件3 — SOT & SOR',
}


def _mp_codes_from_serial_year(serial: str, year: str) -> list[str]:
    """178 + 25 → [Q0178_25, Q178_25]；1241 + 24 → [Q1241_24]"""
    serial = (serial or '').strip()
    year = (year or '').strip()
    if not serial or not year:
        return []
    raw = f'Q{serial}_{year}'.upper()
    padded = f'Q{serial.zfill(4)}_{year}'.upper()
    out: list[str] = []
    for code in (padded, raw):
        if code not in out:
            out.append(code)
    return out


def derive_mp_contract_code_variants(quotation_no=None, project_code=None) -> list[str]:
    """
    由報價／項目代碼推導 MP 合約編號候選。
    MS/Q178/25/kl → Q0178_25（4 位補零）；MS/Q1241/24 → Q1241_24。
    """
    out: list[str] = []
    for src in (quotation_no, project_code):
        if not src:
            continue
        s = str(src).strip()
        m = re.search(r'(?:MS/)?Q(\d+)[/_](\d{2,4})', s, re.I)
        if m:
            for code in _mp_codes_from_serial_year(m.group(1), m.group(2)):
                if code not in out:
                    out.append(code)
            continue
        m = re.match(r'^Q(\d+)_(\d+)$', s, re.I)
        if m:
            for code in _mp_codes_from_serial_year(m.group(1), m.group(2)):
                if code not in out:
                    out.append(code)
    return out


def derive_mp_contract_code(quotation_no=None, project_code=None):
    """MS/Q1241/24/kp 或 Q1241_24 → Q1241_24；MS/Q178/25 → Q0178_25"""
    variants = derive_mp_contract_code_variants(quotation_no, project_code)
    return variants[0] if variants else None


def _sc_charge_group(sc_no):
    """判項前綴 → B(分判) / C(物料及其他)"""
    s = (sc_no or '').strip().upper()
    if s.startswith('M-') or re.match(r'^M\d', s):
        return 'C'
    if s.startswith('O-') or re.match(r'^O\d', s):
        return 'C'
    return 'B'


def compute_settlement(project, subcontractors):
    """
    第5頁項目金額結算 A–E（對齊 Cover Page 第6頁顯示欄）
    A = MP承建金額
    B = 分判承包價（SC 類，不含 excluded）
    C = 物料及其他支出（M/O + 人工分攤 + excluded 扣減）
    D = A - (B + C)
    E = D / A
    """
    contract_a = float(project.get('contract_amount') or 0)
    labour = float(project.get('labour_allocation') or 0)

    sub_b = 0.0
    material_c = 0.0
    excluded_total = 0.0

    for sc in subcontractors or []:
        amt = float(sc.get('contract_amount') or 0)
        if sc.get('is_excluded'):
            excluded_total += amt
            continue
        grp = _sc_charge_group(sc.get('sc_no'))
        if grp == 'B':
            sub_b += amt
        else:
            material_c += amt

    # excluded 在 Excel 以負數計入 (C)
    material_c += labour - excluded_total

    manual_c = project.get('material_other_expenses')
    if manual_c is not None and manual_c != '':
        material_c = float(manual_c)

    profit_d = contract_a - sub_b - material_c
    profit_rate_e = (profit_d / contract_a * 100) if contract_a else 0.0

    final_sub = project.get('final_subcontract_sum')
    if final_sub is None or final_sub == '':
        final_sub = sub_b

    return {
        'contract_sum_a': contract_a,
        'subcontract_sum_b': sub_b,
        'material_other_c': material_c,
        'current_profit_d': profit_d,
        'current_profit_pct_e': round(profit_rate_e, 2),
        'final_subcontract_sum': float(final_sub or 0),
        'excluded_total': excluded_total,
        'labour_allocation': labour,
    }


def format_clients_display(client, client_secondary=None):
    """列表顯示用：客方一 · 客方二"""
    def _clean(v):
        if not v:
            return ''
        return str(v).strip().rstrip('/').strip()

    parts = [_clean(c) for c in (client, client_secondary) if _clean(c)]
    return ' · '.join(parts) if parts else '—'


def format_mp_contract_label(codes, primary=None):
    """Q0231_24 等4個"""
    if not codes:
        return primary or '—', []
    if isinstance(codes[0], dict):
        ordered = [c.get('mp_contract_code') for c in codes if c.get('mp_contract_code')]
    else:
        ordered = list(codes)
    if not ordered:
        return primary or '—', []
    primary = primary or ordered[0]
    if len(ordered) == 1:
        return primary, ordered
    return f"{primary} 等{len(ordered)}個", ordered


def format_summary_row(project, settlement=None):
    """第2頁 Summary 單列"""
    settlement = settlement or {}
    title = project.get('project_name_zh') or project.get('project_name') or ''
    if not title:
        title = project.get('project_name_en') or ''
    mp_code = (
        project.get('mp_contract_code')
        or derive_mp_contract_code(project.get('quotation_no'), project.get('project_code'))
        or project.get('project_code')
    )
    mp_label, mp_list = format_mp_contract_label(
        project.get('mp_contract_codes') or [], mp_code,
    )
    return {
        'project_id': project.get('id'),
        'mp_contract_code': mp_code,
        'mp_contract_label': mp_label,
        'mp_contract_codes': mp_list,
        'account_code': project.get('account_code'),
        'main_contract_title': title,
        'main_contract_title_en': project.get('project_name_en'),
        'client': project.get('client'),
        'client_secondary': project.get('client_secondary'),
        'clients_display': format_clients_display(
            project.get('client'), project.get('client_secondary'),
        ),
        'work_type': project.get('work_type'),
        'category_l1_code': project.get('category_l1_code'),
        'category_l2_code': project.get('category_l2_code'),
        'category_l1_label': project.get('category_l1_label'),
        'category_l2_label': project.get('category_l2_label'),
        'contract_amount': project.get('contract_amount') or 0,
        'status': project.get('status'),
        'current_profit': settlement.get('current_profit_d'),
        'current_profit_pct': settlement.get('current_profit_pct_e'),
        'main_contractor': project.get('main_contractor'),
        'person_in_charge': project.get('person_in_charge') or project.get('qs_in_charge'),
        'quotation_no': project.get('quotation_no'),
        'project_code': project.get('project_code'),
        'sc_count': project.get('sc_count') or 0,
        'total_paid': project.get('total_paid') or 0,
    }


def build_cover_page(project, subcontractors, documents=None):
    """Cover Page 完整 payload（第4–6頁）"""
    settlement = compute_settlement(project, subcontractors)
    summary = format_summary_row(project, settlement)
    retention_label = retention_release_label(project)
    mode = (project.get('retention_release_mode') or 'na').lower()

    return {
        'summary': summary,
        'identity': {
            'main_contract_title_zh': project.get('project_name_zh'),
            'main_contract_title_en': project.get('project_name_en'),
            'mp_contract_code': summary['mp_contract_code'],
            'job_no': project.get('job_no'),
            'work_type': project.get('work_type'),
            'category_l1_code': project.get('category_l1_code'),
            'category_l2_code': project.get('category_l2_code'),
            'category_l1_label': project.get('category_l1_label'),
            'category_l2_label': project.get('category_l2_label'),
            'account_code': project.get('account_code'),
            'client': project.get('client'),
            'client_secondary': project.get('client_secondary'),
            'clients_display': format_clients_display(
                project.get('client'), project.get('client_secondary'),
            ),
            'main_contractor': project.get('main_contractor'),
        },
        'commercial': {
            'tender_sum': project.get('tender_sum') or 0,
            'contract_sum': project.get('contract_amount') or 0,
            'anticipated_profit_pct': project.get('anticipated_profit_pct'),
        },
        'schedule': {
            'main_contract_commencement_date': project.get('main_contract_commencement_date'),
            'project_completion_date': project.get('project_completion_date'),
            'pc_cert_date': project.get('pc_cert_date'),
            'mp_commencement_date': project.get('mp_commencement_date'),
            'extended_completion_date': project.get('extended_completion_date'),
            'dlp_period_months': project.get('dlp_period_months'),
            'construction_period_days': project.get('construction_period_days'),
            'site_period_text': project.get('site_period_text'),
        },
        'people': {
            'project_manager': project.get('project_manager'),
            'qs_in_charge': project.get('qs_in_charge') or project.get('person_in_charge'),
            'person_code': project.get('person_code'),
        },
        'retention': {
            'retention_pct': project.get('retention_pct'),
            'retention_max_pct': project.get('retention_max_pct'),
            'retention_max_amount': project.get('retention_max_amount'),
            'release_mode': mode,
            'release_mode_label': retention_label or '不適用',
            'release_date': project.get('retention_release_date'),
            'release_date_first': project.get('retention_release_date_first'),
            'release_date_second': project.get('retention_release_date_second'),
        },
        'milestones': {
            'dlp_cert_date': project.get('dlp_cert_date'),
            'mp_fac_signed_date': project.get('mp_fac_signed_date'),
            'sc_fac_signed_date': project.get('sc_fac_signed_date'),
        },
        'settlement': settlement,
        'documents': documents or [],
        'quotation_no': project.get('quotation_no'),
        'project_code': project.get('project_code'),
        'status': project.get('status'),
        'notes': project.get('notes'),
    }
