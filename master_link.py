"""
master_link.py — Master List 報價 ↔ 工程項目自動配對

比對優先序：
  1. projects.project_code 完全一致（含 / 與 _ 變體）
  2. projects.quotation_no 一致
  3. MP 合約編號 Q####_##（4 位補零，如 MS/Q178/25 → Q0178_25）
  4. MP 合約清單 project_mp_contracts（完全一致，含同一會計項目下多個 MP）
  5. project_core（MS_Q0925_26）
"""
from __future__ import annotations

from project_cover import derive_mp_contract_code_variants
from sc_contract_ref import _project_core


def _norm_code(val) -> str:
    return (val or '').strip().upper()


def _single_project_id(rows, ambiguous_reason: str) -> tuple[int | None, str]:
    pids = list(dict.fromkeys(r['project_id'] for r in rows))
    if len(pids) == 1:
        return pids[0], ''
    if len(pids) > 1:
        return None, ambiguous_reason
    return None, 'no_match'


def _find_via_mp_contracts(conn, mp_u: str) -> tuple[int | None, str]:
    """同一會計項目（如 N23）可有多個 MP 合約編號"""
    rows = conn.execute(
        "SELECT DISTINCT project_id FROM project_mp_contracts WHERE UPPER(mp_contract_code)=?",
        (mp_u,),
    ).fetchall()
    pid, reason = _single_project_id(rows, 'ambiguous_mp')
    if pid:
        return pid, 'mp_contracts'
    if reason == 'ambiguous_mp':
        return None, 'ambiguous_mp'
    return None, 'no_match'


def _code_variants(val) -> set[str]:
    s = (val or '').strip()
    if not s:
        return set()
    out = {_norm_code(s)}
    out.add(_norm_code(s.replace('/', '_')))
    out.add(_norm_code(s.replace('_', '/')))
    return {x for x in out if x}


def find_project_for_quotation(quotation_no, conn) -> tuple[int | None, str]:
    """回傳 (project_id, reason)；reason 含 matched / ambiguous_* / no_match"""
    q = (quotation_no or '').strip()
    if not q:
        return None, 'no_match'

    variants = _code_variants(q)
    placeholders = ','.join('?' * len(variants))
    if variants:
        row = conn.execute(
            f"SELECT id FROM projects WHERE UPPER(project_code) IN ({placeholders}) LIMIT 2",
            tuple(variants),
        ).fetchall()
        if len(row) == 1:
            return row[0]['id'], 'project_code'
        if len(row) > 1:
            return None, 'ambiguous_code'

    q_upper = _norm_code(q)
    row = conn.execute(
        "SELECT id FROM projects WHERE UPPER(quotation_no)=? LIMIT 2",
        (q_upper,),
    ).fetchall()
    if len(row) == 1:
        return row[0]['id'], 'quotation_no'
    if len(row) > 1:
        return None, 'ambiguous_quotation'

    mp_variants = derive_mp_contract_code_variants(q, q)
    for mp in mp_variants:
        mp_u = mp.upper()
        row = conn.execute(
            """
            SELECT id FROM projects
            WHERE UPPER(COALESCE(mp_contract_code, ''))=? OR UPPER(project_code)=?
            LIMIT 2
            """,
            (mp_u, mp_u),
        ).fetchall()
        if len(row) == 1:
            return row[0]['id'], 'mp_code'
        if len(row) > 1:
            return None, 'ambiguous_mp'

        pid, reason = _find_via_mp_contracts(conn, mp_u)
        if pid:
            return pid, reason
        if reason == 'ambiguous_mp':
            return None, reason

    core = _project_core(q)
    if core:
        hits = []
        for prow in conn.execute(
            "SELECT id, project_code, quotation_no FROM projects"
        ).fetchall():
            matched = False
            for field in (prow['project_code'], prow['quotation_no']):
                if field and _project_core(field) == core:
                    matched = True
                    break
            if matched:
                hits.append(prow['id'])
        hits = list(dict.fromkeys(hits))
        if len(hits) == 1:
            return hits[0], 'project_core'
        if len(hits) > 1:
            return None, 'ambiguous_core'

    return None, 'no_match'


REASON_LABELS = {
    'project_code': '項目代碼一致',
    'quotation_no': '報價編號一致',
    'mp_code': 'MP 合約編號',
    'mp_contracts': 'MP 合約清單',
    'project_core': '項目核心編號',
    'ambiguous_code': '多個項目代碼相符',
    'ambiguous_quotation': '多個報價編號相符',
    'ambiguous_mp': '多個 MP 編號相符',
    'ambiguous_core': '多個核心編號相符',
    'no_match': '找不到相符項目',
    'already_linked': '已配對',
}


def auto_link_quotations(conn, *, source_year=None, dry_run=True, limit=5000):
    sql = """
        SELECT id, quotation_no, project_id, site_name, source_year
        FROM quotation_registry
        WHERE project_id IS NULL
    """
    params: list = []
    if source_year is not None:
        sql += " AND source_year=?"
        params.append(int(source_year))
    sql += " ORDER BY quote_date DESC, quotation_no LIMIT ?"
    params.append(int(limit))

    rows = conn.execute(sql, params).fetchall()
    projects = {
        r['id']: dict(r)
        for r in conn.execute(
            "SELECT id, project_code, project_name, project_name_zh, quotation_no FROM projects"
        ).fetchall()
    }

    matched = []
    skipped = []
    linked = 0

    for row in rows:
        qno = row['quotation_no']
        pid, reason = find_project_for_quotation(qno, conn)
        if pid:
            proj = projects.get(pid, {})
            item = {
                'quotation_no': qno,
                'quotation_id': row['id'],
                'project_id': pid,
                'project_code': proj.get('project_code'),
                'project_name': proj.get('project_name_zh') or proj.get('project_name'),
                'site_name': row['site_name'] if 'site_name' in row.keys() else None,
                'reason': reason,
                'reason_label': REASON_LABELS.get(reason, reason),
            }
            matched.append(item)
            if not dry_run:
                from database import link_quotation_to_project
                link_quotation_to_project(qno, pid, sync_project_code=True)
                linked += 1
        else:
            skipped.append({
                'quotation_no': qno,
                'quotation_id': row['id'],
                'site_name': row['site_name'] if 'site_name' in row.keys() else None,
                'reason': reason,
                'reason_label': REASON_LABELS.get(reason, reason),
            })

    return {
        'dry_run': dry_run,
        'source_year': source_year,
        'scanned': len(rows),
        'matched_count': len(matched),
        'skipped_count': len(skipped),
        'linked': linked if not dry_run else 0,
        'matched': matched,
        'skipped': skipped,
        'matched_sample': matched[:30],
        'skipped_sample': skipped[:20],
    }
