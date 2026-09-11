"""
portfolio.py — 全公司 N 項目結算總表 / 進行中項目

P1：從 projects 補列、進度表 11 欄、FA 左欄。
P2：FA 匯入／匯出、左欄可編、分判槽寫入（矩陣 UI 於 P3）。
P3：分判 FAC 矩陣 15 槽 inline 編輯 + SC 連結 + drawer。
P4：從系統同步衍生欄 + Dashboard KPI stats。
"""
from datetime import datetime, timedelta

import database as db
from database import get_conn
from project_cover import derive_mp_contract_code_variants

SOURCE_SYNC = 'sync-from-projects'
PROGRESS_STATUS_VALUES = ('On Progress', 'Completed')
CLIENT_FAC_STATUS_VALUES = ('On Progress', 'Completed', '待簽')
SC_FAC_STATUS_VALUES = CLIENT_FAC_STATUS_VALUES
MAX_SC_SLOTS = 15

_WRITABLE = (
    'n_code',
    'expected_completion_date',
    'project_progress_status',
    'client_fac_status',
    'portfolio_remark',
    'pc_cert_done',
    'defect_cert_done',
    'dlp_commencement_date',
    'dlp_days',
    'dlp_expiry_date',
)

_COVER_FILL_FIELDS = (
    ('project_manager', 'pm'),
    ('main_contract_commencement_date', 'commencement_date'),
    ('project_completion_date', 'contract_completion_date'),
    ('pc_cert_date', 'pc_date'),
)

_LIST_SQL = """
    SELECT
        pp.id,
        pp.project_id,
        pp.n_code,
        pp.expected_completion_date,
        pp.project_progress_status,
        pp.client_fac_status,
        pp.pc_cert_done,
        pp.defect_cert_done,
        pp.dlp_commencement_date,
        pp.dlp_days,
        pp.dlp_expiry_date,
        pp.retention_to_release,
        pp.portfolio_remark,
        pp.source_file,
        pp.last_import_at,
        pp.updated_at,
        p.project_code,
        p.project_name,
        p.project_name_en,
        p.project_name_zh,
        p.client,
        p.project_manager,
        p.main_contract_commencement_date,
        p.start_date,
        p.project_completion_date,
        p.pc_cert_date,
        p.contract_amount
    FROM portfolio_projects pp
    JOIN projects p ON p.id = pp.project_id
"""


def _blank_to_none(val):
    if val is None:
        return None
    if isinstance(val, str) and not val.strip():
        return None
    return val


def _project_description(row):
    zh = (row['project_name_zh'] or '').strip()
    if zh:
        return zh
    en = (row['project_name_en'] or '').strip()
    if en:
        return en
    return (row['project_name'] or '').strip()


def _bool01(val):
    return bool(val)


def _row_to_item(row, include_subcons=False):
    d = dict(row)
    item = {
        'id': d['id'],
        'project_id': d['project_id'],
        'n_code': d.get('n_code') or '',
        'project_code': d.get('project_code') or '',
        'description': _project_description(d),
        'pm': (d.get('project_manager') or '').strip(),
        'commencement_date': d.get('main_contract_commencement_date') or d.get('start_date'),
        'contract_completion_date': d.get('project_completion_date'),
        'pc_date': d.get('pc_cert_date'),
        'pc_cert_done': _bool01(d.get('pc_cert_done')),
        'dlp_commencement_date': d.get('dlp_commencement_date'),
        'dlp_days': d.get('dlp_days'),
        'dlp_expiry_date': d.get('dlp_expiry_date'),
        'retention_to_release': d.get('retention_to_release'),
        'defect_cert_done': _bool01(d.get('defect_cert_done')),
        'expected_completion_date': d.get('expected_completion_date'),
        'remark': d.get('portfolio_remark') or '',
        'contract_sum': d.get('contract_amount'),
        'project_progress_status': d.get('project_progress_status') or 'On Progress',
        'client': (d.get('client') or '').strip(),
        'client_fac_status': d.get('client_fac_status') or '',
        'source_file': d.get('source_file'),
        'last_import_at': d.get('last_import_at'),
        'updated_at': d.get('updated_at'),
    }
    if include_subcons:
        item['subcontractors'] = []
    return item


