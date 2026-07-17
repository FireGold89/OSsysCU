"""
master_ip_reconcile.py — 地盤糧期 ↔ Master 行政業主糧期 對照（只讀，不覆寫）
"""
import re

from master_finance import _amount_display, _date_display

_AMOUNT_TOL = 0.05  # HK$ 容差


def normalize_ip_seq(ip_no):
    """IP1 / IP-01 / ip 1 → 1"""
    if not ip_no:
        return None
    m = re.search(r'IP[-\s]?(\d+)', str(ip_no).strip(), re.I)
    return int(m.group(1)) if m else None


def _amounts_match(a, b):
    if a is None or b is None:
        return False
    return abs(float(a) - float(b)) <= _AMOUNT_TOL


def _status_row(site, admin):
    has_site = site is not None
    has_admin = admin is not None
    if has_site and has_admin:
        site_amt = site.get('certified_income')
        admin_amt = admin.get('invoice_amount')
        if _amounts_match(site_amt, admin_amt):
            if admin.get('receipt_date'):
                return 'matched', '金額一致 · 已收票'
            return 'matched_open', '金額一致 · 待收票'
        return 'amount_diff', '金額不一致'
    if has_admin and not has_site:
        if admin.get('receipt_date'):
            return 'admin_only', '行政有記錄 · 地盤未建期'
        return 'admin_only', '行政已開票 · 地盤未建期'
    return 'site_only', '地盤已批款 · 行政未記'


def build_ip_reconciliation(site_items, admin_invoices, quotation_no=None, project_id=None):
    """
    配對 IP 期數（IP1 ↔ IP-01），比對地盤 certified_income vs 行政 invoice_amount。
    兩邊資料各自獨立，此函數只做對照。
    """
    site_by_seq = {}
    for item in site_items or []:
        seq = normalize_ip_seq(item.get('ip_no'))
        if seq is not None and seq not in site_by_seq:
            site_by_seq[seq] = item

    admin_by_seq = {}
    for inv in admin_invoices or []:
        seq = normalize_ip_seq(inv.get('ip_no'))
        if seq is not None and seq not in admin_by_seq:
            admin_by_seq[seq] = inv

    all_seqs = sorted(set(site_by_seq) | set(admin_by_seq))
    rows = []
    stats = {
        'matched': 0,
        'amount_diff': 0,
        'admin_only': 0,
        'site_only': 0,
        'site_count': len(site_by_seq),
        'admin_count': len(admin_by_seq),
    }

    for seq in all_seqs:
        site = site_by_seq.get(seq)
        admin = admin_by_seq.get(seq)
        status, status_label = _status_row(site, admin)
        if status in ('matched', 'matched_open'):
            stats['matched'] += 1
        elif status == 'amount_diff':
            stats['amount_diff'] += 1
        elif status == 'admin_only':
            stats['admin_only'] += 1
        elif status == 'site_only':
            stats['site_only'] += 1

        site_amt = site.get('certified_income') if site else None
        admin_amt = admin.get('invoice_amount') if admin else None
        rows.append({
            'ip_seq': seq,
            'ip_label': f'IP-{seq:02d}',
            'status': status,
            'status_label': status_label,
            'site': {
                'ip_no': site.get('ip_no') if site else None,
                'applied_date': site.get('applied_date') if site else None,
                'certificate_date': site.get('certificate_date') if site else None,
                'application_amount': site.get('application_amount') if site else None,
                'certified_income': site_amt,
                'amount_display': _amount_display(site_amt),
            } if site else None,
            'admin': {
                'ip_no': admin.get('ip_no') if admin else None,
                'invoice_date': admin.get('invoice_date') if admin else None,
                'invoice_date_display': admin.get('invoice_date_display') if admin else None,
                'receipt_date': admin.get('receipt_date') if admin else None,
                'receipt_date_display': admin.get('receipt_date_display') if admin else None,
                'invoice_no': admin.get('invoice_no') if admin else None,
                'invoice_amount': admin_amt,
                'amount_display': _amount_display(admin_amt),
            } if admin else None,
            'amount_match': _amounts_match(site_amt, admin_amt) if site and admin else None,
        })

    return {
        'quotation_no': quotation_no,
        'project_id': project_id,
        'linked': bool(quotation_no and project_id),
        'rows': rows,
        'stats': stats,
    }
