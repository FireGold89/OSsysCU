"""
database.py — QS付款管理系統資料庫模組
SQLite 資料庫初始化與CRUD操作
"""
import sqlite3
import os
import json
from datetime import datetime

from config import DB_PATH
from sc_ref import derive_parent_sc_no


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """初始化資料庫，建立所有表格"""
    conn = get_conn()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            key   TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS projects (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            project_code     TEXT NOT NULL UNIQUE,
            project_name     TEXT,
            client           TEXT,
            main_contractor  TEXT,
            contract_amount  REAL DEFAULT 0,
            start_date       TEXT,
            status           TEXT DEFAULT 'Active',
            notes            TEXT,
            created_at       TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS subcontractors (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id          INTEGER NOT NULL,
            sc_no               TEXT NOT NULL,
            quotation_no        TEXT,
            company_name_en     TEXT,
            company_name_zh     TEXT,
            description         TEXT,
            contract_amount     REAL DEFAULT 0,
            payment_note        TEXT,
            oa_status           TEXT,
            oa_ref              TEXT,
            oa_no               TEXT,
            quotation_saved     TEXT,
            quotation_date      TEXT,
            created_at          TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            UNIQUE(project_id, sc_no)
        );

        CREATE TABLE IF NOT EXISTS payment_records (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id       INTEGER NOT NULL,
            sc_id            INTEGER,
            seq_no           TEXT,
            invoice_date     TEXT,
            invoice_no       TEXT,
            quotation_no     TEXT,
            sc_no            TEXT,
            company_name_en  TEXT,
            company_name_zh  TEXT,
            description      TEXT,
            contract_amount  REAL DEFAULT 0,
            paid_amount      REAL DEFAULT 0,
            remainder_amount REAL DEFAULT 0,
            oa_ref           TEXT,
            oa_no            TEXT,
            mc_ip_no         TEXT,
            bc_to_sub        TEXT,
            sub_ip_no        TEXT,
            remark           TEXT,
            pdf_path         TEXT,
            ocr_status       TEXT,
            created_at       TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at       TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (sc_id) REFERENCES subcontractors(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS ocr_extractions (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id       INTEGER,
            pdf_filename     TEXT,
            ocr_raw_text     TEXT,
            extracted_json   TEXT,
            confidence       TEXT,
            status           TEXT DEFAULT 'pending',
            created_at       TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (payment_id) REFERENCES payment_records(id) ON DELETE SET NULL
        );
    """)
    conn.commit()
    _migrate_db(conn)
    conn.close()
    print(f"[DB] 資料庫已初始化: {DB_PATH}")


def _migrate_db(conn):
    """增量欄位（舊資料庫相容）"""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(subcontractors)")}
    if 'is_excluded' not in cols:
        conn.execute("ALTER TABLE subcontractors ADD COLUMN is_excluded INTEGER DEFAULT 0")
    cols = {r[1] for r in conn.execute("PRAGMA table_info(projects)")}
    if 'labour_allocation' not in cols:
        conn.execute("ALTER TABLE projects ADD COLUMN labour_allocation REAL DEFAULT 0")
    cols = {r[1] for r in conn.execute("PRAGMA table_info(subcontractors)")}
    if 'oa_date' not in cols:
        conn.execute("ALTER TABLE subcontractors ADD COLUMN oa_date TEXT")
        conn.execute("""
            UPDATE subcontractors SET oa_date = quotation_date
            WHERE oa_date IS NULL AND quotation_date IS NOT NULL AND quotation_date != ''
        """)
    if 'contract_sum' not in cols:
        conn.execute("ALTER TABLE subcontractors ADD COLUMN contract_sum REAL DEFAULT 0")
    if 'vo_amount' not in cols:
        conn.execute("ALTER TABLE subcontractors ADD COLUMN vo_amount REAL DEFAULT 0")
    if 'parent_sc_no' not in cols:
        conn.execute("ALTER TABLE subcontractors ADD COLUMN parent_sc_no TEXT")
    # 舊資料：contract_sum 預設為 contract_amount，補 parent_sc_no
    rows = conn.execute(
        "SELECT id, sc_no, contract_amount, contract_sum FROM subcontractors"
    ).fetchall()
    for row in rows:
        r = dict(row)
        parent = derive_parent_sc_no(r['sc_no'])
        cs = r.get('contract_sum') or 0
        if not cs and r.get('contract_amount'):
            cs = r['contract_amount']
        conn.execute(
            "UPDATE subcontractors SET parent_sc_no=?, contract_sum=? WHERE id=?",
            (parent, cs, r['id'])
        )
    conn.commit()


# ─── Projects ──────────────────────────────────────────────────────────

def get_all_projects():
    conn = get_conn()
    rows = conn.execute("""
        SELECT p.*,
               COUNT(DISTINCT sc.id) AS sc_count,
               SUM(pr.paid_amount)   AS total_paid
        FROM projects p
        LEFT JOIN subcontractors sc ON sc.project_id = p.id
        LEFT JOIN payment_records pr ON pr.project_id = p.id
        GROUP BY p.id
        ORDER BY p.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_project(project_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_project(data):
    conn = get_conn()
    cur = conn.execute("""
        INSERT INTO projects (project_code, project_name, client, main_contractor,
                              contract_amount, labour_allocation, start_date, status, notes)
        VALUES (:project_code, :project_name, :client, :main_contractor,
                :contract_amount, :labour_allocation, :start_date, :status, :notes)
    """, data)
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def update_project(project_id, data):
    conn = get_conn()
    conn.execute("""
        UPDATE projects SET project_code=:project_code, project_name=:project_name,
            client=:client, main_contractor=:main_contractor,
            contract_amount=:contract_amount, labour_allocation=:labour_allocation,
            start_date=:start_date, status=:status, notes=:notes
        WHERE id=:id
    """, {**data, 'id': project_id})
    conn.commit()
    conn.close()


def delete_project(project_id):
    conn = get_conn()
    conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
    conn.commit()
    conn.close()


# ─── Subcontractors ────────────────────────────────────────────────────

def get_subcontractors(project_id):
    conn = get_conn()
    rows = conn.execute("""
        SELECT sc.*,
               COALESCE(SUM(pr.paid_amount), 0) AS total_paid
        FROM subcontractors sc
        LEFT JOIN payment_records pr ON pr.project_id = sc.project_id
            AND (pr.sc_id = sc.id OR pr.sc_no = sc.sc_no)
        WHERE sc.project_id = ?
        GROUP BY sc.id
        ORDER BY COALESCE(sc.parent_sc_no, sc.sc_no), sc.sc_no
    """, (project_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_subcontractor(sc_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM subcontractors WHERE id=?", (sc_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_subcontractor(data):
    """新增或更新分判商"""
    conn = get_conn()
    existing = conn.execute(
        "SELECT id FROM subcontractors WHERE project_id=? AND sc_no=?",
        (data['project_id'], data['sc_no'])
    ).fetchone()

    data.setdefault('parent_sc_no', derive_parent_sc_no(data.get('sc_no')))
    data.setdefault('contract_sum', data.get('contract_amount') or 0)
    data.setdefault('vo_amount', 0)

    if existing:
        conn.execute("""
            UPDATE subcontractors SET
                quotation_no=:quotation_no, company_name_en=:company_name_en,
                company_name_zh=:company_name_zh, description=:description,
                contract_sum=:contract_sum, vo_amount=:vo_amount,
                contract_amount=:contract_amount, parent_sc_no=:parent_sc_no,
                payment_note=:payment_note,
                oa_status=:oa_status, oa_ref=:oa_ref, oa_no=:oa_no,
                quotation_saved=:quotation_saved, quotation_date=:quotation_date,
                oa_date=:oa_date, is_excluded=:is_excluded
            WHERE project_id=:project_id AND sc_no=:sc_no
        """, data)
        sc_id = existing['id']
    else:
        cur = conn.execute("""
            INSERT INTO subcontractors (project_id, sc_no, quotation_no, company_name_en,
                company_name_zh, description, contract_sum, vo_amount, contract_amount,
                parent_sc_no, payment_note,
                oa_status, oa_ref, oa_no, quotation_saved, quotation_date, oa_date, is_excluded)
            VALUES (:project_id, :sc_no, :quotation_no, :company_name_en,
                :company_name_zh, :description, :contract_sum, :vo_amount, :contract_amount,
                :parent_sc_no, :payment_note,
                :oa_status, :oa_ref, :oa_no, :quotation_saved, :quotation_date, :oa_date, :is_excluded)
        """, data)
        sc_id = cur.lastrowid

    conn.commit()
    conn.close()
    return sc_id


def delete_subcontractor(sc_id):
    conn = get_conn()
    conn.execute("DELETE FROM subcontractors WHERE id=?", (sc_id,))
    conn.commit()
    conn.close()


# ─── Payment Records ───────────────────────────────────────────────────

def _payment_seq_sort_key(row):
    """排序用：優先 seq_no，否則用 id"""
    try:
        if row.get('seq_no'):
            return (int(str(row['seq_no']).strip()), row.get('invoice_date') or '', row['id'])
    except (ValueError, TypeError):
        pass
    return (row['id'], row.get('invoice_date') or '', row['id'])


def compact_seq_numbers(project_id):
    """刪除後重新編號為 1, 2, 3… 無空缺"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, seq_no, invoice_date FROM payment_records WHERE project_id = ?",
        (project_id,)
    ).fetchall()
    if not rows:
        conn.close()
        return
    ordered = sorted([dict(r) for r in rows], key=_payment_seq_sort_key)
    for i, row in enumerate(ordered, 1):
        conn.execute(
            "UPDATE payment_records SET seq_no = ? WHERE id = ?",
            (str(i), row['id'])
        )
    conn.commit()
    conn.close()


def ensure_seq_compact(project_id):
    """若最大編號大於筆數（有空缺），自動重新編號"""
    conn = get_conn()
    count = conn.execute(
        "SELECT COUNT(*) FROM payment_records WHERE project_id = ?",
        (project_id,)
    ).fetchone()[0]
    rows = conn.execute(
        "SELECT seq_no, id FROM payment_records WHERE project_id = ?",
        (project_id,)
    ).fetchall()
    conn.close()
    if count == 0:
        return
    max_n = 0
    for r in rows:
        try:
            n = int(r['seq_no']) if r['seq_no'] else int(r['id'])
        except (ValueError, TypeError):
            n = r['id']
        max_n = max(max_n, n)
    if max_n > count:
        compact_seq_numbers(project_id)


def get_next_seq_no(project_id):
    """下一個可用序號（填補空缺後為 count+1）"""
    ensure_seq_compact(project_id)
    conn = get_conn()
    count = conn.execute(
        "SELECT COUNT(*) FROM payment_records WHERE project_id = ?",
        (project_id,)
    ).fetchone()[0]
    conn.close()
    return str(count + 1)


def get_payments(project_id, filters=None):
    ensure_seq_compact(project_id)
    conn = get_conn()
    sql = """
        SELECT pr.*, sc.company_name_en AS sc_company
        FROM payment_records pr
        LEFT JOIN subcontractors sc ON sc.id = pr.sc_id
        WHERE pr.project_id = ?
    """
    params = [project_id]
    if filters:
        if filters.get('sc_no'):
            sql += " AND pr.sc_no = ?"
            params.append(filters['sc_no'])
        elif filters.get('sc_group'):
            grp = filters['sc_group']
            sql += " AND (pr.sc_no = ? OR pr.sc_no LIKE ?)"
            params.extend([grp, grp + '.%'])
        if filters.get('search'):
            sql += " AND (pr.company_name_en LIKE ? OR pr.invoice_no LIKE ? OR pr.description LIKE ?)"
            s = f"%{filters['search']}%"
            params.extend([s, s, s])
    sql += " ORDER BY pr.invoice_date DESC, pr.seq_no"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_payment(payment_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM payment_records WHERE id=?", (payment_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_payment(data):
    conn = get_conn()
    # 計算餘額
    if 'remainder_amount' not in data or data['remainder_amount'] is None:
        ca = float(data.get('contract_amount') or 0)
        pa = float(data.get('paid_amount') or 0)
        data['remainder_amount'] = ca - pa

    if not data.get('seq_no'):
        data['seq_no'] = get_next_seq_no(data['project_id'])

    cur = conn.execute("""
        INSERT INTO payment_records (
            project_id, sc_id, seq_no, invoice_date, invoice_no, quotation_no,
            sc_no, company_name_en, company_name_zh, description,
            contract_amount, paid_amount, remainder_amount,
            oa_ref, oa_no, mc_ip_no, bc_to_sub, sub_ip_no, remark, pdf_path, ocr_status
        ) VALUES (
            :project_id, :sc_id, :seq_no, :invoice_date, :invoice_no, :quotation_no,
            :sc_no, :company_name_en, :company_name_zh, :description,
            :contract_amount, :paid_amount, :remainder_amount,
            :oa_ref, :oa_no, :mc_ip_no, :bc_to_sub, :sub_ip_no, :remark, :pdf_path, :ocr_status
        )
    """, data)
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def update_payment(payment_id, data):
    data['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    data['id'] = payment_id
    conn = get_conn()
    conn.execute("""
        UPDATE payment_records SET
            invoice_date=:invoice_date, invoice_no=:invoice_no, quotation_no=:quotation_no,
            sc_no=:sc_no, company_name_en=:company_name_en, company_name_zh=:company_name_zh,
            description=:description, contract_amount=:contract_amount,
            paid_amount=:paid_amount, remainder_amount=:remainder_amount,
            oa_ref=:oa_ref, oa_no=:oa_no, mc_ip_no=:mc_ip_no,
            bc_to_sub=:bc_to_sub, sub_ip_no=:sub_ip_no, remark=:remark,
            updated_at=:updated_at
        WHERE id=:id
    """, data)
    conn.commit()
    conn.close()


def delete_payment(payment_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT project_id FROM payment_records WHERE id=?", (payment_id,)
    ).fetchone()
    project_id = row['project_id'] if row else None
    conn.execute("DELETE FROM payment_records WHERE id=?", (payment_id,))
    conn.commit()
    conn.close()
    if project_id:
        compact_seq_numbers(project_id)


# ─── Reports ───────────────────────────────────────────────────────────

def get_project_summary(project_id):
    conn = get_conn()

    project = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not project:
        conn.close()
        return None

    # 按分判商統計
    sc_stats = conn.execute("""
        SELECT sc_no, company_name_en, description,
               contract_amount, SUM(paid_amount) AS total_paid,
               (contract_amount - SUM(paid_amount)) AS remainder,
               COUNT(*) AS payment_count
        FROM payment_records
        WHERE project_id = ?
        GROUP BY sc_no
        ORDER BY sc_no
    """, (project_id,)).fetchall()

    # 總計
    totals = conn.execute("""
        SELECT SUM(paid_amount) AS total_paid,
               SUM(remainder_amount) AS total_remainder
        FROM payment_records WHERE project_id=?
    """, (project_id,)).fetchone()

    # Excel Project Summary 右下角結算 (B)(C)(D)(E)
    sc_items = conn.execute("""
        SELECT contract_amount, is_excluded FROM subcontractors WHERE project_id=?
    """, (project_id,)).fetchall()
    sub_total_b = sum(r['contract_amount'] or 0 for r in sc_items if not r['is_excluded'])
    excluded_c = -sum(r['contract_amount'] or 0 for r in sc_items if r['is_excluded'])
    labour = dict(project).get('labour_allocation') or 0
    total_d = sub_total_b + excluded_c + labour
    contract_a = dict(project).get('contract_amount') or 0
    profit_e = contract_a - total_d
    profit_rate = (profit_e / contract_a * 100) if contract_a else 0

    conn.close()
    return {
        'project': dict(project),
        'sc_stats': [dict(r) for r in sc_stats],
        'total_paid': totals['total_paid'] or 0,
        'total_remainder': totals['total_remainder'] or 0,
        'contract_calc': {
            'main_contract_amount': contract_a,
            'sub_total_b': sub_total_b,
            'excluded_c': excluded_c,
            'labour_allocation': labour,
            'total_d': total_d,
            'profit_e': profit_e,
            'profit_rate': round(profit_rate, 1),
        },
    }


# ─── Settings ──────────────────────────────────────────────────────────

def get_setting(key, default=None):
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return row['value'] if row else default


def set_setting(key, value):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?,?)", (key, value))
    conn.commit()
    conn.close()


# ─── OCR Records ───────────────────────────────────────────────────────

def save_ocr_extraction(payment_id, filename, raw_text, extracted_json, confidence, status):
    conn = get_conn()
    cur = conn.execute("""
        INSERT INTO ocr_extractions (payment_id, pdf_filename, ocr_raw_text, extracted_json, confidence, status)
        VALUES (?,?,?,?,?,?)
    """, (payment_id, filename, raw_text, json.dumps(extracted_json, ensure_ascii=False), confidence, status))
    conn.commit()
    ocr_id = cur.lastrowid
    conn.close()
    return ocr_id


if __name__ == '__main__':
    init_db()
    print("[DB] 初始化完成")
