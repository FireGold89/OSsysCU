"""參考編號工具 — 父級分組（M-011.26 → M-011）"""
import re


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