def _slots_by_portfolio(conn, ids):
    if not ids:
        return {}
    qmarks = ','.join('?' * len(ids))
    rows = conn.execute(
        f"""SELECT portfolio_project_id, slot_no, subcon_name,
                   subcontractor_id, fac_status
            FROM portfolio_sc_fac_status
            WHERE portfolio_project_id IN ({qmarks})
            ORDER BY slot_no""",
        ids,
    ).fetchall()
    out = {}
    for r in rows:
        out.setdefault(r['portfolio_project_id'], []).append({
            'slot': r['slot_no'],
            'name': r['subcon_name'] or '',
            'fac_status': r['fac_status'] or '',
            'subcontractor_id': r['subcontractor_id'],
        })
    return out


def ensure_rows_from_projects():
    """為尚未有 portfolio 列的 projects 補列；不覆寫已有資料。"""
    conn = get_conn()
    cur = conn.execute("""
        INSERT INTO portfolio_projects (
            project_id, project_progress_status, client_fac_status,
            portfolio_remark, source_file, created_at, updated_at
        )
        SELECT
            p.id,
            'On Progress',
            'On Progress',
            p.notes,
            ?,
            datetime('now', 'localtime'),
            datetime('now', 'localtime')
        FROM projects p
        WHERE NOT EXISTS (
            SELECT 1 FROM portfolio_projects pp WHERE pp.project_id = p.id
        )
    """, (SOURCE_SYNC,))
    created = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
    total = conn.execute("SELECT COUNT(*) FROM portfolio_projects").fetchone()[0]
    conn.commit()
    conn.close()
    return {'created': created, 'total': total}


def _compute_stats(conn):
    row = conn.execute("""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN IFNULL(project_progress_status, '') = 'On Progress' THEN 1 ELSE 0 END) AS on_progress,
            SUM(CASE WHEN IFNULL(project_progress_status, '') = 'Completed' THEN 1 ELSE 0 END) AS completed,
            SUM(CASE WHEN IFNULL(client_fac_status, '') != 'Completed' THEN 1 ELSE 0 END) AS client_fa_pending
        FROM portfolio_projects
    """).fetchone()
    sc_pending = conn.execute("""
        SELECT COUNT(DISTINCT portfolio_project_id) FROM portfolio_sc_fac_status
        WHERE IFNULL(fac_status, '') IN ('On Progress', '待簽')
          AND TRIM(IFNULL(subcon_name, '')) != ''
    """).fetchone()[0]
    dlp_soon = conn.execute("""
        SELECT COUNT(*) FROM portfolio_projects
        WHERE TRIM(IFNULL(dlp_expiry_date, '')) != ''
          AND date(dlp_expiry_date) <= date('now', '+90 days')
    """).fetchone()[0]
    return {
        'total': int(row['total'] or 0),
        'on_progress': int(row['on_progress'] or 0),
        'completed': int(row['completed'] or 0),
        'client_fa_pending': int(row['client_fa_pending'] or 0),
        'sc_fac_pending': int(sc_pending or 0),
        'dlp_soon': int(dlp_soon or 0),
    }


def get_portfolio_stats():
    """全公司 FAC KPI（Dashboard / stats API）。"""
    ensure_rows_from_projects()
    conn = get_conn()
    stats = _compute_stats(conn)
    conn.close()
    return stats


def _pct_number(val):
    if val is None or val == '':
        return None
    try:
        v = float(val)
    except (TypeError, ValueError):
        return None
    if 0 < abs(v) <= 1:
        return v * 100
    return v


def _parse_date_str(date_str):
    s = (date_str or '').strip()
    if not s:
        return None
    for fmt in ('%Y-%m-%d', '%Y/%m/%d'):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return None


def _format_date(d):
    return d.isoformat() if d else None


def _add_days_to_date(date_str, days):
    base = _parse_date_str(date_str)
    if base is None or days is None:
        return None
    try:
        offset = int(days)
    except (TypeError, ValueError):
        return None
    return _format_date(base + timedelta(days=offset))


def _derive_retention_amount(project):
    """Main FAC / Cover → Retention to be released（HK$）。"""
    amt = project.get('retention_max_amount')
    if amt not in (None, '', 0):
        try:
            val = float(amt)
            if val > 0:
                return round(val, 2)
        except (TypeError, ValueError):
            pass
    contract = float(project.get('contract_amount') or 0)
    if contract <= 0:
        return None
    pct = _pct_number(project.get('retention_pct'))
    if pct is None:
        return None
    val = contract * pct / 100.0
    max_pct = _pct_number(project.get('retention_max_pct'))
    if max_pct is not None:
        val = min(val, contract * max_pct / 100.0)
    return round(val, 2) if val > 0 else None


