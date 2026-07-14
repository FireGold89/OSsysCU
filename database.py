"""
database.py — QS付款管理系統資料庫模組
SQLite 資料庫初始化與CRUD操作
"""
import sqlite3
import os
import json
import re
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
    if 'project_name_en' not in cols:
        conn.execute("ALTER TABLE projects ADD COLUMN project_name_en TEXT")
    if 'project_name_zh' not in cols:
        conn.execute("ALTER TABLE projects ADD COLUMN project_name_zh TEXT")
    for row in conn.execute(
        "SELECT id, project_name, project_name_en, project_name_zh FROM projects"
    ).fetchall():
        if row['project_name_en'] or row['project_name_zh']:
            continue
        en, zh = _split_legacy_project_name(row['project_name'])
        if not en and not zh:
            continue
        combined = f'{en} · {zh}' if en and zh else (en or zh)
        conn.execute(
            """UPDATE projects SET project_name_en=?, project_name_zh=?, project_name=?
               WHERE id=?""",
            (en or None, zh or None, combined or row['project_name'], row['id']),
        )
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quotation_registry (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            quotation_no        TEXT NOT NULL UNIQUE,
            source_year         INTEGER,
            quote_date          TEXT,
            doc_type            TEXT,
            awarded             TEXT,
            site_name           TEXT,
            trade_category      TEXT,
            description         TEXT,
            person_in_charge    TEXT,
            client_name         TEXT,
            quoted_amount       REAL,
            margin_pct          REAL,
            awarded_amount      REAL,
            contract_days       INTEGER,
            start_date          TEXT,
            completion_date     TEXT,
            subcon_type         TEXT,
            subcon_company      TEXT,
            subcon_amount       REAL,
            profit_amount       REAL,
            profit_pct          REAL,
            checklist_json      TEXT,
            project_id          INTEGER,
            source_file         TEXT,
            source_sheet        TEXT,
            last_sync_at        TEXT DEFAULT (datetime('now', 'localtime')),
            created_at          TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS master_list_imports (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file     TEXT,
            source_year     INTEGER,
            rows_read       INTEGER DEFAULT 0,
            rows_new        INTEGER DEFAULT 0,
            rows_updated    INTEGER DEFAULT 0,
            imported_at     TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    qr_cols = {r[1] for r in conn.execute("PRAGMA table_info(quotation_registry)")}
    if 'person_code' not in qr_cols:
        conn.execute("ALTER TABLE quotation_registry ADD COLUMN person_code TEXT")
        from master_ref import extract_person_code_from_quotation_no, person_display_name
        rows = conn.execute(
            "SELECT id, quotation_no, person_in_charge FROM quotation_registry"
        ).fetchall()
        for row in rows:
            code = extract_person_code_from_quotation_no(row['quotation_no'])
            if not code:
                continue
            pic = row['person_in_charge']
            if not (pic or '').strip():
                pic = person_display_name(code)
            conn.execute(
                "UPDATE quotation_registry SET person_code=?, person_in_charge=? WHERE id=?",
                (code, pic, row['id']),
            )
    proj_cols = {r[1] for r in conn.execute("PRAGMA table_info(projects)")}
    if 'quotation_no' not in proj_cols:
        conn.execute("ALTER TABLE projects ADD COLUMN quotation_no TEXT")
    if 'person_code' not in proj_cols:
        conn.execute("ALTER TABLE projects ADD COLUMN person_code TEXT")
    if 'person_in_charge' not in proj_cols:
        conn.execute("ALTER TABLE projects ADD COLUMN person_in_charge TEXT")
    for row in conn.execute("""
        SELECT qr.quotation_no, qr.person_code, qr.person_in_charge, qr.project_id
        FROM quotation_registry qr
        WHERE qr.project_id IS NOT NULL
    """).fetchall():
        conn.execute("""
            UPDATE projects SET
                quotation_no=COALESCE(quotation_no, ?),
                person_code=COALESCE(person_code, ?),
                person_in_charge=COALESCE(person_in_charge, ?)
            WHERE id=?
        """, (row['quotation_no'], row['person_code'], row['person_in_charge'], row['project_id']))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS staff_members (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            code            TEXT NOT NULL UNIQUE,
            name_en         TEXT,
            name_zh         TEXT,
            email           TEXT,
            phone           TEXT,
            department      TEXT,
            access_role     TEXT DEFAULT 'qs',
            is_active       INTEGER DEFAULT 1,
            notes           TEXT,
            created_at      TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at      TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    staff_count = conn.execute("SELECT COUNT(*) FROM staff_members").fetchone()[0]
    if staff_count == 0:
        from master_ref import PERSON_CODE_NAMES
        for code, name in PERSON_CODE_NAMES.items():
            conn.execute("""
                INSERT OR IGNORE INTO staff_members (code, name_en, access_role, is_active)
                VALUES (?, ?, 'qs', 1)
            """, (code.lower(), name))
    for row in conn.execute("""
        SELECT DISTINCT person_code, person_in_charge
        FROM quotation_registry
        WHERE person_code IS NOT NULL AND person_code != ''
    """).fetchall():
        pic = (row['person_in_charge'] or '').strip()
        if not pic or (len(pic) <= 4 and ' ' not in pic):
            continue
        conn.execute("""
            INSERT OR IGNORE INTO staff_members (code, name_en, access_role, is_active)
            VALUES (?, ?, 'qs', 1)
        """, (row['person_code'].lower(), pic))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS master_subcon_summary (
            quotation_no          TEXT PRIMARY KEY,
            main_subcon_company   TEXT,
            main_subcon_amount    REAL,
            updated_at            TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (quotation_no) REFERENCES quotation_registry(quotation_no) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS master_qs_subcon_lines (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            quotation_no    TEXT NOT NULL,
            line_seq        INTEGER DEFAULT 0,
            subcon_company  TEXT,
            subcon_amount   REAL,
            display_line    TEXT,
            FOREIGN KEY (quotation_no) REFERENCES quotation_registry(quotation_no) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS master_client_invoices (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            quotation_no    TEXT NOT NULL,
            line_seq        INTEGER DEFAULT 0,
            ip_no           TEXT,
            invoice_date    TEXT,
            invoice_no      TEXT,
            invoice_amount  REAL,
            receipt_date    TEXT,
            raw_line        TEXT,
            FOREIGN KEY (quotation_no) REFERENCES quotation_registry(quotation_no) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS master_subcon_payments (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            quotation_no    TEXT NOT NULL,
            line_seq        INTEGER DEFAULT 0,
            subcon_company  TEXT,
            subcon_amount   REAL,
            voucher_date    TEXT,
            is_main_subcon  INTEGER DEFAULT 0,
            FOREIGN KEY (quotation_no) REFERENCES quotation_registry(quotation_no) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS master_cheque_records (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            quotation_no    TEXT NOT NULL,
            line_seq        INTEGER DEFAULT 0,
            cheque_ref      TEXT,
            cheque_date     TEXT,
            raw_line        TEXT,
            FOREIGN KEY (quotation_no) REFERENCES quotation_registry(quotation_no) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_mci_quotation ON master_client_invoices(quotation_no);
        CREATE INDEX IF NOT EXISTS idx_msp_quotation ON master_subcon_payments(quotation_no);
        CREATE INDEX IF NOT EXISTS idx_mchq_quotation ON master_cheque_records(quotation_no);
        CREATE INDEX IF NOT EXISTS idx_mqsl_quotation ON master_qs_subcon_lines(quotation_no);
    """)
    cheq_cols = {r[1] for r in conn.execute("PRAGMA table_info(master_cheque_records)")}
    if 'cheque_no' not in cheq_cols:
        conn.execute("ALTER TABLE master_cheque_records ADD COLUMN cheque_no TEXT")
    if 'bank' not in cheq_cols:
        conn.execute("ALTER TABLE master_cheque_records ADD COLUMN bank TEXT")
    from master_finance import (
        build_subcon_payment_row,
        parse_cheque_line,
        parse_client_invoice_line,
        parse_cheque_line_amount,
        _amount_display,
        format_finance_display_line,
    )
    inv_cols = {r[1] for r in conn.execute("PRAGMA table_info(master_client_invoices)")}
    if 'display_line' not in inv_cols:
        conn.execute("ALTER TABLE master_client_invoices ADD COLUMN display_line TEXT")
    sub_cols = {r[1] for r in conn.execute("PRAGMA table_info(master_subcon_payments)")}
    if 'display_line' not in sub_cols:
        conn.execute("ALTER TABLE master_subcon_payments ADD COLUMN display_line TEXT")
    if 'raw_line' not in sub_cols:
        conn.execute("ALTER TABLE master_subcon_payments ADD COLUMN raw_line TEXT")
    for row in conn.execute(
        "SELECT id, raw_line, invoice_no, ip_no, invoice_amount FROM master_client_invoices WHERE display_line IS NULL"
    ).fetchall():
        parsed = parse_client_invoice_line(row['raw_line'] or row['invoice_no'])
        conn.execute("""
            UPDATE master_client_invoices
            SET invoice_no=COALESCE(invoice_no, ?), ip_no=COALESCE(ip_no, ?),
                invoice_amount=COALESCE(invoice_amount, ?), display_line=?
            WHERE id=?
        """, (
            parsed['invoice_no'], parsed['ip_no'], parsed['invoice_amount'],
            parsed['display_line'], row['id'],
        ))
    for row in conn.execute("""
        SELECT id, subcon_company, subcon_amount, voucher_date, raw_line
        FROM master_subcon_payments WHERE display_line IS NULL
    """).fetchall():
        built = build_subcon_payment_row(
            row['subcon_company'], row['subcon_amount'], row['voucher_date'], [], 0,
        )
        conn.execute("""
            UPDATE master_subcon_payments
            SET display_line=?, raw_line=COALESCE(raw_line, ?)
            WHERE id=?
        """, (built['display_line'], built['raw_line'], row['id']))
    _migrate_client_invoice_amounts(conn)
    for row in conn.execute(
        "SELECT id, raw_line, cheque_ref FROM master_cheque_records WHERE cheque_no IS NULL"
    ).fetchall():
        parsed = parse_cheque_line(row['raw_line'] or row['cheque_ref'])
        if parsed.get('cheque_no'):
            conn.execute("""
                UPDATE master_cheque_records
                SET cheque_no=?, bank=?, cheque_date=COALESCE(cheque_date, ?), cheque_ref=?
                WHERE id=?
            """, (
                parsed['cheque_no'], parsed['bank'], parsed['cheque_date'],
                parsed['cheque_ref'], row['id'],
            ))
    _migrate_pic_abbreviations(conn)
    _migrate_staff_roster(conn)
    _migrate_master_source_filenames(conn)
    _migrate_qs_subcon_registry_fields(conn)
    conn.commit()


def _migrate_client_invoice_amounts(conn):
    """業主糧期金額：只取自發票欄或支票(Admin)欄，不用分判金額"""
    from master_finance import (
        parse_client_invoice_line,
        parse_cheque_line_amount,
        _amount_display,
        format_finance_display_line,
    )
    rows = conn.execute("""
        SELECT ci.id, ci.quotation_no, ci.line_seq, ci.invoice_no, ci.invoice_amount,
               ci.raw_line, ci.ip_no, mch.raw_line AS cheque_raw
        FROM master_client_invoices ci
        LEFT JOIN master_cheque_records mch
            ON mch.quotation_no = ci.quotation_no AND mch.line_seq = ci.line_seq
    """).fetchall()
    for row in rows:
        parsed = parse_client_invoice_line(row['raw_line'] or row['invoice_no'])
        amt = parsed.get('invoice_amount')
        ip_no = parsed.get('ip_no') or row['ip_no']
        inv_no = parsed.get('invoice_no') or row['invoice_no']
        if amt is None and row['cheque_raw']:
            amt = parse_cheque_line_amount(row['cheque_raw'])
        if (amt != row['invoice_amount']) or (inv_no != row['invoice_no']):
            disp = format_finance_display_line(inv_no, ip_no, _amount_display(amt))
            conn.execute("""
                UPDATE master_client_invoices
                SET invoice_no=?, ip_no=?, invoice_amount=?, display_line=?
                WHERE id=?
            """, (inv_no, ip_no, amt, disp, row['id']))


def _migrate_qs_subcon_registry_fields(conn):
    """主檔 subcon 欄與 master_qs_subcon_lines 對齊（首家 + 合計）"""
    rows = conn.execute("""
        SELECT quotation_no,
               (SELECT subcon_company FROM master_qs_subcon_lines m
                WHERE m.quotation_no = l.quotation_no ORDER BY line_seq LIMIT 1) AS first_co,
               SUM(subcon_amount) AS total
        FROM master_qs_subcon_lines l
        GROUP BY quotation_no
    """).fetchall()
    for row in rows:
        if not row['first_co']:
            continue
        conn.execute("""
            UPDATE quotation_registry
            SET subcon_company=?, subcon_amount=?
            WHERE quotation_no=?
        """, (row['first_co'], row['total'], row['quotation_no']))


def _migrate_master_source_filenames(conn):
    """舊版 Master List 檔名（含日期後綴）→ YYYY Quotation & Contract number.xlsx"""
    from master_list_importer import normalize_master_source_file
    for table in ('quotation_registry', 'master_list_imports'):
        rows = conn.execute(
            f"SELECT DISTINCT source_file FROM {table} WHERE source_file IS NOT NULL"
        ).fetchall()
        for row in rows:
            old = row['source_file']
            new = normalize_master_source_file(old)
            if new and new != old:
                conn.execute(
                    f"UPDATE {table} SET source_file=? WHERE source_file=?",
                    (new, old),
                )


# ─── Projects ──────────────────────────────────────────────────────────

def _split_legacy_project_name(name):
    """將舊 project_name 拆成中英（匯入/遷移用）"""
    name = (name or '').strip()
    if not name:
        return '', ''
    has_cjk = bool(re.search(r'[\u4e00-\u9fff]', name))
    has_latin = bool(re.search(r'[A-Za-z]', name))
    if has_cjk and has_latin:
        for sep in (' / ', ' · ', '｜', ' | ', '\n'):
            if sep in name:
                a, b = name.split(sep, 1)
                return a.strip(), b.strip()
        return name, ''
    if has_cjk:
        return '', name
    return name, ''


def _normalize_project_fields(data):
    en = (data.get('project_name_en') or '').strip()
    zh = (data.get('project_name_zh') or '').strip()
    legacy = (data.get('project_name') or '').strip()
    if not en and not zh and legacy:
        en, zh = _split_legacy_project_name(legacy)
    data['project_name_en'] = en or None
    data['project_name_zh'] = zh or None
    if en and zh:
        data['project_name'] = f'{en} · {zh}'
    else:
        data['project_name'] = en or zh or legacy or (data.get('project_code') or '')
    return data


def _enrich_project(row):
    """合併 Master List 配對欄位（報價編號、負責人）"""
    d = dict(row)
    if not d.get('quotation_no') and d.get('reg_quotation_no'):
        d['quotation_no'] = d['reg_quotation_no']
    if not d.get('person_code') and d.get('reg_person_code'):
        d['person_code'] = d['reg_person_code']
    if not d.get('person_in_charge') and d.get('reg_person_in_charge'):
        d['person_in_charge'] = d['reg_person_in_charge']
    for k in ('reg_quotation_no', 'reg_person_code', 'reg_person_in_charge'):
        d.pop(k, None)
    return d


def get_all_projects():
    conn = get_conn()
    rows = conn.execute("""
        SELECT p.*,
               qr.quotation_no AS reg_quotation_no,
               qr.person_code AS reg_person_code,
               qr.person_in_charge AS reg_person_in_charge,
               (SELECT COUNT(*) FROM subcontractors sc WHERE sc.project_id = p.id) AS sc_count,
               (SELECT COALESCE(SUM(pr.paid_amount), 0)
                FROM payment_records pr WHERE pr.project_id = p.id) AS total_paid
        FROM projects p
        LEFT JOIN quotation_registry qr ON qr.project_id = p.id
        ORDER BY p.created_at DESC
    """).fetchall()
    conn.close()
    return [_enrich_project(r) for r in rows]


def get_project(project_id):
    conn = get_conn()
    row = conn.execute("""
        SELECT p.*,
               qr.quotation_no AS reg_quotation_no,
               qr.person_code AS reg_person_code,
               qr.person_in_charge AS reg_person_in_charge
        FROM projects p
        LEFT JOIN quotation_registry qr ON qr.project_id = p.id
        WHERE p.id=?
    """, (project_id,)).fetchone()
    conn.close()
    return _enrich_project(row) if row else None


def create_project(data):
    data = _normalize_project_fields(dict(data))
    data.setdefault('quotation_no', None)
    data.setdefault('person_code', None)
    data.setdefault('person_in_charge', None)
    data.setdefault('labour_allocation', 0)
    from master_ref import enrich_person_fields
    enrich_person_fields(data)
    conn = get_conn()
    cur = conn.execute("""
        INSERT INTO projects (project_code, project_name, project_name_en, project_name_zh,
                              client, main_contractor, contract_amount, labour_allocation,
                              start_date, status, notes,
                              quotation_no, person_code, person_in_charge)
        VALUES (:project_code, :project_name, :project_name_en, :project_name_zh,
                :client, :main_contractor, :contract_amount, :labour_allocation,
                :start_date, :status, :notes,
                :quotation_no, :person_code, :person_in_charge)
    """, data)
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    if data.get('quotation_no'):
        link_quotation_to_project(data['quotation_no'], new_id, sync_project_code=True)
    return new_id


def update_project(project_id, data):
    data = _normalize_project_fields(dict(data))
    data.setdefault('quotation_no', None)
    data.setdefault('person_code', None)
    data.setdefault('person_in_charge', None)
    if 'labour_allocation' not in data:
        existing = get_project(project_id) or {}
        data['labour_allocation'] = existing.get('labour_allocation') or 0
    from master_ref import enrich_person_fields
    enrich_person_fields(data)
    conn = get_conn()
    conn.execute("""
        UPDATE projects SET project_code=:project_code, project_name=:project_name,
            project_name_en=:project_name_en, project_name_zh=:project_name_zh,
            client=:client, main_contractor=:main_contractor,
            contract_amount=:contract_amount, labour_allocation=:labour_allocation,
            start_date=:start_date, status=:status, notes=:notes,
            quotation_no=:quotation_no, person_code=:person_code,
            person_in_charge=:person_in_charge
        WHERE id=:id
    """, {**data, 'id': project_id})
    conn.commit()
    conn.close()
    qno = data.get('quotation_no')
    if qno:
        link_quotation_to_project(qno, project_id, sync_project_code=True)


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

    clear_pdf = bool(data.pop('clear_quotation_pdf', False))

    if existing:
        old = dict(existing)
        new_pdf = data.get('quotation_saved')
        old_pdf = old.get('quotation_saved')
        if clear_pdf and old_pdf:
            add_sc_document(
                data['project_id'], old['id'], data['sc_no'], 'quotation',
                old_pdf, ocr_id=None, conn=conn,
            )
            data['quotation_saved'] = None
        elif new_pdf and old_pdf and new_pdf != old_pdf:
            add_sc_document(
                data['project_id'], old['id'], data['sc_no'], 'quotation',
                old_pdf, ocr_id=None, conn=conn,
            )
        # Excel 同步時保留 OCR 已填入的報價日期 / PDF
        if not data.get('quotation_date') and old.get('quotation_date'):
            data['quotation_date'] = old['quotation_date']
        if not clear_pdf and not data.get('quotation_saved') and old.get('quotation_saved'):
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


def attach_quotation_pdf(sc_id, file_path, original_filename=None, ocr_id=None):
    """將 PDF/圖片設為合同報價存證（舊檔自動存入 sc_documents）"""
    sc = get_subcontractor(sc_id)
    if not sc:
        return None
    data = {
        'project_id': sc['project_id'],
        'sc_no': sc['sc_no'],
        'quotation_no': sc.get('quotation_no'),
        'company_name_en': sc.get('company_name_en'),
        'company_name_zh': sc.get('company_name_zh'),
        'description': sc.get('description'),
        'contract_sum': sc.get('contract_sum'),
        'vo_amount': sc.get('vo_amount'),
        'contract_amount': sc.get('contract_amount'),
        'payment_note': sc.get('payment_note'),
        'oa_status': sc.get('oa_status'),
        'oa_ref': sc.get('oa_ref'),
        'oa_no': sc.get('oa_no'),
        'quotation_saved': file_path,
        'quotation_date': sc.get('quotation_date'),
        'oa_date': sc.get('oa_date'),
        'is_excluded': sc.get('is_excluded') or 0,
        'original_filename': original_filename,
        'ocr_id': ocr_id,
    }
    return upsert_subcontractor(data)


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


def get_quotation_for_project(project_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT quotation_no FROM quotation_registry WHERE project_id=? LIMIT 1",
        (project_id,),
    ).fetchone()
    conn.close()
    return row['quotation_no'] if row else None


def get_ip_reconciliation(project_id=None, quotation_no=None):
    """
    地盤糧期 ↔ 行政業主糧期 對照（需項目已配對 Master List）。
    可傳 project_id 或 quotation_no。
    """
    if not project_id and quotation_no:
        qr = get_quotation_by_no(quotation_no)
        project_id = qr.get('project_id') if qr else None
    if project_id and not quotation_no:
        quotation_no = get_quotation_for_project(project_id)
        if not quotation_no:
            proj = get_project(project_id)
            quotation_no = (proj or {}).get('quotation_no')

    if not project_id or not quotation_no:
        return {
            'linked': False,
            'quotation_no': quotation_no,
            'project_id': project_id,
            'rows': [],
            'stats': {},
            'message': '尚未配對 Master List 與工程項目，無法對照糧期。',
        }

    site_items = get_interim_payments(project_id)
    finance = get_quotation_finance(quotation_no)
    admin_invoices = finance.get('client_invoices') or []

    from master_ip_reconcile import build_ip_reconciliation
    return build_ip_reconciliation(
        site_items, admin_invoices,
        quotation_no=quotation_no, project_id=project_id,
    )


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


# ─── Master List (quotation_registry) ───────────────────────────────────

def get_quotation_by_no(quotation_no):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM quotation_registry WHERE quotation_no=?", (quotation_no,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_quotation_by_id(row_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM quotation_registry WHERE id=?", (row_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def upsert_quotation_registry(data):
    data = dict(data)
    data.setdefault('project_id', None)
    data.setdefault('person_code', None)
    from master_ref import enrich_person_fields
    from master_finance import apply_master_profit_fields
    enrich_person_fields(data)
    apply_master_profit_fields(data)
    conn = get_conn()
    existing = conn.execute(
        "SELECT id FROM quotation_registry WHERE quotation_no=?",
        (data['quotation_no'],),
    ).fetchone()
    data['last_sync_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if existing:
        conn.execute("""
            UPDATE quotation_registry SET
                source_year=:source_year, quote_date=:quote_date, doc_type=:doc_type,
                awarded=:awarded, site_name=:site_name, trade_category=:trade_category,
                description=:description, person_code=:person_code,
                person_in_charge=:person_in_charge,
                client_name=:client_name, quoted_amount=:quoted_amount,
                margin_pct=:margin_pct, awarded_amount=:awarded_amount,
                contract_days=:contract_days, start_date=:start_date,
                completion_date=:completion_date, subcon_type=:subcon_type,
                subcon_company=:subcon_company, subcon_amount=:subcon_amount,
                profit_amount=:profit_amount, profit_pct=:profit_pct,
                checklist_json=:checklist_json,
                project_id=COALESCE(:project_id, project_id),
                source_file=:source_file, source_sheet=:source_sheet,
                last_sync_at=:last_sync_at
            WHERE quotation_no=:quotation_no
        """, data)
    else:
        conn.execute("""
            INSERT INTO quotation_registry (
                quotation_no, source_year, quote_date, doc_type, awarded,
                site_name, trade_category, description, person_code, person_in_charge, client_name,
                quoted_amount, margin_pct, awarded_amount, contract_days,
                start_date, completion_date, subcon_type, subcon_company,
                subcon_amount, profit_amount, profit_pct, checklist_json,
                project_id, source_file, source_sheet, last_sync_at
            ) VALUES (
                :quotation_no, :source_year, :quote_date, :doc_type, :awarded,
                :site_name, :trade_category, :description, :person_code, :person_in_charge, :client_name,
                :quoted_amount, :margin_pct, :awarded_amount, :contract_days,
                :start_date, :completion_date, :subcon_type, :subcon_company,
                :subcon_amount, :profit_amount, :profit_pct, :checklist_json,
                :project_id, :source_file, :source_sheet, :last_sync_at
            )
        """, data)
    conn.commit()
    conn.close()


def link_quotation_to_project(quotation_no, project_id, sync_project_code=True):
    """配對 Master List ↔ 工程項目，同步報價編號與負責人"""
    qr = get_quotation_by_no(quotation_no)
    if not qr:
        raise ValueError(f'找不到報價記錄: {quotation_no}')
    conn = get_conn()
    conn.execute(
        "UPDATE quotation_registry SET project_id=NULL WHERE project_id=? AND quotation_no!=?",
        (project_id, quotation_no),
    )
    conn.execute(
        "UPDATE quotation_registry SET project_id=? WHERE quotation_no=?",
        (project_id, quotation_no),
    )
    pic = qr.get('person_in_charge')
    if sync_project_code:
        conn.execute("""
            UPDATE projects SET
                quotation_no=?,
                person_in_charge=?,
                person_code=NULL,
                project_code=?
            WHERE id=?
        """, (quotation_no, pic, quotation_no, project_id))
    else:
        conn.execute("""
            UPDATE projects SET quotation_no=?, person_in_charge=?, person_code=NULL
            WHERE id=?
        """, (quotation_no, pic, project_id))
    conn.commit()
    conn.close()


def unlink_quotation_from_project(quotation_no):
    qr = get_quotation_by_no(quotation_no)
    if not qr:
        return
    project_id = qr.get('project_id')
    conn = get_conn()
    conn.execute(
        "UPDATE quotation_registry SET project_id=NULL WHERE quotation_no=?",
        (quotation_no,),
    )
    if project_id:
        conn.execute("""
            UPDATE projects SET quotation_no=NULL, person_code=NULL, person_in_charge=NULL
            WHERE id=?
        """, (project_id,))
    conn.commit()
    conn.close()


MASTER_EDITABLE_FIELDS = (
    'quote_date', 'doc_type', 'awarded', 'site_name', 'trade_category', 'description',
    'person_code', 'person_in_charge', 'client_name', 'quoted_amount', 'margin_pct',
    'awarded_amount', 'contract_days', 'start_date', 'completion_date',
    'subcon_type', 'subcon_company', 'subcon_amount', 'profit_amount', 'profit_pct',
    'checklist_json',
)


def _normalize_checklist_json(value):
    if value is None or value == '':
        return None
    if isinstance(value, str):
        return value if value.strip() else None
    if isinstance(value, dict):
        import json
        cleaned = {k: v for k, v in value.items() if v}
        return json.dumps(cleaned, ensure_ascii=False) if cleaned else None
    return None


def update_quotation_registry(quotation_no, data):
    existing = get_quotation_by_no(quotation_no)
    if not existing:
        return False
    patch = {k: data[k] for k in MASTER_EDITABLE_FIELDS if k in data}
    if 'checklist_json' in patch:
        patch['checklist_json'] = _normalize_checklist_json(patch['checklist_json'])
    if not patch:
        return True
    merged = {**existing, **patch, 'quotation_no': quotation_no}
    from master_ref import enrich_person_fields
    from master_finance import apply_master_profit_fields
    enrich_person_fields(merged)
    apply_master_profit_fields(merged)
    if existing.get('project_id'):
        merged['project_id'] = existing['project_id']
    upsert_quotation_registry(merged)
    if existing.get('project_id'):
        conn = get_conn()
        conn.execute("""
            UPDATE projects SET person_in_charge=?
            WHERE id=?
        """, (merged.get('person_in_charge'), existing['project_id']))
        conn.commit()
        conn.close()
    return True


def replace_quotation_finance(quotation_no, finance):
    """覆寫報價的 Phase 2 財務明細（匯入時呼叫）"""
    if not finance:
        return
    conn = get_conn()
    conn.execute("DELETE FROM master_client_invoices WHERE quotation_no=?", (quotation_no,))
    conn.execute("DELETE FROM master_subcon_payments WHERE quotation_no=?", (quotation_no,))
    conn.execute("DELETE FROM master_cheque_records WHERE quotation_no=?", (quotation_no,))
    conn.execute("DELETE FROM master_subcon_summary WHERE quotation_no=?", (quotation_no,))
    conn.execute("DELETE FROM master_qs_subcon_lines WHERE quotation_no=?", (quotation_no,))

    summary = finance.get('summary')
    if summary and (summary.get('main_subcon_company') or summary.get('main_subcon_amount') is not None):
        conn.execute("""
            INSERT INTO master_subcon_summary (quotation_no, main_subcon_company, main_subcon_amount)
            VALUES (?, ?, ?)
        """, (
            quotation_no,
            summary.get('main_subcon_company'),
            summary.get('main_subcon_amount'),
        ))

    for row in finance.get('qs_subcon_lines') or []:
        conn.execute("""
            INSERT INTO master_qs_subcon_lines (
                quotation_no, line_seq, subcon_company, subcon_amount, display_line
            ) VALUES (?, ?, ?, ?, ?)
        """, (
            quotation_no, row.get('line_seq'), row.get('subcon_company'),
            row.get('subcon_amount'), row.get('display_line'),
        ))

    for row in finance.get('client_invoices') or []:
        conn.execute("""
            INSERT INTO master_client_invoices (
                quotation_no, line_seq, ip_no, invoice_date, invoice_no,
                invoice_amount, receipt_date, display_line, raw_line
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            quotation_no, row.get('line_seq'), row.get('ip_no'), row.get('invoice_date'),
            row.get('invoice_no'), row.get('invoice_amount'), row.get('receipt_date'),
            row.get('display_line'), row.get('raw_line'),
        ))

    for row in finance.get('subcon_payments') or []:
        conn.execute("""
            INSERT INTO master_subcon_payments (
                quotation_no, line_seq, subcon_company, subcon_amount,
                voucher_date, is_main_subcon, display_line, raw_line
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            quotation_no, row.get('line_seq'), row.get('subcon_company'),
            row.get('subcon_amount'), row.get('voucher_date'), row.get('is_main_subcon', 0),
            row.get('display_line'), row.get('raw_line'),
        ))

    for row in finance.get('cheques') or []:
        conn.execute("""
            INSERT INTO master_cheque_records (
                quotation_no, line_seq, cheque_no, bank, cheque_ref, cheque_date, raw_line
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            quotation_no, row.get('line_seq'), row.get('cheque_no'), row.get('bank'),
            row.get('cheque_ref'), row.get('cheque_date'), row.get('raw_line'),
        ))

    conn.commit()
    conn.close()


def sync_qs_subcon_registry_fields(quotation_no, finance):
    """QS 主分判多行 → 主檔首家公司 + 金額合計"""
    qs_lines = (finance or {}).get('qs_subcon_lines') or []
    if not qs_lines:
        return
    total = sum(r.get('subcon_amount') or 0 for r in qs_lines)
    first_co = qs_lines[0].get('subcon_company')
    update_quotation_registry(quotation_no, {
        'subcon_company': first_co,
        'subcon_amount': total if total else qs_lines[0].get('subcon_amount'),
    })


def get_quotation_finance(quotation_no):
    conn = get_conn()
    summary = conn.execute(
        "SELECT * FROM master_subcon_summary WHERE quotation_no=?", (quotation_no,)
    ).fetchone()
    invoices = conn.execute(
        "SELECT * FROM master_client_invoices WHERE quotation_no=? ORDER BY line_seq",
        (quotation_no,),
    ).fetchall()
    payments = conn.execute(
        "SELECT * FROM master_subcon_payments WHERE quotation_no=? ORDER BY line_seq",
        (quotation_no,),
    ).fetchall()
    cheques = conn.execute(
        "SELECT * FROM master_cheque_records WHERE quotation_no=? ORDER BY line_seq",
        (quotation_no,),
    ).fetchall()
    qs_lines = conn.execute(
        "SELECT * FROM master_qs_subcon_lines WHERE quotation_no=? ORDER BY line_seq",
        (quotation_no,),
    ).fetchall()
    conn.close()
    from master_finance import (
        _amount_display,
        _date_display,
        build_subcon_payment_row,
        parse_cheque_line,
        parse_client_invoice_line,
    )
    qs = []
    for r in qs_lines:
        d = dict(r)
        d['amount_display'] = _amount_display(d.get('subcon_amount'))
        qs.append(d)
    inv = []
    for r in invoices:
        d = dict(r)
        if not d.get('display_line') and d.get('raw_line'):
            parsed = parse_client_invoice_line(d['raw_line'])
            d['display_line'] = parsed.get('display_line')
        d['amount_display'] = _amount_display(d.get('invoice_amount'))
        d['invoice_date_display'] = _date_display(d.get('invoice_date'))
        d['receipt_date_display'] = _date_display(d.get('receipt_date'))
        inv.append(d)
    pay = []
    for r in payments:
        d = dict(r)
        if not d.get('display_line'):
            built = build_subcon_payment_row(
                d.get('subcon_company'), d.get('subcon_amount'), d.get('voucher_date'), qs, 0,
            )
            d['display_line'] = built.get('display_line')
            d['is_main_subcon'] = built.get('is_main_subcon')
        d['amount_display'] = _amount_display(d.get('subcon_amount'))
        d['voucher_display'] = _date_display(d.get('voucher_date'))
        pay.append(d)
    chq = []
    for r in cheques:
        d = dict(r)
        if not d.get('cheque_no') and (d.get('raw_line') or d.get('cheque_ref')):
            parsed = parse_cheque_line(d.get('raw_line') or d.get('cheque_ref'))
            for k in ('cheque_no', 'bank', 'cheque_date', 'cheque_ref'):
                if parsed.get(k) and not d.get(k):
                    d[k] = parsed[k]
            d['cheque_date_display'] = parsed.get('cheque_date_display')
        elif d.get('cheque_ref') and ',' in d['cheque_ref']:
            d['cheque_date_display'] = d['cheque_ref'].split(',')[-1].strip()
        else:
            d['cheque_date_display'] = _date_display(d.get('cheque_date'))
        chq.append(d)
    subcon_companies = sorted({p.get('subcon_company') for p in pay if p.get('subcon_company')})
    qs_total = sum(r.get('subcon_amount') or 0 for r in qs)
    return {
        'summary': dict(summary) if summary else None,
        'qs_subcon_lines': qs,
        'client_invoices': inv,
        'subcon_payments': pay,
        'cheques': chq,
        'stats': {
            'ip_count': len(inv),
            'qs_subcon_count': len(qs),
            'qs_subcon_total': qs_total if qs else None,
            'subcon_payment_count': len(pay),
            'cheque_count': len(chq),
            'subcon_company_count': len(subcon_companies),
            'subcon_companies': subcon_companies,
        },
    }


def _is_pic_abbreviation_label(label):
    """略過報價尾碼式縮寫／純數字，下拉只列項目負責人全名"""
    s = (label or '').strip()
    if not s:
        return True
    if s.isdigit():
        return True
    if ' ' in s:
        return False
    if 2 <= len(s) <= 4 and s.isalpha() and (s == s.lower() or s == s.upper()):
        return True
    return False


def _invalid_master_person_label(label):
    """略過主檔中非正式負責人寫法（縮寫、多人並列等）"""
    s = (label or '').strip()
    if not s or _is_pic_abbreviation_label(s):
        return True
    if any(ch in s for ch in ',/·、'):
        return True
    return False


def _pick_canonical_person_name(variants):
    """同一負責人多種寫法時取最常見、較完整者"""
    best_name = ''
    best_cnt = -1
    best_len = -1
    for name, cnt in variants:
        n = (name or '').strip()
        if not n:
            continue
        ln = len(n)
        if cnt > best_cnt or (cnt == best_cnt and ln > best_len):
            best_name, best_cnt, best_len = n, cnt, ln
    return best_name


def _registry_by_person(conn, filt_sql='', params=None):
    """Master List 項目負責人統計（正規化姓名）"""
    params = params or []
    pic_rows = conn.execute(f"""
        SELECT lower(trim(qr.person_in_charge)) AS pic_key,
               qr.person_in_charge AS person_name,
               COUNT(*) AS cnt
        FROM quotation_registry qr
        WHERE qr.person_in_charge IS NOT NULL AND trim(qr.person_in_charge) != ''{filt_sql}
        GROUP BY pic_key, qr.person_in_charge
    """, params).fetchall()
    groups = {}
    for row in pic_rows:
        key = row['pic_key']
        groups.setdefault(key, []).append((row['person_name'], row['cnt']))
    result = []
    for key, variants in groups.items():
        name = _pick_canonical_person_name(variants)
        if _invalid_master_person_label(name):
            continue
        result.append({
            'person_name': name,
            'cnt': sum(c for _, c in variants),
            'pic_key': key,
            'variant_count': len(variants),
        })
    result.sort(key=lambda x: (-x['cnt'], x['person_name'].lower()))
    return result


def _migrate_pic_abbreviations(conn):
    """主檔 person_in_charge 縮寫 → 項目負責人全名（不以尾碼區分）"""
    from master_ref import PERSON_CODE_NAMES
    name_map = {}
    for code, name in PERSON_CODE_NAMES.items():
        name_map[code.lower()] = name
    for row in conn.execute(
        "SELECT code, name_en, name_zh FROM staff_members WHERE is_active=1"
    ).fetchall():
        full = (row['name_en'] or row['name_zh'] or '').strip()
        if not full or _is_pic_abbreviation_label(full):
            continue
        name_map[row['code'].lower()] = full
    for abbr, full in name_map.items():
        conn.execute(
            "UPDATE quotation_registry SET person_in_charge=? "
            "WHERE lower(trim(person_in_charge))=lower(trim(?))",
            (full, abbr),
        )


def _staff_canonical_name(staff_row):
    return (staff_row.get('name_en') or staff_row.get('name_zh') or '').strip()


def _migrate_staff_roster(conn):
    """停用縮寫式負責人、合併同名重複記錄（只保留最早一筆）"""
    seen_names = {}
    for row in conn.execute("""
        SELECT id, name_en, name_zh FROM staff_members
        WHERE is_active = 1
        ORDER BY id
    """).fetchall():
        label = _staff_canonical_name(dict(row))
        if not label or _is_pic_abbreviation_label(label):
            conn.execute(
                "UPDATE staff_members SET is_active=0, updated_at=datetime('now','localtime') WHERE id=?",
                (row['id'],),
            )
            continue
        key = label.lower()
        if key in seen_names:
            conn.execute(
                "UPDATE staff_members SET is_active=0, updated_at=datetime('now','localtime') WHERE id=?",
                (row['id'],),
            )
        else:
            seen_names[key] = row['id']


def _staff_display_names(staff_row):
    """項目負責人全名（不含報價尾碼／縮寫）"""
    names = []
    for col in ('name_en', 'name_zh'):
        v = (staff_row.get(col) or '').strip()
        if v and v.lower() not in {n.lower() for n in names}:
            names.append(v)
    return names


def _person_match_clause(alias, conn, person_label):
    """依主檔 person_in_charge 全名篩選（不用 staff id／尾碼）"""
    pic = (person_label or '').strip()
    if not pic:
        return '', []
    return f" AND lower(trim({alias}.person_in_charge)) = lower(trim(?))", [pic]


def _sql_person_in_charge_match(alias, names):
    clauses = ' OR '.join(
        f"lower(trim({alias}.person_in_charge)) = lower(trim(?))" for _ in names
    )
    return f" AND ({clauses})", list(names)


def _registry_filter_sql(conn, q=None, awarded_only=False, unlinked_only=False,
                         source_year=None, person_in_charge=None, doc_type=None,
                         exclude=None):
    """Master List 篩選 SQL 片段（qr 別名）"""
    exclude = exclude or frozenset()
    parts = []
    params = []
    if q and 'q' not in exclude:
        parts.append(
            "(qr.quotation_no LIKE ? OR qr.site_name LIKE ? OR qr.description LIKE ? "
            "OR qr.client_name LIKE ? OR qr.person_in_charge LIKE ? OR qr.person_code LIKE ?)"
        )
        like = f'%{q}%'
        params.extend([like, like, like, like, like, like])
    if awarded_only and 'awarded' not in exclude:
        parts.append("qr.awarded = '中'")
    if unlinked_only and 'unlinked' not in exclude:
        parts.append("qr.project_id IS NULL")
    if source_year and 'year' not in exclude:
        parts.append("qr.source_year = ?")
        params.append(source_year)
    if person_in_charge and 'person' not in exclude:
        clause, clause_params = _person_match_clause('qr', conn, person_in_charge)
        if clause:
            parts.append(clause.replace(' AND ', '', 1))
            params.extend(clause_params)
    if doc_type and 'doc_type' not in exclude:
        parts.append("qr.doc_type = ?")
        params.append(doc_type)
    sql = (' AND ' + ' AND '.join(parts)) if parts else ''
    return sql, params


_REGISTRY_SORTABLE = {
    'quotation_no': 'qr.quotation_no',
    'quote_date': 'qr.quote_date',
    'person_in_charge': 'qr.person_in_charge',
    'doc_type': 'qr.doc_type',
    'awarded': "CASE WHEN qr.awarded = '中' THEN 1 ELSE 0 END",
    'site_name': 'qr.site_name',
    'description': 'qr.description',
    'awarded_amount': 'qr.awarded_amount',
    'project_code': 'p.project_code',
}


def _registry_order_sql(sort_by=None, sort_dir='desc'):
    """Master List 排序（NULL/空白排最後）"""
    if not sort_by or sort_by not in _REGISTRY_SORTABLE:
        return 'qr.quote_date IS NULL, qr.quote_date DESC, qr.quotation_no DESC'
    col = _REGISTRY_SORTABLE[sort_by]
    desc = (sort_dir or 'desc').lower() != 'asc'
    dir_sql = 'DESC' if desc else 'ASC'
    if sort_by == 'awarded_amount':
        return f'{col} IS NULL, {col} {dir_sql}, qr.quotation_no DESC'
    if sort_by == 'awarded':
        return f'{col} {dir_sql}, qr.quotation_no DESC'
    return f"({col} IS NULL OR trim({col}) = ''), {col} {dir_sql}, qr.quotation_no DESC"


def list_quotation_registry(q=None, awarded_only=False, unlinked_only=False,
                            source_year=None, person_in_charge=None, doc_type=None,
                            limit=100, offset=0,
                            sort_by=None, sort_dir='desc'):
    conn = get_conn()
    filt, params = _registry_filter_sql(
        conn, q, awarded_only, unlinked_only, source_year, person_in_charge, doc_type,
    )
    order_sql = _registry_order_sql(sort_by, sort_dir)
    sql = f"""
        SELECT qr.*, p.project_code, p.project_name
        FROM quotation_registry qr
        LEFT JOIN projects p ON p.id = qr.project_id
        WHERE 1=1{filt}
        ORDER BY {order_sql} LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])
    rows = conn.execute(sql, params).fetchall()

    count_sql = f"SELECT COUNT(*) FROM quotation_registry qr WHERE 1=1{filt}"
    total = conn.execute(count_sql, params[:-2]).fetchone()[0]
    conn.close()
    return {'items': [dict(r) for r in rows], 'total': total}


def get_quotation_registry_stats(q=None, awarded_only=False, unlinked_only=False,
                                 source_year=None, person_in_charge=None, doc_type=None):
    conn = get_conn()
    filt, params = _registry_filter_sql(
        conn, q, awarded_only, unlinked_only, source_year, person_in_charge, doc_type,
    )
    summary = conn.execute(f"""
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN qr.awarded = '中' THEN 1 ELSE 0 END) AS awarded_count,
            SUM(CASE WHEN qr.project_id IS NOT NULL THEN 1 ELSE 0 END) AS linked_count,
            SUM(CASE WHEN qr.project_id IS NULL THEN 1 ELSE 0 END) AS unlinked_count
        FROM quotation_registry qr
        WHERE 1=1{filt}
    """, params).fetchone()

    year_filt, year_params = _registry_filter_sql(
        conn, q, awarded_only, unlinked_only, source_year, person_in_charge, doc_type,
        exclude=frozenset({'year'}),
    )
    years = conn.execute(f"""
        SELECT qr.source_year, COUNT(*) AS cnt
        FROM quotation_registry qr
        WHERE qr.source_year IS NOT NULL{year_filt}
        GROUP BY qr.source_year ORDER BY qr.source_year DESC
    """, year_params).fetchall()

    person_filt, person_params = _registry_filter_sql(
        conn, q, awarded_only, unlinked_only, source_year, person_in_charge, doc_type,
        exclude=frozenset({'person'}),
    )
    by_person = [
        {'person_name': p['person_name'], 'cnt': p['cnt']}
        for p in _registry_by_person(conn, person_filt, person_params)
    ]

    doc_type_filt, doc_type_params = _registry_filter_sql(
        conn, q, awarded_only, unlinked_only, source_year, person_in_charge, doc_type,
        exclude=frozenset({'doc_type'}),
    )
    type_rows = conn.execute(f"""
        SELECT qr.doc_type, COUNT(*) AS cnt
        FROM quotation_registry qr
        WHERE qr.doc_type IN ('報價', '標書'){doc_type_filt}
        GROUP BY qr.doc_type ORDER BY qr.doc_type
    """, doc_type_params).fetchall()
    by_doc_type = [dict(r) for r in type_rows]

    last_import = conn.execute(
        "SELECT * FROM master_list_imports ORDER BY imported_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return {
        'total': summary['total'] or 0,
        'awarded_count': summary['awarded_count'] or 0,
        'linked_count': summary['linked_count'] or 0,
        'unlinked_count': summary['unlinked_count'] or 0,
        'by_year': [dict(y) for y in years],
        'by_person': by_person,
        'by_doc_type': by_doc_type,
        'last_import': dict(last_import) if last_import else None,
        'filters_applied': bool(filt),
    }


def record_master_list_import(data):
    conn = get_conn()
    conn.execute("""
        INSERT INTO master_list_imports
            (source_file, source_year, rows_read, rows_new, rows_updated)
        VALUES (:source_file, :source_year, :rows_read, :rows_new, :rows_updated)
    """, data)
    conn.commit()
    conn.close()


def list_master_import_history(limit=20):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM master_list_imports ORDER BY imported_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Staff roster (負責人名單 → 未來權限) ───────────────────────────────

STAFF_ACCESS_ROLES = ('admin', 'qs', 'finance', 'viewer')


def _normalize_staff_code(code):
    if not code:
        return None
    c = str(code).strip().lstrip('/').lower()
    if not c or len(c) < 2 or len(c) > 4:
        return None
    if not c.isalpha():
        return None
    return c


def _derive_staff_code(conn, name_en, name_zh):
    raw = (name_en or name_zh or 'staff').lower()
    letters = re.sub(r'[^a-z]', '', raw.replace(' ', ''))
    base = letters[:6] if len(letters) >= 2 else 'st'
    code = base
    n = 2
    while conn.execute("SELECT 1 FROM staff_members WHERE code=?", (code,)).fetchone():
        code = f'{base}{n}'
        n += 1
    return code


def list_master_person_roster(active_only=False, conn=None):
    """以 Master List 主檔為準的項目負責人名單（合併 staff_members 聯絡資料）"""
    own = conn is None
    if own:
        conn = get_conn()
    by_person = _registry_by_person(conn)
    staff_rows = [dict(r) for r in conn.execute("SELECT * FROM staff_members").fetchall()]
    staff_by_lower = {}
    for s in staff_rows:
        for n in _staff_display_names(s):
            staff_by_lower[n.lower()] = s
        key = _staff_canonical_name(s).lower()
        if key:
            staff_by_lower[key] = s

    roster = []
    for p in by_person:
        name = p['person_name']
        key = p['pic_key']
        staff = staff_by_lower.get(key) or staff_by_lower.get(name.lower())
        project_count = conn.execute(
            "SELECT COUNT(*) FROM projects WHERE lower(trim(person_in_charge))=?",
            (key,),
        ).fetchone()[0]
        entry = {
            'person_name': name,
            'quotation_count': p['cnt'],
            'project_count': project_count,
            'variant_count': p.get('variant_count', 1),
            'in_staff_table': bool(staff),
        }
        if staff:
            entry.update({
                'id': staff['id'],
                'code': staff.get('code'),
                'name_en': staff.get('name_en'),
                'name_zh': staff.get('name_zh'),
                'email': staff.get('email'),
                'phone': staff.get('phone'),
                'department': staff.get('department'),
                'access_role': staff.get('access_role', 'qs'),
                'is_active': staff.get('is_active', 1),
                'notes': staff.get('notes'),
            })
        else:
            entry.update({
                'id': None,
                'code': None,
                'name_en': name,
                'name_zh': None,
                'email': None,
                'phone': None,
                'department': None,
                'access_role': 'qs',
                'is_active': 1,
                'notes': None,
            })
        roster.append(entry)

    if active_only:
        roster = [r for r in roster if not r['in_staff_table'] or r.get('is_active')]
    if own:
        conn.close()
    return roster


def list_staff_members(active_only=False):
    return list_master_person_roster(active_only=active_only)


def get_staff_member(staff_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM staff_members WHERE id=?", (staff_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_staff_by_code(code):
    code = _normalize_staff_code(code)
    if not code:
        return None
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM staff_members WHERE code=? AND is_active=1", (code,)
    ).fetchone()
    if not row:
        row = conn.execute("SELECT * FROM staff_members WHERE code=?", (code,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_staff_name_map():
    """縮寫 → 顯示名（供 master_ref 對照）"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT code, name_en, name_zh FROM staff_members WHERE is_active=1"
    ).fetchall()
    conn.close()
    out = {}
    for r in rows:
        name = (r['name_en'] or '').strip() or (r['name_zh'] or '').strip()
        if name:
            out[r['code']] = name
    return out


def create_staff_member(data):
    data = dict(data)
    data['name_en'] = (data.get('name_en') or '').strip() or None
    data['name_zh'] = (data.get('name_zh') or '').strip() or None
    if not data['name_en'] and not data['name_zh']:
        raise ValueError('請填寫項目負責人姓名')
    if _is_pic_abbreviation_label(data['name_en'] or '') or _is_pic_abbreviation_label(data['name_zh'] or ''):
        raise ValueError('請填寫項目負責人全名，不要使用縮寫')
    data['email'] = (data.get('email') or '').strip() or None
    data['phone'] = (data.get('phone') or '').strip() or None
    data['department'] = (data.get('department') or '').strip() or None
    role = (data.get('access_role') or 'qs').strip().lower()
    data['access_role'] = role if role in STAFF_ACCESS_ROLES else 'qs'
    data['is_active'] = 1 if data.get('is_active', 1) else 0
    data['notes'] = (data.get('notes') or '').strip() or None
    conn = get_conn()
    canon = (data['name_en'] or data['name_zh'] or '').strip()
    dup = conn.execute("""
        SELECT id FROM staff_members
        WHERE is_active = 1 AND lower(trim(COALESCE(name_en, name_zh, ''))) = lower(trim(?))
    """, (canon,)).fetchone()
    if dup:
        conn.close()
        raise ValueError(f'項目負責人「{canon}」已存在')
    code = _normalize_staff_code(data.get('code'))
    if not code:
        code = _derive_staff_code(conn, data['name_en'], data['name_zh'])
    data['code'] = code
    try:
        cur = conn.execute("""
            INSERT INTO staff_members
                (code, name_en, name_zh, email, phone, department, access_role, is_active, notes)
            VALUES (:code, :name_en, :name_zh, :email, :phone, :department, :access_role, :is_active, :notes)
        """, data)
        conn.commit()
        new_id = cur.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        raise ValueError('內部代碼衝突，請稍後再試')
    conn.close()
    from master_ref import invalidate_staff_name_cache
    invalidate_staff_name_cache()
    return new_id


def update_staff_member(staff_id, data):
    existing = get_staff_member(staff_id)
    if not existing:
        return False
    data = dict(data)
    data['name_en'] = (data.get('name_en') or '').strip() or None
    data['name_zh'] = (data.get('name_zh') or '').strip() or None
    if not data['name_en'] and not data['name_zh']:
        raise ValueError('請填寫項目負責人姓名')
    if _is_pic_abbreviation_label(data['name_en'] or '') or _is_pic_abbreviation_label(data['name_zh'] or ''):
        raise ValueError('請填寫項目負責人全名，不要使用縮寫')
    data['email'] = (data.get('email') or '').strip() or None
    data['phone'] = (data.get('phone') or '').strip() or None
    data['department'] = (data.get('department') or '').strip() or None
    role = (data.get('access_role') or existing['access_role'] or 'qs').strip().lower()
    data['access_role'] = role if role in STAFF_ACCESS_ROLES else 'qs'
    data['is_active'] = 1 if data.get('is_active', existing.get('is_active', 1)) else 0
    data['notes'] = (data.get('notes') or '').strip() or None
    data['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    canon = (data['name_en'] or data['name_zh'] or '').strip()
    conn = get_conn()
    dup = conn.execute("""
        SELECT id FROM staff_members
        WHERE is_active = 1 AND id != ? AND lower(trim(COALESCE(name_en, name_zh, ''))) = lower(trim(?))
    """, (staff_id, canon)).fetchone()
    if dup:
        conn.close()
        raise ValueError(f'項目負責人「{canon}」已存在')
    conn.execute("""
        UPDATE staff_members SET
            name_en=:name_en, name_zh=:name_zh, email=:email, phone=:phone,
            department=:department, access_role=:access_role, is_active=:is_active,
            notes=:notes, updated_at=:updated_at
        WHERE id=:id
    """, {**data, 'id': staff_id})
    conn.commit()
    conn.close()
    from master_ref import invalidate_staff_name_cache
    invalidate_staff_name_cache()
    return True


def deactivate_staff_member(staff_id):
    return update_staff_member(staff_id, {'is_active': 0})


if __name__ == '__main__':
    init_db()
    print("[DB] 初始化完成")
