"""
database.py — QS付款管理系統資料庫模組
SQLite 資料庫初始化與CRUD操作
"""
import sqlite3
import os
import json
from datetime import datetime

from config import DB_PATH
from sc_ref import derive_parent_sc_no, suggest_next_sc_no


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

        CREATE TABLE IF NOT EXISTS interim_payments (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id            INTEGER NOT NULL,
            ip_no                 TEXT NOT NULL,
            seq_no                INTEGER DEFAULT 0,
            applied_date          TEXT,
            application_amount    REAL DEFAULT 0,
            application_pct       REAL,
            certified_income      REAL DEFAULT 0,
            certified_income_pct  REAL,
            certificate_date      TEXT,
            subcon_paid           REAL DEFAULT 0,
            subcon_paid_pct       REAL,
            subcon_cert_date      TEXT,
            created_at            TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            UNIQUE(project_id, ip_no)
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
    if 'site_period_text' not in cols:
        conn.execute("ALTER TABLE projects ADD COLUMN site_period_text TEXT")
    if 'ip_total_income' not in cols:
        conn.execute("ALTER TABLE projects ADD COLUMN ip_total_income REAL DEFAULT 0")
    if 'ip_total_expenditure' not in cols:
        conn.execute("ALTER TABLE projects ADD COLUMN ip_total_expenditure REAL DEFAULT 0")
    if 'ip_advance' not in cols:
        conn.execute("ALTER TABLE projects ADD COLUMN ip_advance REAL DEFAULT 0")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS interim_payments (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id            INTEGER NOT NULL,
            ip_no                 TEXT NOT NULL,
            seq_no                INTEGER DEFAULT 0,
            applied_date          TEXT,
            application_amount    REAL DEFAULT 0,
            application_pct       REAL,
            certified_income      REAL DEFAULT 0,
            certified_income_pct  REAL,
            certificate_date      TEXT,
            subcon_paid           REAL DEFAULT 0,
            subcon_paid_pct       REAL,
            subcon_cert_date      TEXT,
            created_at            TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            UNIQUE(project_id, ip_no)
        )
    """)
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sc_documents (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id          INTEGER NOT NULL,
            sc_id               INTEGER,
            sc_no               TEXT,
            doc_type            TEXT NOT NULL,
            file_path           TEXT NOT NULL,
            original_filename   TEXT,
            ocr_id              INTEGER,
            created_at          TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (sc_id) REFERENCES subcontractors(id) ON DELETE SET NULL
        )
    """)
    ocr_cols = {r[1] for r in conn.execute("PRAGMA table_info(ocr_extractions)")}
    if 'project_id' not in ocr_cols:
        conn.execute("ALTER TABLE ocr_extractions ADD COLUMN project_id INTEGER")
    if 'sc_id' not in ocr_cols:
        conn.execute("ALTER TABLE ocr_extractions ADD COLUMN sc_id INTEGER")
    if 'doc_type' not in ocr_cols:
        conn.execute("ALTER TABLE ocr_extractions ADD COLUMN doc_type TEXT")
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
        "SELECT * FROM subcontractors WHERE project_id=? AND sc_no=?",
        (data['project_id'], data['sc_no'])
    ).fetchone()

    data.setdefault('parent_sc_no', derive_parent_sc_no(data.get('sc_no')))
    data.setdefault('contract_sum', data.get('contract_amount') or 0)
    data.setdefault('vo_amount', 0)

    if existing:
        old = dict(existing)
        new_pdf = data.get('quotation_saved')
        old_pdf = old.get('quotation_saved')
        if new_pdf and old_pdf and new_pdf != old_pdf:
            add_sc_document(
                data['project_id'], old['id'], data['sc_no'], 'quotation',
                old_pdf, ocr_id=None, conn=conn,
            )
        # Excel 同步時保留 OCR 已填入的報價日期 / PDF
        if not data.get('quotation_date') and old.get('quotation_date'):
            data['quotation_date'] = old['quotation_date']
        if not data.get('quotation_saved') and old.get('quotation_saved'):
            data['quotation_saved'] = old['quotation_saved']
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
    new_pdf = data.get('quotation_saved')
    old_pdf = dict(existing).get('quotation_saved') if existing else None
    if new_pdf and new_pdf != old_pdf:
        add_sc_document(
            data['project_id'], sc_id, data['sc_no'], 'quotation',
            new_pdf, original_filename=data.get('original_filename'),
            ocr_id=data.get('ocr_id'),
        )
    return sc_id