def _norm_sc_name(name):
    return ''.join((name or '').split()).lower()


def _match_subcon_id_fuzzy(conn, project_id, name):
    """Exact match first, then normalized contains match."""
    mid = _match_subcon_id(conn, project_id, name)
    if mid:
        return mid
    target = _norm_sc_name(name)
    if not target:
        return None
    rows = conn.execute(
        """SELECT id, company_name_zh, company_name_en
           FROM subcontractors WHERE project_id=?""",
        (project_id,),
    ).fetchall()
    for row in rows:
        for col in ('company_name_zh', 'company_name_en'):
            cand = _norm_sc_name(row[col])
            if not cand:
                continue
            if cand == target or cand in target or target in cand:
                return row['id']
    return None


def _sync_sc_slots_from_subcontractors(conn, portfolio_id, project_id):
    """連結 Excel 名稱 ↔ 系統分判；僅填空白槽；不覆寫 fac_status 或已有名稱。"""
    subs = conn.execute(
        """SELECT id, company_name_zh, company_name_en
           FROM subcontractors
           WHERE project_id=?
           ORDER BY sc_no COLLATE NOCASE""",
        (project_id,),
    ).fetchall()
    existing = {
        r['slot_no']: dict(r)
        for r in conn.execute(
            """SELECT slot_no, subcon_name, fac_status, subcontractor_id
               FROM portfolio_sc_fac_status
               WHERE portfolio_project_id=?""",
            (portfolio_id,),
        ).fetchall()
    }
    linked = 0
    used_sub_ids = set()
    used_names = set()
    for slot_no in range(1, MAX_SC_SLOTS + 1):
        ex = existing.get(slot_no)
        if not ex:
            continue
        name = (ex.get('subcon_name') or '').strip()
        sc_id = ex.get('subcontractor_id')
        if name:
            used_names.add(_norm_sc_name(name))
        if sc_id:
            used_sub_ids.add(int(sc_id))
            continue
        if not name:
            continue
        mid = _match_subcon_id_fuzzy(conn, project_id, name)
        if not mid:
            continue
        conn.execute(
            """UPDATE portfolio_sc_fac_status
               SET subcontractor_id=?
               WHERE portfolio_project_id=? AND slot_no=?""",
            (mid, portfolio_id, slot_no),
        )
        used_sub_ids.add(int(mid))
        linked += 1

    empty_slots = []
    for slot_no in range(1, MAX_SC_SLOTS + 1):
        ex = existing.get(slot_no)
        if ex and (ex.get('subcon_name') or '').strip():
            continue
        empty_slots.append(slot_no)

    if not subs:
        return {
            'filled': 0,
            'linked': linked,
            'empty_slots': len(empty_slots),
            'no_system_sc': bool(empty_slots),
        }

    available_subs = []
    for sub in subs:
        sc_id = int(sub['id'])
        if sc_id in used_sub_ids:
            continue
        name = (sub['company_name_zh'] or sub['company_name_en'] or '').strip()
        if not name:
            continue
        if _norm_sc_name(name) in used_names:
            continue
        available_subs.append(sub)

    filled = 0
    for slot_no, sub in zip(empty_slots, available_subs):
        name = (sub['company_name_zh'] or sub['company_name_en'] or '').strip()
        sc_id = sub['id']
        ex = existing.get(slot_no)
        if ex:
            conn.execute(
                """UPDATE portfolio_sc_fac_status
                   SET subcon_name=?, subcontractor_id=?
                   WHERE portfolio_project_id=? AND slot_no=?""",
                (name, sc_id, portfolio_id, slot_no),
            )
        else:
            conn.execute(
                """INSERT INTO portfolio_sc_fac_status
                   (portfolio_project_id, slot_no, subcon_name, subcontractor_id, fac_status)
                   VALUES (?, ?, ?, ?, NULL)""",
                (portfolio_id, slot_no, name, sc_id),
            )
        filled += 1

    return {
        'filled': filled,
        'linked': linked,
        'empty_slots': max(0, len(empty_slots) - filled),
        'no_system_sc': False,
    }


