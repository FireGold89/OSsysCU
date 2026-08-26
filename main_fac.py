"""
main_fac.py — 主合約最終結算（PPT 第19頁 Main Con Final Account）
"""
from project_cover import (
    derive_mp_contract_code,
    retention_release_label,
    build_fac_retention_rows,
    format_retention_pct,
    retention_dlp_pending_hint,
)

MAIN_FAC_MIGRATIONS = [
    ('fac_remeasurement_b', 'REAL DEFAULT 0'),
    ('fac_provisional_qty_e', 'REAL DEFAULT 0'),
    ('fac_provisional_sums_f', 'REAL DEFAULT 0'),
    ('fac_fluctuations_g', 'REAL DEFAULT 0'),
    ('fac_variations_d_override', 'REAL'),
    ('fac_contra_charge_j_override', 'REAL'),
    ('fac_total_paid_i_override', 'REAL'),
    ('fac_paid_as_at_date', 'TEXT'),
    ('fac_lad_rate', 'REAL'),
    ('fac_lad_max', 'REAL'),
    ('fac_testing_commission_date', 'TEXT'),
    ('fac_make_good_date', 'TEXT'),
    ('fac_statement_path', 'TEXT'),
    ('fac_statement_name', 'TEXT'),
    ('fac_pc_cert_path', 'TEXT'),
    ('fac_pc_cert_name', 'TEXT'),
    ('fac_mg_cert_path', 'TEXT'),
    ('fac_mg_cert_name', 'TEXT'),
]

MAIN_FAC_WRITABLE = [
    'fac_remeasurement_b', 'fac_provisional_qty_e', 'fac_provisional_sums_f',
    'fac_fluctuations_g', 'fac_variations_d_override', 'fac_contra_charge_j_override',
    'fac_total_paid_i_override', 'fac_paid_as_at_date',
    'fac_lad_rate', 'fac_lad_max', 'fac_testing_commission_date', 'fac_make_good_date',
]


def _fval(v, default=0.0):
    if v is None or v == '':
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _contract_label(project):
    code = (
        project.get('mp_contract_code')
        or derive_mp_contract_code(project.get('quotation_no'), project.get('project_code'))
        or project.get('project_code')
        or '—'
    )
    title_en = project.get('project_name_en') or ''
    title_zh = project.get('project_name_zh') or project.get('project_name') or ''
    works = title_zh or title_en or '—'
    return code, works, title_zh, title_en


def _dlp_days(project):
    months = project.get('dlp_period_months')
    if months:
        return int(months) * 30
    return None


def build_main_con_fac(project, vo_totals=None, interim_items=None):
    """組裝主合約 FAC 頁面 payload"""
    vo_totals = vo_totals or {}
    interim_items = interim_items or []

    a = _fval(project.get('contract_amount'))
    b = _fval(project.get('fac_remeasurement_b'))
    c = _fval(project.get('supplemental_contract_amount'))
    e = _fval(project.get('fac_provisional_qty_e'))
    f = _fval(project.get('fac_provisional_sums_f'))
    g = _fval(project.get('fac_fluctuations_g'))

    d_auto = _fval(vo_totals.get('vo_total'))
    d_ov = project.get('fac_variations_d_override')
    d = _fval(d_ov) if d_ov is not None and d_ov != '' else d_auto
    d_source = 'manual' if d_ov is not None and d_ov != '' else 'auto_vo'

    i_auto = _fval(project.get('ip_total_income'))
    if not i_auto and interim_items:
        i_auto = sum(_fval(it.get('certified_income')) for it in interim_items)
    i_ov = project.get('fac_total_paid_i_override')
    i = _fval(i_ov) if i_ov is not None and i_ov != '' else i_auto
    i_source = 'manual' if i_ov is not None and i_ov != '' else ('ip_total' if project.get('ip_total_income') else 'interim_sum')

    j_auto = abs(_fval(vo_totals.get('deduction_total')))
    j_ov = project.get('fac_contra_charge_j_override')
    j = _fval(j_ov) if j_ov is not None and j_ov != '' else j_auto
    j_source = 'manual' if j_ov is not None and j_ov != '' else 'auto_deduction'

    h = a + b + c + d + e + f + g
    k = h - i - j

    contract_no, works, name_zh, name_en = _contract_label(project)
    dlp_days = _dlp_days(project)

    return {
        'header': {
            'contract_no': contract_no,
            'contract_works': works,
            'project_name_zh': name_zh,
            'project_name_en': name_en,
            'project_code': project.get('project_code'),
            'quotation_no': project.get('quotation_no'),
        },
        'settlement': {
            'a_original': a,
            'b_remeasurement': b,
            'c_supplemental': c,
            'd_variations': d,
            'd_auto': d_auto,
            'd_source': d_source,
            'e_provisional_qty': e,
            'f_provisional_sums': f,
            'g_fluctuations': g,
            'h_final_sum': h,
            'i_total_paid': i,
            'i_auto': i_auto,
            'i_source': i_source,
            'i_as_at': project.get('fac_paid_as_at_date'),
            'j_contra_charge': j,
            'j_auto': j_auto,
            'j_source': j_source,
            'k_outstanding': k,
        },
        'attachments': {
            'statement': {
                'path': project.get('fac_statement_path'),
                'name': project.get('fac_statement_name'),
            },
            'pc_cert': {
                'path': project.get('fac_pc_cert_path'),
                'name': project.get('fac_pc_cert_name'),
            },
            'mg_cert': {
                'path': project.get('fac_mg_cert_path'),
                'name': project.get('fac_mg_cert_name'),
            },
        },
        'key_dates': {
            'commencement_date': project.get('main_contract_commencement_date') or project.get('mp_commencement_date'),
            'completion_date': project.get('project_completion_date'),
            'contract_period_days': project.get('construction_period_days'),
            'dlp_days': dlp_days,
            'dlp_months': project.get('dlp_period_months'),
            'lad_rate': project.get('fac_lad_rate'),
            'lad_max': project.get('fac_lad_max'),
            'pc_cert_date': project.get('pc_cert_date'),
            'dlp_commencement_date': project.get('dlp_cert_date'),
            'testing_commission_date': project.get('fac_testing_commission_date'),
            'make_good_date': project.get('fac_make_good_date') or project.get('dlp_cert_date'),
            'mp_fac_signed_date': project.get('mp_fac_signed_date'),
            'retention_release_label': retention_release_label(project),
            'retention_release_date': project.get('retention_release_date'),
            'retention_release_date_first': project.get('retention_release_date_first'),
            'retention_release_date_second': project.get('retention_release_date_second'),
            'retention_pct_display': format_retention_pct(project.get('retention_pct')),
            'retention_max_pct_display': format_retention_pct(project.get('retention_max_pct')),
            'retention_max_amount': project.get('retention_max_amount'),
            'retention_rows': build_fac_retention_rows(project),
            'retention_dlp_hint': retention_dlp_pending_hint(project),
        },
        'editable': {k: project.get(k) for k in MAIN_FAC_WRITABLE},
    }