def add_sc_document(project_id, sc_id, sc_no, doc_type, file_path,
                    original_filename=None, ocr_id=None, conn=None):
    """存檔 PDF/圖片（每次掃描保留，不覆蓋舊檔）"""
    if not file_path:
        return None
    own = conn is None
    if own:
        conn = get_conn()
    cur = conn.execute("""
        INSERT INTO sc_documents (
            project_id, sc_id, sc_no, doc_type, file_path,
            original_filename, ocr_id
        ) VALUES (?,?,?,?,?,?,?)
    """, (project_id, sc_id, sc_no, doc_type, file_path, original_filename, ocr_id))
    doc_id = cur.lastrowid
    if own:
        conn.commit()
        conn.close()
    return doc_id


def get_sc_documents(sc_id):
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM sc_documents WHERE sc_id=? ORDER BY created_at DESC, id DESC
    """, (sc_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


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


def payment_invoice_exists(project_id, invoice_no, exclude_id=None):
    """檢查項目內是否已有相同發票號"""
    inv = (invoice_no or '').strip()
    if not inv:
        return None
    conn = get_conn()
    sql = """
        SELECT id, invoice_no, sc_no, paid_amount, invoice_date
        FROM payment_records
        WHERE project_id=? AND LOWER(TRIM(invoice_no))=LOWER(TRIM(?))
    """
    params = [project_id, inv]
    if exclude_id:
        sql += " AND id<>?"
        params.append(exclude_id)
    row = conn.execute(sql, params).fetchone()
    conn.close()
    return dict(row) if row else None


def suggest_sc_matches(project_id, hints=None):
    """依報價單號、公司名、金額建議關聯合同項目"""
    hints = hints or {}
    sc_list = get_subcontractors(project_id)
    if not sc_list:
        return []

    q_no = (hints.get('quotation_no') or '').strip().lower()
    company = (hints.get('company') or '').strip().lower()
    sc_hint = (hints.get('sc_no') or '').strip().upper()
    amount = float(hints.get('amount') or 0)

    results = []
    for sc in sc_list:
        score = 0
        reasons = []
        sc_no = (sc.get('sc_no') or '').upper()
        if sc_hint and sc_no == sc_hint:
            score += 120
            reasons.append('參考編號相符')
        if q_no and sc.get('quotation_no'):
            sq = str(sc['quotation_no']).strip().lower()
            if q_no == sq or q_no in sq or sq in q_no:
                score += 100
                reasons.append('報價單號相符')
        if company:
            for field in ('company_name_en', 'company_name_zh'):
                val = (sc.get(field) or '').strip().lower()
                if not val:
                    continue
                if company == val or company in val or val in company:
                    score += 40
                    reasons.append('公司名稱相符')
                    break
        if amount > 0 and sc.get('contract_amount'):
            ca = float(sc['contract_amount'] or 0)
            if ca > 0 and abs(ca - amount) / ca < 0.05:
                score += 25
                reasons.append('金額接近合同')
        if score > 0:
            results.append({
                'sc_id': sc['id'],
                'sc_no': sc['sc_no'],
                'company_name_en': sc.get('company_name_en'),
                'company_name_zh': sc.get('company_name_zh'),
                'quotation_no': sc.get('quotation_no'),
                'contract_amount': sc.get('contract_amount'),
                'score': score,
                'reasons': reasons,
            })
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:5]


def suggest_next_sc_number(project_id, prefix='SC', company=None):
    """建議 OCR 新建參考編號"""
    sc_list = get_subcontractors(project_id)
    return suggest_next_sc_no(sc_list, prefix, company)


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
    if data.get('pdf_path'):
        add_sc_document(
            data['project_id'], data.get('sc_id'), data.get('sc_no'), 'invoice',
            data['pdf_path'], ocr_id=data.get('ocr_id'),
        )
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


def replace_payments_for_project(project_id):
    """清除項目付款記錄（Excel 重新同步用）"""
    conn = get_conn()
    conn.execute("DELETE FROM payment_records WHERE project_id=?", (project_id,))
    conn.commit()
    conn.close()


# ─── 地盤糧期狀況 (Interim Payments) ───────────────────────────────────

def calc_ip_cumulative_pcts(items, contract_amount):
    """申請% / 批款% = 累計金額 ÷ 承建金額 × 100（與 Excel Summary 一致）"""
    base = float(contract_amount or 0)
    cum_app = cum_cert = 0.0
    out = []
    for it in items:
        row = dict(it)
        cum_app += float(row.get('application_amount') or 0)
        cum_cert += float(row.get('certified_income') or 0)
        if base > 0:
            row['application_pct'] = round(cum_app / base * 100, 2)
            row['certified_income_pct'] = round(cum_cert / base * 100, 2)
        else:
            row['application_pct'] = None
            row['certified_income_pct'] = None
        out.append(row)
    return out


def replace_interim_payments(project_id, items, meta=None):
    """取代項目全部糧期記錄（Excel Summary 匯入）"""
    project = get_project(project_id)
    contract_amount = (project or {}).get('contract_amount') or 0
    items = calc_ip_cumulative_pcts(items, contract_amount)
    conn = get_conn()
    conn.execute("DELETE FROM interim_payments WHERE project_id=?", (project_id,))
    for it in items:
        conn.execute("""
            INSERT INTO interim_payments (
                project_id, ip_no, seq_no, applied_date,
                application_amount, application_pct,
                certified_income, certified_income_pct, certificate_date,
                subcon_paid, subcon_paid_pct, subcon_cert_date
            ) VALUES (
                :project_id, :ip_no, :seq_no, :applied_date,
                :application_amount, :application_pct,
                :certified_income, :certified_income_pct, :certificate_date,
                :subcon_paid, :subcon_paid_pct, :subcon_cert_date
            )
        """, {**it, 'project_id': project_id})
    if meta:
        conn.execute("""
            UPDATE projects SET site_period_text=:site_period_text,
                ip_total_income=:ip_total_income,
                ip_total_expenditure=:ip_total_expenditure,
                ip_advance=:ip_advance
            WHERE id=:project_id
        """, {**meta, 'project_id': project_id})
    conn.commit()
    conn.close()


def get_interim_payments(project_id):
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM interim_payments WHERE project_id=?
        ORDER BY seq_no, ip_no
    """, (project_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_ip_period_summary(project_id):
    """地盤糧期狀況（儀表板用）"""
    project = get_project(project_id)
    if not project:
        return None
    items = calc_ip_cumulative_pcts(
        get_interim_payments(project_id),
        project.get('contract_amount'),
    )
    return {
        'site_period_text': project.get('site_period_text'),
        'items': items,
        'totals': {
            'total_income': project.get('ip_total_income') or 0,
            'total_expenditure': project.get('ip_total_expenditure') or 0,
            'advance': project.get('ip_advance') or 0,
        },
    }


def get_interim_payment(ip_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM interim_payments WHERE id=?", (ip_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def _recalc_and_save_ip_pcts(project_id):
    project = get_project(project_id)
    if not project:
        return
    items = get_interim_payments(project_id)
    calc_items = calc_ip_cumulative_pcts(items, project.get('contract_amount'))
    conn = get_conn()
    for it in calc_items:
        conn.execute(
            "UPDATE interim_payments SET application_pct=?, certified_income_pct=? WHERE id=?",
            (it.get('application_pct'), it.get('certified_income_pct'), it['id'])
        )
    conn.commit()
    conn.close()


def upsert_interim_payment(data):
    conn = get_conn()
    project_id = data['project_id']
    for f in ['applied_date', 'certificate_date', 'subcon_cert_date']:
        data.setdefault(f, None)
    for f in ['application_amount', 'certified_income', 'subcon_paid']:
        data.setdefault(f, 0)
    if not data.get('seq_no'):
        max_seq = conn.execute(
            "SELECT COALESCE(MAX(seq_no), 0) FROM interim_payments WHERE project_id=?",
            (project_id,)
        ).fetchone()[0]
        data['seq_no'] = max_seq + 1

    if data.get('id'):
        conn.execute("""
            UPDATE interim_payments SET
                ip_no=:ip_no, seq_no=:seq_no, applied_date=:applied_date,
                application_amount=:application_amount,
                certified_income=:certified_income, certificate_date=:certificate_date,
                subcon_paid=:subcon_paid, subcon_cert_date=:subcon_cert_date
            WHERE id=:id AND project_id=:project_id
        """, data)
        ip_id = data['id']
    else:
        cur = conn.execute("""
            INSERT INTO interim_payments (
                project_id, ip_no, seq_no, applied_date,
                application_amount, certified_income, certificate_date,
                subcon_paid, subcon_cert_date
            ) VALUES (
                :project_id, :ip_no, :seq_no, :applied_date,
                :application_amount, :certified_income, :certificate_date,
                :subcon_paid, :subcon_cert_date
            )
        """, data)
        ip_id = cur.lastrowid
    conn.commit()
    conn.close()
    _recalc_and_save_ip_pcts(project_id)
    return ip_id


def delete_interim_payment(ip_id):
    conn = get_conn()
    row = conn.execute("SELECT project_id FROM interim_payments WHERE id=?", (ip_id,)).fetchone()
    if not row:
        conn.close()
        return None
    project_id = row['project_id']
    conn.execute("DELETE FROM interim_payments WHERE id=?", (ip_id,))
    conn.commit()
    conn.close()
    _recalc_and_save_ip_pcts(project_id)
    return project_id


def update_ip_period_meta(project_id, meta):
    conn = get_conn()
    conn.execute("""
        UPDATE projects SET
            site_period_text=:site_period_text,
            ip_total_income=:ip_total_income,
            ip_total_expenditure=:ip_total_expenditure,
            ip_advance=:ip_advance
        WHERE id=:project_id
    """, {
        'project_id': project_id,
        'site_period_text': meta.get('site_period_text'),
        'ip_total_income': float(meta.get('ip_total_income') or 0),
        'ip_total_expenditure': float(meta.get('ip_total_expenditure') or 0),
        'ip_advance': float(meta.get('ip_advance') or 0),
    })
    conn.commit()
    conn.close()


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

    ip_period = get_ip_period_summary(project_id)

    conn.close()
    return {
        'project': dict(project),
        'sc_stats': [dict(r) for r in sc_stats],
        'total_paid': totals['total_paid'] or 0,
        'total_remainder': totals['total_remainder'] or 0,
        'ip_period': ip_period,
        'contract_calc': {
            'main_contract_amount': contract_a,
            'sub_total_b': sub_total_b,
            'excluded_c': excluded_c,
            'labour_allocation': labour,
            'total_d': total_d,
            'profit_e': profit_e,
            'profit_rate': round(profit_rate, 2),
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

def save_ocr_extraction(payment_id, filename, raw_text, extracted_json, confidence, status,
                        project_id=None, sc_id=None, doc_type=None):
    conn = get_conn()
    cur = conn.execute("""
        INSERT INTO ocr_extractions (
            payment_id, pdf_filename, ocr_raw_text, extracted_json,
            confidence, status, project_id, sc_id, doc_type
        ) VALUES (?,?,?,?,?,?,?,?,?)
    """, (
        payment_id, filename, raw_text, json.dumps(extracted_json, ensure_ascii=False),
        confidence, status, project_id, sc_id, doc_type,
    ))
    conn.commit()
    ocr_id = cur.lastrowid
    conn.close()
    return ocr_id


def link_ocr_extraction(ocr_id, project_id=None, sc_id=None, payment_id=None, doc_type=None):
    if not ocr_id:
        return
    conn = get_conn()
    conn.execute("""
        UPDATE ocr_extractions SET
            project_id=COALESCE(?, project_id),
            sc_id=COALESCE(?, sc_id),
            payment_id=COALESCE(?, payment_id),
            doc_type=COALESCE(?, doc_type)
        WHERE id=?
    """, (project_id, sc_id, payment_id, doc_type, ocr_id))
    conn.commit()
    conn.close()


if __name__ == '__main__':
    init_db()
    print("[DB] 初始化完成")