def sync_from_system():
    """P4：補列 + 衍生 PC/Defect Cert、Retention、DLP；空槽填分判名；保留手填狀態。"""
    base = ensure_rows_from_projects()
    stats = {
        'created': base['created'],
        'total': base['total'],
        'portfolio_updated': 0,
        'pc_cert_synced': 0,
        'defect_cert_synced': 0,
        'retention_synced': 0,
        'dlp_filled': 0,
        'expected_completion_filled': 0,
        'sc_slots_filled': 0,
        'sc_slots_linked': 0,
        'projects_no_system_sc': 0,
    }
    conn = get_conn()
    rows = conn.execute("""
        SELECT
            pp.id,
            pp.project_id,
            pp.dlp_commencement_date,
            pp.dlp_days,
            pp.dlp_expiry_date,
            pp.expected_completion_date,
            pp.pc_cert_done,
            pp.defect_cert_done,
            pp.retention_to_release,
            p.fac_pc_cert_path,
            p.fac_mg_cert_path,
            p.pc_cert_date,
            p.dlp_cert_date,
            p.dlp_period_months,
            p.project_completion_date,
            p.contract_amount,
            p.retention_pct,
            p.retention_max_pct,
            p.retention_max_amount
        FROM portfolio_projects pp
        JOIN projects p ON p.id = pp.project_id
    """).fetchall()
    for row in rows:
        r = dict(row)
        portfolio_id = r['id']
        updates = {}

        pc_done = 1 if (r.get('fac_pc_cert_path') or '').strip() else 0
        if int(r.get('pc_cert_done') or 0) != pc_done:
            updates['pc_cert_done'] = pc_done
            stats['pc_cert_synced'] += 1

        def_done = 1 if (r.get('fac_mg_cert_path') or '').strip() else 0
        if int(r.get('defect_cert_done') or 0) != def_done:
            updates['defect_cert_done'] = def_done
            stats['defect_cert_synced'] += 1

        retention = _derive_retention_amount(r)
        if retention is not None and retention != r.get('retention_to_release'):
            updates['retention_to_release'] = retention
            stats['retention_synced'] += 1

        if not r.get('dlp_days'):
            months = r.get('dlp_period_months')
            if months:
                try:
                    updates['dlp_days'] = int(months) * 30
                    stats['dlp_filled'] += 1
                except (TypeError, ValueError):
                    pass

        if not (r.get('dlp_commencement_date') or '').strip():
            comm = None
            if (r.get('pc_cert_date') or '').strip():
                comm = _add_days_to_date(r['pc_cert_date'], 1)
            elif (r.get('dlp_cert_date') or '').strip():
                comm = r['dlp_cert_date']
            if comm:
                updates['dlp_commencement_date'] = comm
                stats['dlp_filled'] += 1

        if not (r.get('dlp_expiry_date') or '').strip():
            comm = updates.get('dlp_commencement_date') or r.get('dlp_commencement_date')
            days = updates.get('dlp_days') or r.get('dlp_days')
            if comm and days:
                expiry = _add_days_to_date(comm, days)
                if expiry:
                    updates['dlp_expiry_date'] = expiry
                    stats['dlp_filled'] += 1

        if not (r.get('expected_completion_date') or '').strip():
            comp = (r.get('project_completion_date') or '').strip()
            if comp:
                updates['expected_completion_date'] = comp
                stats['expected_completion_filled'] += 1

        if updates:
            sets = [f'{k}=?' for k in updates]
            sets.append("updated_at=datetime('now', 'localtime')")
            conn.execute(
                f"UPDATE portfolio_projects SET {', '.join(sets)} WHERE id=?",
                list(updates.values()) + [portfolio_id],
            )
            stats['portfolio_updated'] += 1

        sc_sync = _sync_sc_slots_from_subcontractors(
            conn, portfolio_id, r['project_id'],
        )
        stats['sc_slots_filled'] += sc_sync.get('filled', 0)
        stats['sc_slots_linked'] += sc_sync.get('linked', 0)
        if sc_sync.get('no_system_sc') and sc_sync.get('empty_slots'):
            stats['projects_no_system_sc'] += 1

    conn.commit()
    conn.close()
    return stats


def get_portfolio_by_project_id(project_id, include_subcons=True):
    ensure_rows_from_projects()
    conn = get_conn()
    row = conn.execute(
        _LIST_SQL + " WHERE pp.project_id = ?",
        (project_id,),
    ).fetchone()
    if not row:
        conn.close()
        return None
    item = _row_to_item(row, include_subcons=include_subcons)
    if include_subcons:
        item['subcontractors'] = _slots_by_portfolio(conn, [item['id']]).get(item['id'], [])
    conn.close()
    return item


