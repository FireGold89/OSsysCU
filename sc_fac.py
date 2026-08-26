"""
sc_fac.py — 分判最終結算（PPT 第20–21頁 · Statement of Final Account）
對照 Final Account Excel：Statement / Summary of Variations / MP-Statement
"""
from datetime import date

from project_cover import derive_mp_contract_code


def _fval(v, default=0.0):
    if v is None or v == '':
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _match_sc_no(record_sc_no, sc_no):
    rs = (record_sc_no or '').strip()
    sn = (sc_no or '').strip()
    if not rs or not sn:
        return False
    return rs == sn or rs.startswith(sn + '.')


def _company_name(sc):
    return (
        (sc.get('company_name_zh') or '').strip()
        or (sc.get('company_name_en') or '').strip()
        or '—'
    )


def _works_title(project):
    en = (project.get('project_name_en') or '').strip()
    zh = (project.get('project_name_zh') or '').strip()
    return en or zh or (project.get('project_name') or '—')


def _paid_as_at(payments):
    dates = []
    for p in payments or []:
        d = p.get('invoice_date') or p.get('paid_date')
        if d:
            dates.append(str(d)[:10])
    return max(dates) if dates else date.today().isoformat()


def _format_as_at(d):
    if not d:
        return ''
    s = str(d)[:10]
    parts = s.split('-')
    if len(parts) == 3:
        return f'{int(parts[2]):02d}/{int(parts[1]):02d}/{parts[0]}'
    return s


def _vo_appendix_rows(vo_records):
    rows = []
    total = 0.0
    for i, v in enumerate(vo_records or [], 1):
        amt = _fval(v.get('amount'))
        total += amt
        rows.append({
            'ai_ref': v.get('ref_no') or f'VO-{i:03d}',
            'quo_ref': v.get('main_contract_vo_no') or v.get('quotation_no') or '',
            'description': (v.get('description') or v.get('service_description') or '—').strip(),
            'qty': 1,
            'unit': 'sum',
            'rate': amt,
            'amount': amt,
        })
    return rows, total


def _deduction_appendix_rows(deduction_records):
    rows = []
    total = 0.0
    for i, v in enumerate(deduction_records or [], 1):
        raw = abs(_fval(v.get('amount')))
        if raw <= 0:
            continue
        amt = -raw
        total += amt
        rows.append({
            'ai_ref': v.get('ref_no') or f'CC-{i:03d}',
            'quo_ref': v.get('quotation_no') or v.get('main_contract_vo_no') or '',
            'description': (v.get('description') or v.get('service_description') or '—').strip(),
            'qty': 1,
            'unit': 'sum',
            'rate': amt,
            'amount': amt,
        })
    return rows, total


def _effective_deductions(vo_records):
    """僅含 record_type=deduction 且金額非零的代支（零額佔位不觸發 P1 行／附錄 II）"""
    return [
        v for v in (vo_records or [])
        if v.get('record_type') == 'deduction' and abs(_fval(v.get('amount'))) > 0
    ]


def _cn_num(n: int) -> str:
    """期數中文數字（一…十、十一…）"""
    ones = ['', '一', '二', '三', '四', '五', '六', '七', '八', '九']
    if n <= 0:
        return str(n)
    if n < 10:
        return ones[n]
    if n == 10:
        return '十'
    if n < 20:
        return '十' + ones[n % 10]
    tens, unit = divmod(n, 10)
    return ones[tens] + '十' + ones[unit]


def build_sc_fac(project, sc, vo_records, payments, interim_count=0, project_subcontractors=None):
    """組裝單一判項 FAC payload（供 UI 與 PDF）"""
    from sc_contract_ref import display_p1_sub_contract_no, resolve_sub_contract_no

    sc_no = sc.get('sc_no') or '—'
    vos = [v for v in (vo_records or []) if v.get('record_type') == 'vo']
    deductions = _effective_deductions(vo_records)

    original = _fval(sc.get('contract_amount'))
    vo_total = sum(_fval(v.get('amount')) for v in vos)
    ded_lines = []
    ded_total = 0.0
    for v in deductions:
        amt = abs(_fval(v.get('amount')))
        ded_total += amt
        ded_lines.append({
            'label_zh': (v.get('description') or v.get('ref_no') or '扣款').strip(),
            'label_en': 'Contra Charge (refer to Appendix II)',
            'amount': -amt,
        })

    final_sum = original + vo_total
    total_paid = sum(_fval(p.get('paid_amount')) for p in (payments or []))
    paid_as_at = _paid_as_at(payments)
    outstanding = final_sum - total_paid - ded_total

    ip_no = max(interim_count, 1)
    final_ip_label = f'Payment IP{ip_no:02d} (Final Payment)'
    final_ip_zh = f'第{_cn_num(ip_no)}期糧款（尾款）'

    appendix_rows, appendix_total = _vo_appendix_rows(vos)
    if appendix_total == 0:
        appendix_total = vo_total
    contra_rows, contra_total = _deduction_appendix_rows(deductions)
    if contra_total == 0 and ded_total:
        contra_total = -ded_total

    mp_contract = (
        project.get('mp_contract_code')
        or derive_mp_contract_code(project.get('quotation_no'), project.get('project_code'))
        or project.get('project_code')
        or '—'
    )

    sc_works = (sc.get('description') or sc.get('service_description') or sc.get('scope') or '').strip()
    if not sc_works:
        sc_works = _company_name(sc)

    return {
        'header': {
            'main_contract_works': _works_title(project),
            'job_no': project.get('job_no') or project.get('project_code') or '—',
            'mp_contract_code': mp_contract,
            'sc_no': sc_no,
            'sub_contract_no': display_p1_sub_contract_no(
                resolve_sub_contract_no(project, sc, project_subcontractors),
            ),
            'quotation_no': sc.get('quotation_no') or '',
            'subcontractor_en': (sc.get('company_name_en') or '').strip(),
            'subcontractor_zh': (sc.get('company_name_zh') or '').strip(),
            'subcontractor': _company_name(sc),
            'sc_works': sc_works,
            'project_name_zh': (project.get('project_name_zh') or '').strip(),
        },
        'settlement': {
            'original_sum': original,
            'variations': vo_total,
            'final_sum': final_sum,
            'total_paid': total_paid,
            'paid_as_at': paid_as_at,
            'paid_as_at_display': _format_as_at(paid_as_at),
            'deduction_lines': ded_lines,
            'deduction_total': ded_total,
            'outstanding': outstanding,
            'final_payment_label_en': final_ip_label,
            'final_payment_label_zh': final_ip_zh,
            'final_payment_amount': max(outstanding, 0),
            'total_outstanding': max(outstanding, 0),
            'reference_only_note': '*僅供糧款',
        },
        'mp_settlement': {
            'original_sum': original,
            'variations': vo_total,
            'final_sum': final_sum,
            'total_paid': total_paid,
            'paid_as_at_display': _format_as_at(paid_as_at),
            'outstanding': outstanding,
            'final_payment_label_zh': final_ip_zh,
            'final_payment_label_en': final_ip_label,
            'final_payment_amount': max(outstanding, 0),
            'total_outstanding': max(outstanding, 0),
            'deduction_lines': [],
        },
        'variations': appendix_rows,
        'variations_total': appendix_total,
        'contra_charges': contra_rows,
        'contra_charges_total': contra_total,
        'appendix_meta': {
            'has_vo': len(vos) > 0,
            'has_contra': ded_total > 0,
        },
        'sc_id': sc.get('id'),
    }
