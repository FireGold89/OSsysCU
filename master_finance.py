"""
master_finance.py — Master List Phase 2：糧期／分判付款／支票明細
"""
import re
from datetime import datetime


def _safe_str(val):
    if val is None:
        return None
    s = str(val).strip()
    return s if s and s.lower() not in ('none', 'nan', '-') else None


def _safe_float(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace(',', '').replace('$', '')
    if not s:
        return None
    m = re.search(r'[\d,]+(?:\.\d+)?', s.replace(',', ''))
    if m:
        try:
            return float(m.group().replace(',', ''))
        except ValueError:
            pass
    return None


def _safe_date(val):
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.strftime('%Y-%m-%d')
    s = str(val).strip()
    if not s:
        return None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y'):
        try:
            return datetime.strptime(s[:10], fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return None

# 2022+ modern 預設欄位索引（0-based）
MODERN_FINANCE_DEFAULTS = {
    'subcon_qs_company': 23,
    'subcon_qs_amount': 24,
    'subcon_type': 22,
    'invoice_date': 27,
    'invoice_no': 28,
    'receipt_date': 29,
    'cheque': 30,
    'subcon_admin_company': 32,
    'subcon_admin_amount': 33,
    'voucher_date': 34,
}

_IP_RE = re.compile(r'IP\s*(\d+)', re.I)


def split_cell_lines(val):
    """Excel 儲存格內換行 → 多筆明細"""
    if val is None:
        return []
    if isinstance(val, datetime):
        return [val.strftime('%Y-%m-%d')]
    s = str(val).replace('\r\n', '\n').replace('\r', '\n')
    parts = re.split(r'\n+', s)
    out = []
    for p in parts:
        p = p.strip().strip('|').strip()
        if not p or p in ('-', '—', 'NA', 'N/A'):
            continue
        out.append(p)
    return out


def _header_text(raw):
    return str(raw or '').replace('\n', ' ').strip().lower()


def map_finance_columns(header_vals):
    """辨識 QS 主分判 vs Admin 財務欄"""
    m = {}
    for i, raw in enumerate(header_vals):
        h = _header_text(raw)
        if not h:
            continue
        is_admin = 'admin' in h or '由admin' in h
        if '主要分判' in h and not is_admin and 'subcon_qs_company' not in m:
            m['subcon_qs_company'] = i
        elif h.startswith('分判金額') and not is_admin and 'subcon_qs_amount' not in m:
            m['subcon_qs_amount'] = i
        elif '外判與否' in h and 'subcon_type' not in m:
            m['subcon_type'] = i
        elif ('外判公司' in h or ('主要分判' in h and is_admin)) and 'subcon_admin_company' not in m:
            m['subcon_admin_company'] = i
        elif ('外判金額' in h or '分判金額' in h) and is_admin and 'subcon_admin_amount' not in m:
            m['subcon_admin_amount'] = i
        elif ('上憑' in h or '上週' in h) and is_admin and 'voucher_date' not in m:
            m['voucher_date'] = i
        elif '出發票' in h and is_admin and 'invoice_date' not in m:
            m['invoice_date'] = i
        elif ('發票編號' in h or '發票號碼' in h or '憑證' in h) and is_admin and 'invoice_no' not in m:
            m['invoice_no'] = i
        elif ('收票' in h or '收款' in h) and is_admin and 'receipt_date' not in m:
            m['receipt_date'] = i
        elif '支票' in h and is_admin and 'cheque' not in m:
            m['cheque'] = i
    return m


def _col_idx(finance_map, key, defaults=None):
    d = defaults or MODERN_FINANCE_DEFAULTS
    return finance_map.get(key, d.get(key))


def _cell_lines(row_vals, finance_map, key):
    idx = _col_idx(finance_map, key)
    if idx is None or idx >= len(row_vals):
        return []
    return split_cell_lines(row_vals[idx])


def _normalize_name(s):
    if not s:
        return ''
    return re.sub(r'[\s有限公司()（）]+', '', str(s).lower())


def names_similar(a, b):
    na, nb = _normalize_name(a), _normalize_name(b)
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    if len(na) >= 2 and len(nb) >= 2 and na[:2] == nb[:2]:
        return True
    return False


def _amount_display(amt):
    if amt is None:
        return None
    s = f'{amt:.2f}'.rstrip('0').rstrip('.')
    return f'${s}' if s else None


def _date_display(val):
    """Excel 日期顯示（例 22/3/2025）"""
    if val is None:
        return None
    if isinstance(val, datetime):
        return f'{val.day}/{val.month}/{val.year}'
    s = str(val).strip()
    if re.match(r'\d{1,2}/\d{1,2}/\d{2,4}', s):
        return s
    iso = _safe_date(s)
    if iso:
        d = datetime.strptime(iso, '%Y-%m-%d')
        return f'{d.day}/{d.month}/{d.year}'
    return s or None


def format_finance_display_line(part1, part2=None, part3=None):
    """統一顯示：A , B, C（例 #828310 , 003, 22/3/2025）"""
    parts = [p for p in (part1, part2, part3) if p is not None and str(p).strip()]
    if len(parts) >= 3:
        return f'{parts[0]} , {parts[1]}, {parts[2]}'
    if len(parts) == 2:
        return f'{parts[0]} , {parts[1]}'
    return parts[0] if parts else None


def parse_invoice_line(text):
    """M58740-$3224313-IP1 或 M52161 -IP1-$525000 → invoice_no, ip_no, amount"""
    parsed = parse_client_invoice_line(text)
    return parsed['invoice_no'], parsed['ip_no'], parsed['invoice_amount']


def parse_client_invoice_line(text):
    """發票號碼 , 糧期, 金額 — 例 M57872 , IP1, $182481.3"""
    raw = (text or '').strip()
    s = raw.replace('，', ',')
    flat = s.replace(',', '')
    if not s:
        return {
            'invoice_no': None,
            'ip_no': None,
            'invoice_amount': None,
            'amount_display': None,
            'display_line': None,
            'raw_line': None,
        }

    ip_no = None
    ip_m = _IP_RE.search(flat)
    if ip_m:
        ip_no = f"IP{ip_m.group(1)}"

    amt = None
    amt_m = re.search(r'\$\s*([\d,]+(?:\.\d+)?)', s)
    if amt_m:
        amt = _safe_float(amt_m.group(1))
    else:
        # 僅有單一發票號（如 M61422）時，不應把尾數當金額。
        only_invoice_token = bool(
            re.match(r'^[A-Za-z]?[A-Za-z0-9-]*\d{4,}[A-Za-z0-9-]*$', flat)
        ) and (' ' not in flat and '-' not in flat and '/' not in flat)
        if not only_invoice_token:
            tail = flat[ip_m.end():] if ip_m else flat
            nums = [
                float(x.replace(',', ''))
                for x in re.findall(r'[\d,]+(?:\.\d+)?', tail)
                if x.replace(',', '').strip()
            ]
            if nums:
                amt = max(nums)
            elif not ip_no:
                amt = _safe_float(flat)

    inv_no = None
    inv_m = re.match(r'^([A-Za-z]?[A-Za-z0-9-]*\d{4,}[A-Za-z0-9-]*)', flat)
    if inv_m:
        inv_no = inv_m.group(1).rstrip('-/,')

    if not inv_no and not ip_no and amt is None:
        inv_no = flat[:40]

    amt_disp = _amount_display(amt)
    display = format_finance_display_line(inv_no, ip_no, amt_disp)
    return {
        'invoice_no': inv_no,
        'ip_no': ip_no,
        'invoice_amount': amt,
        'amount_display': amt_disp,
        'display_line': display,
        'raw_line': raw or None,
    }


def split_qs_subcon_companies(val):
    """QS 主分判商：儲存格內換行或多段空白分隔"""
    if val is None:
        return []
    lines = split_cell_lines(val)
    if len(lines) > 1:
        return [_safe_str(x) for x in lines if _safe_str(x)]
    s = str(val).strip()
    if not s:
        return []
    parts = [_safe_str(p) for p in re.split(r'\s{2,}', s) if _safe_str(p)]
    return parts if parts else ([_safe_str(s)] if _safe_str(s) else [])


def split_qs_subcon_amounts(val):
    """QS 分判金額：$1,900,000 等多段"""
    if val is None:
        return []
    s = str(val).replace('\r\n', '\n').replace('\r', '\n')
    found = re.findall(r'\$\s*[\d,]+(?:\.\d+)?', s.replace(',', ''))
    if found:
        return [a for a in (_safe_float(x) for x in found) if a is not None]
    lines = split_cell_lines(val)
    out = []
    for line in lines:
        amt = _safe_float(line)
        if amt is not None:
            out.append(amt)
    return out


def parse_qs_subcon_lines(co_val, amt_val):
    """主要分判商/供應商 + 分判金額（可多行配對）"""
    companies = split_qs_subcon_companies(co_val)
    amounts = split_qs_subcon_amounts(amt_val)
    n = max(len(companies), len(amounts), 0)
    rows = []
    for i in range(n):
        co = companies[i] if i < len(companies) else None
        amt = amounts[i] if i < len(amounts) else None
        amt_disp = _amount_display(amt)
        rows.append({
            'line_seq': i + 1,
            'subcon_company': co,
            'subcon_amount': amt,
            'amount_display': amt_disp,
            'display_line': format_finance_display_line(co, amt_disp),
        })
    return rows


def is_qs_main_subcon(company, qs_subcon_lines):
    if not company:
        return 0
    for row in qs_subcon_lines or []:
        if names_similar(company, row.get('subcon_company')):
            return 1
    return 0


def build_subcon_payment_row(company, amount_raw, voucher_raw, qs_subcon_lines, line_seq):
    """分判商 , 金額, 上憑日期"""
    co = _safe_str(company)
    amt = _safe_float(amount_raw)
    voucher_iso = _safe_date(voucher_raw)
    voucher_disp = _date_display(voucher_raw)
    amt_disp = _amount_display(amt)
    display = format_finance_display_line(co, amt_disp, voucher_disp)
    raw_parts = [co, str(amount_raw).strip() if amount_raw is not None else None, _date_display(voucher_raw)]
    raw_line = ' , '.join(p for p in raw_parts if p) or co
    return {
        'line_seq': line_seq,
        'subcon_company': co,
        'subcon_amount': amt,
        'voucher_date': voucher_iso,
        'voucher_display': voucher_disp,
        'amount_display': amt_disp,
        'display_line': display,
        'raw_line': raw_line,
        'is_main_subcon': is_qs_main_subcon(co, qs_subcon_lines),
    }


def parse_cheque_line_amount(text):
    """支票欄若含金額（例 $120280 或純數字），供業主糧期發票金額對應"""
    s = (text or '').strip()
    if not s:
        return None
    # 支票號碼行（#828310 003 , 日期）不含業主發票金額
    if re.match(r'^#?\d+\s+\d{3}\s*[,，]', s):
        return None
    amt_m = re.search(r'\$\s*([\d,]+(?:\.\d+)?)', s)
    if amt_m:
        return _safe_float(amt_m.group(1))
    if re.match(r'^[\d,]+(?:\.\d+)?$', s.replace(',', '')):
        return _safe_float(s)
    return None


def parse_cheque_line(text):
    """
    #828310 003 , 22/3/2025 → 支票號碼 #828310、銀行 003、日期
    顯示格式：#828310 , 003, 22/3/2025
    """
    s = (text or '').strip()
    if not s:
        return {
            'cheque_no': None,
            'bank': None,
            'cheque_date': None,
            'cheque_ref': None,
            'raw_line': None,
        }
    m = re.match(r'^\s*(#?\d+)\s+(\d{3})\s*,?\s*(.+)\s*$', s)
    if m:
        cheque_no = m.group(1)
        if not cheque_no.startswith('#'):
            cheque_no = f'#{cheque_no.lstrip("#")}'
        bank = m.group(2)
        date_part = m.group(3).strip().lstrip(',').strip()
        cheque_date = _safe_date(date_part)
        cheque_ref = f'{cheque_no} , {bank}, {date_part}'
        return {
            'cheque_no': cheque_no,
            'bank': bank,
            'cheque_date': cheque_date,
            'cheque_date_display': date_part,
            'cheque_ref': cheque_ref,
            'raw_line': s,
        }
    cheque_date = _safe_date(s)
    return {
        'cheque_no': None,
        'bank': None,
        'cheque_date': cheque_date,
        'cheque_ref': s[:200],
        'raw_line': s,
    }


def extract_finance_detail(row_vals, finance_map=None, layout='modern'):
    """
    從一列 Excel 抽出 Phase 2 財務明細。
    僅 modern (2022+) 有完整 Admin 欄；其他版型回傳空明細。
    """
    finance_map = finance_map or {}
    if layout != 'modern':
        return {
            'summary': None,
            'qs_subcon_lines': [],
            'client_invoices': [],
            'subcon_payments': [],
            'cheques': [],
        }

    d = MODERN_FINANCE_DEFAULTS
    qs_co_idx = _col_idx(finance_map, 'subcon_qs_company', d)
    qs_amt_idx = _col_idx(finance_map, 'subcon_qs_amount', d)
    qs_co_raw = row_vals[qs_co_idx] if qs_co_idx is not None and qs_co_idx < len(row_vals) else None
    qs_amt_raw = row_vals[qs_amt_idx] if qs_amt_idx is not None and qs_amt_idx < len(row_vals) else None
    qs_subcon_lines = parse_qs_subcon_lines(qs_co_raw, qs_amt_raw)

    summary = None
    if qs_subcon_lines:
        total = sum(r['subcon_amount'] or 0 for r in qs_subcon_lines)
        first = qs_subcon_lines[0]
        summary = {
            'main_subcon_company': first.get('subcon_company'),
            'main_subcon_amount': total or first.get('subcon_amount'),
            'qs_subcon_count': len(qs_subcon_lines),
            'qs_subcon_total': total if total else None,
        }

    inv_dates = _cell_lines(row_vals, finance_map, 'invoice_date')
    inv_lines = _cell_lines(row_vals, finance_map, 'invoice_no')
    receipt_lines = _cell_lines(row_vals, finance_map, 'receipt_date')
    cheque_lines = _cell_lines(row_vals, finance_map, 'cheque')
    sub_cos = _cell_lines(row_vals, finance_map, 'subcon_admin_company')
    sub_amts = _cell_lines(row_vals, finance_map, 'subcon_admin_amount')
    voucher_dates = _cell_lines(row_vals, finance_map, 'voucher_date')

    client_invoices = []
    n_inv = max(len(inv_lines), len(inv_dates), len(receipt_lines))
    for i in range(n_inv):
        raw = inv_lines[i] if i < len(inv_lines) else ''
        parsed = parse_client_invoice_line(raw)
        # 業主糧期金額：發票欄內嵌金額，或同列「支票號碼,銀行,日期(Admin)」欄的 $ 金額（非分判金額）
        if parsed.get('invoice_amount') is None and i < len(cheque_lines):
            cheque_amt = parse_cheque_line_amount(cheque_lines[i])
            if cheque_amt is not None:
                parsed['invoice_amount'] = cheque_amt
                parsed['amount_display'] = _amount_display(cheque_amt)
                parsed['display_line'] = format_finance_display_line(
                    parsed.get('invoice_no'), parsed.get('ip_no'), parsed.get('amount_display')
                )
        inv_date_raw = inv_dates[i] if i < len(inv_dates) else None
        receipt_raw = receipt_lines[i] if i < len(receipt_lines) else None
        client_invoices.append({
            'line_seq': i + 1,
            'ip_no': parsed['ip_no'],
            'invoice_date': _safe_date(inv_date_raw),
            'invoice_date_display': _date_display(inv_date_raw),
            'invoice_no': parsed['invoice_no'],
            'invoice_amount': parsed['invoice_amount'],
            'amount_display': parsed['amount_display'],
            'receipt_date': _safe_date(receipt_raw),
            'receipt_date_display': _date_display(receipt_raw),
            'display_line': parsed['display_line'],
            'raw_line': parsed['raw_line'],
        })

    subcon_payments = []
    n_sub = max(len(sub_cos), len(sub_amts), len(voucher_dates))
    for i in range(n_sub):
        co = sub_cos[i] if i < len(sub_cos) else None
        amt_raw = sub_amts[i] if i < len(sub_amts) else None
        voucher_raw = voucher_dates[i] if i < len(voucher_dates) else None
        subcon_payments.append(
            build_subcon_payment_row(co, amt_raw, voucher_raw, qs_subcon_lines, i + 1)
        )

    cheques = []
    for i, raw in enumerate(cheque_lines):
        parsed = parse_cheque_line(raw)
        cheques.append({
            'line_seq': i + 1,
            'cheque_no': parsed['cheque_no'],
            'bank': parsed['bank'],
            'cheque_ref': parsed['cheque_ref'],
            'cheque_date': parsed['cheque_date'],
            'cheque_date_display': parsed.get('cheque_date_display'),
            'raw_line': parsed['raw_line'],
        })

    return {
        'summary': summary,
        'qs_subcon_lines': qs_subcon_lines,
        'client_invoices': client_invoices,
        'subcon_payments': subcon_payments,
        'cheques': cheques,
    }


def calc_master_profit(quoted_amount, awarded_amount, subcon_amount):
    """
    Master List 利潤公式（與 Excel Z/AA 欄一致）：
      利潤$ = 中標金額 − 分判金額
      利潤% = 利潤$ ÷ 報價/投標金額 × 100
    """
    if awarded_amount is None or subcon_amount is None:
        return None, None
    try:
        awarded = float(awarded_amount)
        subcon = float(subcon_amount)
    except (TypeError, ValueError):
        return None, None
    profit_amount = round(awarded - subcon, 2)
    profit_pct = None
    if quoted_amount is not None:
        try:
            quoted = float(quoted_amount)
            if quoted != 0:
                profit_pct = round(profit_amount / quoted * 100, 4)
        except (TypeError, ValueError):
            pass
    return profit_amount, profit_pct


def apply_master_profit_fields(rec):
    """依主檔金額重算利潤$ / 利潤%（覆寫 Excel 匯入值）"""
    profit_amount, profit_pct = calc_master_profit(
        rec.get('quoted_amount'),
        rec.get('awarded_amount'),
        rec.get('subcon_amount'),
    )
    rec['profit_amount'] = profit_amount
    rec['profit_pct'] = profit_pct
    return rec


def apply_qs_subcon_to_record(rec, row_vals, finance_map=None):
    """2b：主檔 subcon 欄取 QS 主分判首行 + 金額合計"""
    finance_map = finance_map or {}
    idx = _col_idx(finance_map, 'subcon_qs_company', MODERN_FINANCE_DEFAULTS)
    idx_a = _col_idx(finance_map, 'subcon_qs_amount', MODERN_FINANCE_DEFAULTS)
    co_raw = row_vals[idx] if idx is not None and idx < len(row_vals) else None
    amt_raw = row_vals[idx_a] if idx_a is not None and idx_a < len(row_vals) else None
    qs_lines = parse_qs_subcon_lines(co_raw, amt_raw)
    if qs_lines:
        rec['subcon_company'] = qs_lines[0].get('subcon_company')
        total = sum(r['subcon_amount'] or 0 for r in qs_lines)
        rec['subcon_amount'] = total if total else qs_lines[0].get('subcon_amount')
    apply_master_profit_fields(rec)
    return rec