def _pm_options(conn):
    rows = conn.execute("""
        SELECT DISTINCT TRIM(p.project_manager) AS pm
        FROM portfolio_projects pp
        JOIN projects p ON p.id = pp.project_id
        WHERE TRIM(IFNULL(p.project_manager, '')) != ''
        ORDER BY pm COLLATE NOCASE
    """).fetchall()
    return [r['pm'] for r in rows]


def list_portfolio(status=None, pm=None, q=None, include_subcons=False):
    """列出 portfolio 列（先補缺）。status: all | On Progress | Completed"""
    ensure_rows_from_projects()
    conn = get_conn()
    where = []
    params = []
    status_key = (status or '').strip()
    if status_key and status_key.lower() != 'all':
        where.append("pp.project_progress_status = ?")
        params.append(status_key)
    pm_key = (pm or '').strip()
    if pm_key:
        where.append("TRIM(IFNULL(p.project_manager, '')) = ?")
        params.append(pm_key)
    q_key = (q or '').strip()
    if q_key:
        like = f'%{q_key}%'
        where.append("""(
            IFNULL(p.project_code, '') LIKE ?
            OR IFNULL(p.project_name_zh, '') LIKE ?
            OR IFNULL(p.project_name_en, '') LIKE ?
            OR IFNULL(p.project_name, '') LIKE ?
            OR IFNULL(p.client, '') LIKE ?
            OR IFNULL(pp.n_code, '') LIKE ?
        )""")
        params.extend([like] * 6)
    sql = _LIST_SQL
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += """
        ORDER BY
            CASE WHEN IFNULL(pp.n_code, '') = '' THEN 1 ELSE 0 END,
            pp.n_code COLLATE NOCASE,
            p.project_code COLLATE NOCASE
    """
    rows = conn.execute(sql, params).fetchall()
    stats = _compute_stats(conn)
    pms = _pm_options(conn)
    last_import = _latest_import(conn)
    slot_map = {}
    if include_subcons:
        slot_map = _slots_by_portfolio(conn, [r['id'] for r in rows])
    conn.close()
    items = [_row_to_item(r, include_subcons=include_subcons) for r in rows]
    if include_subcons:
        for item in items:
            item['subcontractors'] = slot_map.get(item['id'], [])
    return {'items': items, 'stats': stats, 'pms': pms, 'last_import': last_import}


def get_portfolio_item(portfolio_id, include_subcons=False):
    conn = get_conn()
    row = conn.execute(_LIST_SQL + " WHERE pp.id = ?", (portfolio_id,)).fetchone()
    if not row:
        conn.close()
        return None
    item = _row_to_item(row, include_subcons=include_subcons)
    if include_subcons:
        item['subcontractors'] = _slots_by_portfolio(conn, [portfolio_id]).get(portfolio_id, [])
    conn.close()
    return item


def update_portfolio(portfolio_id, data):
    """更新 P1 可編欄；回傳更新後的列。"""
    if not get_portfolio_item(portfolio_id):
        raise ValueError('記錄不存在')
    payload = data or {}
    fields = []
    params = []
    for key in _WRITABLE:
        if key not in payload:
            continue
        val = _blank_to_none(payload.get(key))
        if key in ('pc_cert_done', 'defect_cert_done'):
            raw = payload.get(key)
            val = 1 if raw in (True, 1, '1', 'true', 'True', '✔') else 0
        if key == 'dlp_days' and val is not None:
            try:
                val = int(float(val))
            except (TypeError, ValueError):
                raise ValueError('DLP (日) 須為整數')
        if key == 'project_progress_status' and val is not None:
            if val not in PROGRESS_STATUS_VALUES:
                raise ValueError('項目狀態須為 On Progress 或 Completed')
        if key == 'client_fac_status' and val is not None:
            if val not in CLIENT_FAC_STATUS_VALUES:
                raise ValueError('Client FA 狀態須為 Completed、On Progress 或 待簽')
        fields.append(f"{key} = ?")
        params.append(val)
    if not fields:
        return get_portfolio_item(portfolio_id, include_subcons=True)
    fields.append("updated_at = datetime('now', 'localtime')")
    params.append(portfolio_id)
    conn = get_conn()
    conn.execute(
        f"UPDATE portfolio_projects SET {', '.join(fields)} WHERE id = ?",
        params,
    )
    conn.commit()
    conn.close()
    return get_portfolio_item(portfolio_id, include_subcons=True)


