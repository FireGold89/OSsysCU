"""參考編號工具 — 父級分組（M-011.26 → M-011）"""
import re

SC_PREFIXES = ('SC', 'M', 'O')
_SC_NO_RE = re.compile(r'^(SC|M|O)-(\d+)(?:\.(\d+))?(.*)$', re.IGNORECASE)


def derive_parent_sc_no(sc_no):
    """從參考編號推導父級（用於 M-011.xx / SC-003A 分組）"""
    if not sc_no:
        return None
    s = sc_no.strip()
    if '.' in s:
        return s.rsplit('.', 1)[0]
    m = re.match(r'^(.+?)([A-Z]\d*)$', s)
    if m and m.group(1) != s and len(m.group(2)) <= 3:
        return m.group(1)
    return s


def resolve_contract_amounts(contract_sum, vo_amount, revised=None):
    """
    Excel: Revised (J) = Contract Sum (H) + VO (I)
    優先使用 J；若 J 缺失則 H + I；若只有 J 則 H=J, VO=0
    """
    h = float(contract_sum or 0)
    v = float(vo_amount or 0)
    j = float(revised or 0) if revised is not None else 0

    if j > 0:
        if h <= 0 and v == 0:
            h = j
        elif abs(j - (h + v)) > 0.02:
            # J 與 H+VO 不一致時以 J 為準，反推 H
            h = j - v
    elif h or v:
        j = h + v
    else:
        j = 0

    return round(h, 2), round(v, 2), round(j, 2)


def _norm_company(name):
    return re.sub(r'\s+', ' ', (name or '').strip().lower())


def company_matches_sc(sc, company):
    """公司名稱是否與合同項目相符（模糊比對）"""
    company = _norm_company(company)
    if not company:
        return False
    for field in ('company_name_en', 'company_name_zh'):
        val = _norm_company(sc.get(field) if isinstance(sc, dict) else getattr(sc, field, None))
        if not val:
            continue
        if company == val or company in val or val in company:
            return True
    return False


def parse_sc_no(sc_no):
    """解析 SC-003A / M-011.26 / O-001.1"""
    if not sc_no:
        return None
    m = _SC_NO_RE.match(sc_no.strip())
    if not m:
        return None
    tail = (m.group(4) or '').strip().upper()
    letter = tail if tail.isalpha() and len(tail) <= 2 else None
    sub = int(m.group(3)) if m.group(3) is not None else None
    return {
        'prefix': m.group(1).upper(),
        'main': int(m.group(2)),
        'sub': sub,
        'letter': letter,
        'raw': sc_no.strip(),
    }


def _format_main(prefix, main):
    """與現有編號風格一致：SC/O 用三位，M 亦三位"""
    return f'{prefix.upper()}-{main:03d}'


def suggest_next_sc_no(sc_list, prefix, company=None):
    """
    建議下一個參考編號。
    - 若公司已有同類合同 → 延續子號 (.N) 或字母後綴 (A/B/C)
    - 否則 → 該分類下一個主編號
    回傳 dict: sc_no, reason, linked_company
    """
    prefix = (prefix or 'SC').upper()
    if prefix not in SC_PREFIXES:
        prefix = 'SC'

    all_nos = [
        (sc.get('sc_no') or '').strip()
        for sc in (sc_list or [])
        if (sc.get('sc_no') or '').upper().startswith(prefix + '-')
    ]

    company_nos = []
    if company:
        for sc in sc_list or []:
            if company_matches_sc(sc, company):
                no = (sc.get('sc_no') or '').strip()
                if no.upper().startswith(prefix + '-'):
                    company_nos.append(no)

    if company_nos:
        base = company_nos[0]
        parent = derive_parent_sc_no(base) or base
        siblings = [
            no for no in all_nos
            if no == parent or derive_parent_sc_no(no) == parent
        ]

        letters = []
        subs = []
        parent_parsed = parse_sc_no(parent)
        for no in siblings:
            p = parse_sc_no(no)
            if not p:
                continue
            if p['letter']:
                letters.append(p['letter'])
            if p['sub'] is not None:
                subs.append(p['sub'])

        if letters and parent_parsed:
            nxt = chr(ord(max(letters)) + 1)
            sc_no = f"{parent_parsed['prefix']}-{parent_parsed['main']:03d}{nxt}"
            return {
                'sc_no': sc_no,
                'reason': f'同公司已有 {base}，延續字母後綴',
                'linked_company': True,
                'parent_sc_no': parent,
            }

        if subs and parent_parsed:
            sc_no = f"{parent_parsed['prefix']}-{parent_parsed['main']:03d}.{max(subs) + 1}"
            return {
                'sc_no': sc_no,
                'reason': f'同公司已有 {base}，延續子編號',
                'linked_company': True,
                'parent_sc_no': parent,
            }

        if parent_parsed and base == parent:
            sc_no = f"{parent_parsed['prefix']}-{parent_parsed['main']:03d}A"
            return {
                'sc_no': sc_no,
                'reason': f'同公司已有 {parent}，加字母後綴',
                'linked_company': True,
                'parent_sc_no': parent,
            }

        if parent_parsed:
            sc_no = f"{parent_parsed['prefix']}-{parent_parsed['main']:03d}.1"
            return {
                'sc_no': sc_no,
                'reason': f'同公司已有 {base}，新增子編號',
                'linked_company': True,
                'parent_sc_no': parent,
            }

    main_nums = []
    for no in all_nos:
        p = parse_sc_no(no)
        if p:
            main_nums.append(p['main'])
    next_main = (max(main_nums) + 1) if main_nums else 1
    sc_no = _format_main(prefix, next_main)
    return {
        'sc_no': sc_no,
        'reason': '新分包商，使用下一個主編號',
        'linked_company': False,
        'parent_sc_no': sc_no,
    }