def update_sc_status(portfolio_id, slots_data):
    """更新分判 FAC 矩陣（1..15 槽）；name 與 fac_status 皆空則刪除該槽。"""
    base = get_portfolio_item(portfolio_id)
    if not base:
        raise ValueError('記錄不存在')
    project_id = base['project_id']
    slots = slots_data or []
    if not isinstance(slots, list):
        raise ValueError('slots 須為陣列')
    conn = get_conn()
    touched = 0
    for sl in slots:
        try:
            slot_no = int(sl.get('slot') or 0)
        except (TypeError, ValueError):
            raise ValueError('slot 須為 1–15 的整數')
        if slot_no < 1 or slot_no > MAX_SC_SLOTS:
            raise ValueError('slot 須為 1–15')
        name = (sl.get('name') or '').strip()
        status = (sl.get('fac_status') or '').strip()
        if status and status not in SC_FAC_STATUS_VALUES:
            raise ValueError('分判 FAC 狀態須為 Completed、On Progress 或 待簽')
        if not name and not status:
            conn.execute(
                "DELETE FROM portfolio_sc_fac_status "
                "WHERE portfolio_project_id=? AND slot_no=?",
                (portfolio_id, slot_no),
            )
            touched += 1
            continue
        sc_id = sl.get('subcontractor_id')
        if sc_id is not None and sc_id != '':
            try:
                sc_id = int(sc_id)
            except (TypeError, ValueError):
                raise ValueError('subcontractor_id 須為整數')
            row = conn.execute(
                "SELECT id FROM subcontractors WHERE id=? AND project_id=?",
                (sc_id, project_id),
            ).fetchone()
            if not row:
                raise ValueError('分判不存在或不屬於此項目')
        else:
            sc_id = _match_subcon_id(conn, project_id, name)
        existing = conn.execute(
            "SELECT id FROM portfolio_sc_fac_status "
            "WHERE portfolio_project_id=? AND slot_no=?",
            (portfolio_id, slot_no),
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE portfolio_sc_fac_status
                   SET subcon_name=?, subcontractor_id=?, fac_status=?
                   WHERE id=?""",
                (name or None, sc_id, status or None, existing['id']),
            )
        else:
            conn.execute(
                """INSERT INTO portfolio_sc_fac_status
                   (portfolio_project_id, slot_no, subcon_name, subcontractor_id, fac_status)
                   VALUES (?, ?, ?, ?, ?)""",
                (portfolio_id, slot_no, name or None, sc_id, status or None),
            )
        touched += 1
    if touched:
        conn.execute(
            "UPDATE portfolio_projects SET updated_at=datetime('now', 'localtime') WHERE id=?",
            (portfolio_id,),
        )
    conn.commit()
    conn.close()
    return get_portfolio_item(portfolio_id, include_subcons=True)


def _latest_import(conn, import_type=None):
    if import_type:
        row = conn.execute(
            """SELECT import_type, filename, rows_read, rows_upserted, imported_at
               FROM portfolio_imports WHERE import_type=?
               ORDER BY id DESC LIMIT 1""",
            (import_type,),
        ).fetchone()
    else:
        row = conn.execute(
            """SELECT import_type, filename, rows_read, rows_upserted, imported_at
               FROM portfolio_imports ORDER BY id DESC LIMIT 1"""
        ).fetchone()
    if not row:
        return None
    return dict(row)


def record_import(import_type, filename, rows_read, rows_upserted):
    conn = get_conn()
    cur = conn.execute(
        """INSERT INTO portfolio_imports
           (import_type, filename, rows_read, rows_upserted, imported_at)
           VALUES (?, ?, ?, ?, datetime('now', 'localtime'))""",
        (import_type, filename, rows_read, rows_upserted),
    )
    conn.commit()
    rec = conn.execute(
        "SELECT import_type, filename, rows_read, rows_upserted, imported_at "
        "FROM portfolio_imports WHERE id=?",
        (cur.lastrowid,),
    ).fetchone()
    conn.close()
    return dict(rec) if rec else {}


def _code_keys(code):
    keys = set()
    s = (code or '').strip()
    if not s:
        return keys
    keys.add(s.upper())
    for v in derive_mp_contract_code_variants(s, s):
        keys.add(v.upper())
    return keys


def find_project_id_for_code(project_code):
    """Q1059_25 / MS/Q1059/25/dc / Q0116_24 ↔ projects.project_code／mp_contract_code。"""
    keys = _code_keys(project_code)
    if not keys:
        return None
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, project_code, mp_contract_code, quotation_no FROM projects"
    ).fetchall()
    mp_rows = conn.execute(
        "SELECT project_id, mp_contract_code FROM project_mp_contracts"
    ).fetchall()
    conn.close()
    index = {}
    for r in rows:
        for src in (r['project_code'], r['mp_contract_code'], r['quotation_no']):
            for k in _code_keys(src):
                index.setdefault(k, r['id'])
    for r in mp_rows:
        for k in _code_keys(r['mp_contract_code']):
            index.setdefault(k, r['project_id'])
    for k in keys:
        if k in index:
            return index[k]
    return None


def _fill_cover_if_empty(conn, project_id, parsed):
    row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not row:
        return
    proj = dict(row)
    sets = []
    params = []
    for col, src in _COVER_FILL_FIELDS:
        incoming = _blank_to_none(parsed.get(src))
        if not incoming:
            continue
        existing = (proj.get(col) or '')
        if isinstance(existing, str):
            existing = existing.strip()
        if existing:
            continue
        sets.append(f"{col}=?")
        params.append(incoming)
    client = _blank_to_none(parsed.get('client'))
    if client and not (proj.get('client') or '').strip():
        sets.append('client=?')
        params.append(client)
    desc = _blank_to_none(parsed.get('description'))
    if desc and not (proj.get('project_name_zh') or '').strip():
        sets.append('project_name_zh=?')
        params.append(desc)
        if not (proj.get('project_name') or '').strip():
            sets.append('project_name=?')
            params.append(desc)
    amount = parsed.get('contract_sum')
    if amount not in (None, '') and not float(proj.get('contract_amount') or 0):
        sets.append('contract_amount=?')
        params.append(float(amount))
    mp = None
    variants = derive_mp_contract_code_variants(parsed.get('project_code'), parsed.get('project_code'))
    if variants and not (proj.get('mp_contract_code') or '').strip():
        mp = variants[0]
        sets.append('mp_contract_code=?')
        params.append(mp)
    if not sets:
        return
    params.append(project_id)
    conn.execute(f"UPDATE projects SET {', '.join(sets)} WHERE id=?", params)


def _create_placeholder_project(parsed):
    code = (parsed.get('project_code') or '').strip()
    desc = (parsed.get('description') or '').strip()
    payload = {
        'project_code': code,
        'project_name': desc or code,
        'project_name_zh': desc or None,
        'project_name_en': None,
        'client': parsed.get('client') or '',
        'main_contractor': '',
        'contract_amount': parsed.get('contract_sum') or 0,
        'start_date': parsed.get('commencement_date'),
        'status': 'Active',
        'notes': '由 FA 清單匯入',
        'project_manager': parsed.get('pm'),
        'main_contract_commencement_date': parsed.get('commencement_date'),
        'project_completion_date': parsed.get('contract_completion_date'),
        'pc_cert_date': parsed.get('pc_date'),
        'mp_contract_code': (
            derive_mp_contract_code_variants(code, code) or [None]
        )[0],
    }
    try:
        return db.create_project(payload)
    except Exception:
        return find_project_id_for_code(code)


def _match_subcon_id(conn, project_id, name):
    n = (name or '').strip()
    if not n:
        return None
    row = conn.execute(
        """SELECT id FROM subcontractors
           WHERE project_id=? AND (
             TRIM(IFNULL(company_name_zh, '')) = ?
             OR TRIM(IFNULL(company_name_en, '')) = ?
           ) LIMIT 1""",
        (project_id, n, n),
    ).fetchone()
    return row['id'] if row else None


def _replace_sc_slots(conn, portfolio_id, project_id, slots):
    conn.execute(
        "DELETE FROM portfolio_sc_fac_status WHERE portfolio_project_id=?",
        (portfolio_id,),
    )
    written = 0
    for sl in slots or []:
        name = (sl.get('name') or '').strip()
        status = (sl.get('fac_status') or '').strip()
        slot_no = int(sl.get('slot') or 0)
        if slot_no < 1 or slot_no > 15:
            continue
        if not name and not status:
            continue
        sc_id = _match_subcon_id(conn, project_id, name)
        conn.execute(
            """INSERT INTO portfolio_sc_fac_status
               (portfolio_project_id, slot_no, subcon_name, subcontractor_id, fac_status)
               VALUES (?, ?, ?, ?, ?)""",
            (portfolio_id, slot_no, name or None, sc_id, status or None),
        )
        written += 1
    return written


def upsert_from_import(parsed, create_placeholder=True, write_slots=True, source_file=None):
    """以 Excel 列 upsert portfolio_projects；可建 placeholder 項目。"""
    code = (parsed.get('project_code') or '').strip()
    if not code:
        return {'action': 'skipped'}
    created_project = False
    project_id = find_project_id_for_code(code)
    if not project_id:
        if not create_placeholder:
            return {'action': 'skipped', 'project_code': code}
        project_id = _create_placeholder_project(parsed)
        if not project_id:
            return {'action': 'skipped', 'project_code': code}
        created_project = True
    conn = get_conn()
    _fill_cover_if_empty(conn, project_id, parsed)
    existing = conn.execute(
        "SELECT id FROM portfolio_projects WHERE project_id=?",
        (project_id,),
    ).fetchone()
    fields = {
        'n_code': _blank_to_none(parsed.get('n_code')),
        'expected_completion_date': _blank_to_none(parsed.get('expected_completion_date')),
        'project_progress_status': parsed.get('project_progress_status') or 'On Progress',
        'client_fac_status': parsed.get('client_fac_status') or 'On Progress',
        'portfolio_remark': parsed.get('remark') or None,
        'source_file': source_file,
        'last_import_at': None,
    }
    if parsed.get('pc_cert_done') is not None:
        fields['pc_cert_done'] = 1 if parsed.get('pc_cert_done') else 0
    if parsed.get('defect_cert_done') is not None:
        fields['defect_cert_done'] = 1 if parsed.get('defect_cert_done') else 0
    for key in (
        'dlp_commencement_date', 'dlp_days', 'dlp_expiry_date', 'retention_to_release',
    ):
        if parsed.get(key) is not None:
            fields[key] = parsed.get(key)
    if existing:
        pid = existing['id']
        sets = [
            'expected_completion_date=?',
            'project_progress_status=?',
            'portfolio_remark=?',
            'source_file=?',
            "last_import_at=datetime('now', 'localtime')",
            "updated_at=datetime('now', 'localtime')",
        ]
        params = [
            fields['expected_completion_date'],
            fields['project_progress_status'],
            fields['portfolio_remark'],
            fields['source_file'],
        ]
        if parsed.get('n_code') is not None:
            sets.insert(0, 'n_code=?')
            params.insert(0, fields['n_code'])
        if parsed.get('client_fac_status'):
            sets.insert(0, 'client_fac_status=?')
            params.insert(0, fields['client_fac_status'])
        extra_map = {
            'pc_cert_done': 'pc_cert_done=?',
            'defect_cert_done': 'defect_cert_done=?',
            'dlp_commencement_date': 'dlp_commencement_date=?',
            'dlp_days': 'dlp_days=?',
            'dlp_expiry_date': 'dlp_expiry_date=?',
            'retention_to_release': 'retention_to_release=?',
        }
        for key, sql_frag in extra_map.items():
            if key in fields:
                sets.insert(-2, sql_frag)
                params.append(fields[key])
        params.append(pid)
        conn.execute(
            f"UPDATE portfolio_projects SET {', '.join(sets)} WHERE id=?",
            params,
        )
    else:
        cur = conn.execute(
            """INSERT INTO portfolio_projects (
                   project_id, n_code, expected_completion_date,
                   project_progress_status, client_fac_status,
                   pc_cert_done, defect_cert_done,
                   dlp_commencement_date, dlp_days, dlp_expiry_date,
                   retention_to_release, portfolio_remark, source_file,
                   last_import_at, created_at, updated_at
               ) VALUES (
                   ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                   datetime('now', 'localtime'),
                   datetime('now', 'localtime'),
                   datetime('now', 'localtime')
               )""",
            (
                project_id, fields['n_code'], fields['expected_completion_date'],
                fields['project_progress_status'], fields['client_fac_status'],
                fields.get('pc_cert_done') or 0, fields.get('defect_cert_done') or 0,
                fields.get('dlp_commencement_date'), fields.get('dlp_days'),
                fields.get('dlp_expiry_date'), fields.get('retention_to_release'),
                fields['portfolio_remark'], fields['source_file'],
            ),
        )
        pid = cur.lastrowid
    slots_n = 0
    if write_slots:
        slots_n = _replace_sc_slots(conn, pid, project_id, parsed.get('subcontractors'))
    conn.commit()
    conn.close()
    return {
        'action': 'upserted',
        'id': pid,
        'project_id': project_id,
        'created_project': created_project,
        'slots': slots_n,
    }
