"""
database.py — QS管理系統資料庫模組
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS interim_payment_sc_lines (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id  INTEGER NOT NULL,
            ip_no       TEXT NOT NULL,
            sc_no       TEXT NOT NULL,
            amount      REAL DEFAULT 0,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            UNIQUE(project_id, ip_no, sc_no)
        )
    """)
    ip_cols = {r[1] for r in conn.execute("PRAGMA table_info(interim_payments)")}
    for col, ddl in [
        ('receipt_method', 'TEXT'),
        ('receipt_cheque_no', 'TEXT'),
        ('receipt_bank', 'TEXT'),
        ('receipt_date', 'TEXT'),
        ('receipt_note', 'TEXT'),
        ('receipt_attachment', 'TEXT'),
        ('receipt_attachment_name', 'TEXT'),
        ('ip_cert_attachment', 'TEXT'),
        ('ip_cert_attachment_name', 'TEXT'),
    ]:
        if col not in ip_cols:
            conn.execute(f"ALTER TABLE interim_payments ADD COLUMN {col} {ddl}")
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
    if 'trade_label' not in cols:
        conn.execute("ALTER TABLE subcontractors ADD COLUMN trade_label TEXT")
    sc_cols = {r[1] for r in conn.execute("PRAGMA table_info(subcontractors)")}
    if 'sc_entry_type' not in sc_cols:
        conn.execute("ALTER TABLE subcontractors ADD COLUMN sc_entry_type TEXT DEFAULT 'quotation'")
    if 'retention_sum' not in sc_cols:
        conn.execute("ALTER TABLE subcontractors ADD COLUMN retention_sum REAL")
    if 'sub_contract_no' not in sc_cols:
        conn.execute("ALTER TABLE subcontractors ADD COLUMN sub_contract_no TEXT")
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
        CREATE TABLE IF NOT EXISTS sc_contract_registry (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            sub_contract_no     TEXT NOT NULL UNIQUE,
            company             TEXT,
            works               TEXT,
            project_code        TEXT,
            project_core        TEXT,
            amount              REAL DEFAULT 0,
            sheet               TEXT,
            source_file         TEXT,
            updated_at          TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sc_contract_imports (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file     TEXT,
            rows_read       INTEGER DEFAULT 0,
            rows_new        INTEGER DEFAULT 0,
            rows_updated    INTEGER DEFAULT 0,
            imported_at     TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_scr_project_core ON sc_contract_registry(project_core)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_scr_project_code ON sc_contract_registry(project_code)"
    )
    scr_cols = {r[1] for r in conn.execute("PRAGMA table_info(sc_contract_registry)")}
    for col, typ in (
        ('legacy_contract_no', 'TEXT'),
        ('person_in_charge', 'TEXT'),
        ('person_code', 'TEXT'),
        ('countersign', 'TEXT'),
        ('partner', 'TEXT'),
        ('tender_minutes', 'TEXT'),
        ('final_account', 'TEXT'),
        ('final_account_statement', 'TEXT'),
        ('iso_flag', 'TEXT'),
        ('remark', 'TEXT'),
    ):
        if col not in scr_cols:
            conn.execute(f"ALTER TABLE sc_contract_registry ADD COLUMN {col} {typ}")
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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_qr_source_year ON quotation_registry(source_year)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_qr_quote_date ON quotation_registry(quote_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_qr_person ON quotation_registry(person_in_charge)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_qr_doc_type ON quotation_registry(doc_type)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_qr_project_id ON quotation_registry(project_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_qr_awarded ON quotation_registry(awarded)")
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
    pay_cols = {r[1] for r in conn.execute("PRAGMA table_info(payment_records)")}
    if 'payment_type' not in pay_cols:
        conn.execute(
            "ALTER TABLE payment_records ADD COLUMN payment_type TEXT DEFAULT 'normal'"
        )
    if 'backcharge_amount' not in pay_cols:
        conn.execute(
            "ALTER TABLE payment_records ADD COLUMN backcharge_amount REAL DEFAULT 0"
        )
    conn.execute("""
        UPDATE payment_records SET payment_type='normal'
        WHERE payment_type IS NULL OR payment_type=''
    """)
    pay_cols = {r[1] for r in conn.execute("PRAGMA table_info(payment_records)")}
    if 'deduction_ids_json' not in pay_cols:
        conn.execute("ALTER TABLE payment_records ADD COLUMN deduction_ids_json TEXT")
    if 'deduction_total' not in pay_cols:
        conn.execute("ALTER TABLE payment_records ADD COLUMN deduction_total REAL DEFAULT 0")
    if 'interim_cert_json' not in pay_cols:
        conn.execute("ALTER TABLE payment_records ADD COLUMN interim_cert_json TEXT")
    if 'vo_ids_json' not in pay_cols:
        conn.execute("ALTER TABLE payment_records ADD COLUMN vo_ids_json TEXT")
    pay_cols = {r[1] for r in conn.execute("PRAGMA table_info(payment_records)")}
    if 'revoked_at' not in pay_cols:
        conn.execute("ALTER TABLE payment_records ADD COLUMN revoked_at TEXT")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sc_vo_records (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id          INTEGER NOT NULL,
            sc_id               INTEGER,
            sc_no               TEXT NOT NULL,
            record_type         TEXT NOT NULL DEFAULT 'deduction',
            ref_no              TEXT,
            description         TEXT,
            amount              REAL DEFAULT 0,
            line_code           TEXT,
            applied_payment_id  INTEGER,
            created_at          TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (applied_payment_id) REFERENCES payment_records(id) ON DELETE SET NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_svr_project_sc
        ON sc_vo_records(project_id, sc_no)
    """)
    conn.commit()
    svr_cols = {r[1] for r in conn.execute("PRAGMA table_info(sc_vo_records)")}
    if 'line_code' not in svr_cols:
        conn.execute("ALTER TABLE sc_vo_records ADD COLUMN line_code TEXT")
    _svr_extra_cols = {
        'seq_no': 'TEXT',
        'invoice_date': 'TEXT',
        'invoice_no': 'TEXT',
        'quotation_no': 'TEXT',
        'company_name_en': 'TEXT',
        'company_name_zh': 'TEXT',
        'service_description': 'TEXT',
        'oa_ref': 'TEXT',
        'oa_no': 'TEXT',
        'remark': 'TEXT',
        'main_contract_vo_no': 'TEXT',
        'approval_attachment': 'TEXT',
        'approval_attachment_name': 'TEXT',
        'quotation_attachment': 'TEXT',
        'quotation_attachment_name': 'TEXT',
    }
    for col, typ in _svr_extra_cols.items():
        if col not in svr_cols:
            conn.execute(f"ALTER TABLE sc_vo_records ADD COLUMN {col} {typ}")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sc_vo_template_catalog (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            code            TEXT NOT NULL UNIQUE,
            source          TEXT NOT NULL,
            record_type     TEXT,
            ref_no          TEXT,
            description     TEXT,
            cert_label      TEXT,
            group_name      TEXT,
            direction       TEXT,
            sort_order      INTEGER DEFAULT 0,
            is_builtin      INTEGER DEFAULT 0,
            is_active       INTEGER DEFAULT 1,
            updated_at      TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    conn.commit()
    seed_sc_vo_template_catalog(conn)
    _migrate_cover_page_fields(conn)
    _migrate_engineering_categories(conn)
    _migrate_master_trade_categories(conn)
    _migrate_trade_scope_fields(conn)
    _migrate_main_fac_fields(conn)
    _migrate_iso_documents(conn)
    _migrate_iso_documents_v2(conn)


def _migrate_main_fac_fields(conn):
    from main_fac import MAIN_FAC_MIGRATIONS
    cols = {r[1] for r in conn.execute("PRAGMA table_info(projects)")}
    for name, ddl in MAIN_FAC_MIGRATIONS:
        if name not in cols:
            conn.execute(f"ALTER TABLE projects ADD COLUMN {name} {ddl}")
    conn.commit()


def _migrate_iso_documents(conn):
    """ISO 文件登記 — 主合約／分判附件槽位"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS iso_document_files (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id          INTEGER NOT NULL,
            scope               TEXT NOT NULL,
            subcontractor_id    INTEGER,
            doc_slot            TEXT NOT NULL,
            file_path           TEXT NOT NULL,
            original_filename   TEXT,
            created_at          TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at          TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY (subcontractor_id) REFERENCES subcontractors(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_iso_doc_unique_slot
        ON iso_document_files(project_id, scope, IFNULL(subcontractor_id, 0), doc_slot)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_iso_doc_project
        ON iso_document_files(project_id)
    """)
    conn.commit()


def _migrate_iso_documents_v2(conn):
    """ISO Sprint C — 連結模式、版本歷史"""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(iso_document_files)")}
    for name, ddl in [
        ('storage_type', "TEXT DEFAULT 'file'"),
        ('external_url', 'TEXT'),
        ('link_label', 'TEXT'),
    ]:
        if name not in cols:
            conn.execute(f"ALTER TABLE iso_document_files ADD COLUMN {name} {ddl}")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS iso_document_versions (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id          INTEGER NOT NULL,
            scope               TEXT NOT NULL,
            subcontractor_id    INTEGER,
            doc_slot            TEXT NOT NULL,
            file_path           TEXT,
            original_filename   TEXT,
            external_url        TEXT,
            storage_type        TEXT,
            archived_at         TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_iso_doc_versions_slot
        ON iso_document_versions(project_id, scope, IFNULL(subcontractor_id, 0), doc_slot)
    """)
    conn.commit()


def iso_safe_project_code(project_code):
    import re
    s = (project_code or 'project').strip()
    s = s.replace('/', '_').replace('\\', '_')
    s = re.sub(r'[^\w\-]+', '_', s)
    s = re.sub(r'_+', '_', s).strip('_')
    return (s[:80] or 'project')


def _archive_iso_slot(conn, project_id, scope, doc_slot, subcontractor_id):
    row = conn.execute("""
        SELECT file_path, original_filename, external_url, storage_type
        FROM iso_document_files
        WHERE project_id=? AND scope=? AND IFNULL(subcontractor_id, 0)=IFNULL(?, 0) AND doc_slot=?
    """, (project_id, scope, subcontractor_id, doc_slot)).fetchone()
    if not row:
        return
    d = dict(row)
    if not (d.get('file_path') or d.get('external_url')):
        return
    conn.execute("""
        INSERT INTO iso_document_versions
            (project_id, scope, subcontractor_id, doc_slot, file_path, original_filename,
             external_url, storage_type)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        project_id, scope, subcontractor_id, doc_slot,
        d.get('file_path'), d.get('original_filename'),
        d.get('external_url'), d.get('storage_type') or 'file',
    ))


ISO_MAIN_SLOTS = (
    'main_contract_loa',
    'supplemental_optional',
    'partner_list',
    'mou',
    'nda',
    'mepo_tmc',
    'hkmo_tmc',
    'tender_signoff',
    'other',
)

ISO_SC_SLOTS = (
    'tender_confirm',
    'tender_collect',
    'tender_opening',
    'mepo_tmc',
    'hkmo_tmc',
    'contract_signoff',
    'other',
)

# 實體檔名用（uploads/iso/{project_code}/）
ISO_SLOT_DISK_LABELS = {
    'main_contract_loa': '主合約LOA',
    'supplemental_optional': '補充合約Optional',
    'partner_list': '合作伙伴名單',
    'mou': 'MOU',
    'nda': 'NDA',
    'mepo_tmc': '美博TMC',
    'hkmo_tmc': '港澳TMC',
    'tender_signoff': '投標會簽',
    'other': '其他',
    'tender_confirm': '承判確認',
    'tender_collect': '領取標書',
    'tender_opening': '開標記錄',
    'contract_signoff': '合約會簽',
}


def iso_slot_disk_label(doc_slot):
    return ISO_SLOT_DISK_LABELS.get(doc_slot, doc_slot or 'ISO文件')


def _migrate_cover_page_fields(conn):
    """Cover Page / Summary 工程項目主檔欄位（QS 優化第一期 第2–6頁）"""
    from project_cover import PROJECT_COVER_MIGRATIONS, derive_mp_contract_code

    cols = {r[1] for r in conn.execute("PRAGMA table_info(projects)")}
    for name, ddl in PROJECT_COVER_MIGRATIONS:
        if name not in cols:
            conn.execute(f"ALTER TABLE projects ADD COLUMN {name} {ddl}")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS project_documents (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id          INTEGER NOT NULL,
            doc_category        TEXT NOT NULL,
            file_path           TEXT NOT NULL,
            original_filename   TEXT,
            notes               TEXT,
            created_at          TEXT DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_project_documents_project
        ON project_documents(project_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_projects_account_code
        ON projects(account_code)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_projects_mp_contract_code
        ON projects(mp_contract_code)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS project_mp_contracts (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id       INTEGER NOT NULL,
            mp_contract_code TEXT NOT NULL,
            seq_no           INTEGER DEFAULT 1,
            is_primary       INTEGER DEFAULT 0,
            contract_amount  REAL,
            notes            TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
            UNIQUE(project_id, mp_contract_code)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_pmc_project
        ON project_mp_contracts(project_id)
    """)
    for row in conn.execute("""
        SELECT id, quotation_no, project_code, person_in_charge,
               qs_in_charge, mp_contract_code, start_date, mp_commencement_date
        FROM projects
    """).fetchall():
        r = dict(row)
        sets, vals = [], []
        if not r.get('mp_contract_code'):
            code = derive_mp_contract_code(r.get('quotation_no'), r.get('project_code'))
            if code:
                sets.append('mp_contract_code=?')
                vals.append(code)
        if r.get('person_in_charge') and not r.get('qs_in_charge'):
            sets.append('qs_in_charge=?')
            vals.append(r['person_in_charge'])
        if r.get('start_date') and not r.get('mp_commencement_date'):
            sets.append('mp_commencement_date=?')
            vals.append(r['start_date'])
        if sets:
            vals.append(r['id'])
            conn.execute(
                f"UPDATE projects SET {', '.join(sets)} WHERE id=?",
                vals,
            )
    conn.commit()


def _migrate_master_trade_categories(conn):
    """Master List 工作範疇選項（Excel I/J 欄已有資料）"""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(master_trade_categories)").fetchall()}
    if cols and 'field_type' not in cols:
        conn.execute("DROP TABLE master_trade_categories")
        cols = set()
    if not cols:
        conn.execute("""
            CREATE TABLE master_trade_categories (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                field_type      TEXT NOT NULL,
                name_zh         TEXT NOT NULL,
                use_count       INTEGER DEFAULT 0,
                sort_order      INTEGER DEFAULT 0,
                is_active       INTEGER DEFAULT 1,
                source_file     TEXT,
                updated_at      TEXT DEFAULT (datetime('now', 'localtime')),
                UNIQUE(field_type, name_zh)
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_master_trade_type ON master_trade_categories(field_type)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_master_trade_active ON master_trade_categories(is_active)"
        )
    cols = {r[1] for r in conn.execute("PRAGMA table_info(master_trade_categories)").fetchall()}
    if 'group_name' not in cols:
        conn.execute("ALTER TABLE master_trade_categories ADD COLUMN group_name TEXT")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_master_trade_group ON master_trade_categories(group_name)"
        )


def _migrate_trade_scope_fields(conn):
    """報價／標書：工作範疇 I 欄 + 重新輸入 J 欄"""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(quotation_registry)").fetchall()}
    if 'trade_scope' not in cols:
        conn.execute("ALTER TABLE quotation_registry ADD COLUMN trade_scope TEXT")
    if 'trade_override' not in cols:
        conn.execute("ALTER TABLE quotation_registry ADD COLUMN trade_override TEXT")


def _migrate_engineering_categories(conn):
    """美博工程標準分類表（R1）"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS engineering_categories (
            l2_code       TEXT PRIMARY KEY,
            l1_code       TEXT NOT NULL,
            l1_name_zh    TEXT,
            l1_name_en    TEXT,
            l2_name_zh    TEXT,
            l2_name_en    TEXT,
            scope         TEXT,
            sort_order    INTEGER DEFAULT 0,
            source_file   TEXT,
            updated_at    TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_eng_cat_l1 ON engineering_categories(l1_code)"
    )
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_projects_category_l2
        ON projects(category_l2_code)
    """)


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


def _project_cover_defaults(data, existing=None):
    """Cover Page 欄位預設與衍生值"""
    from project_cover import PROJECT_COVER_WRITABLE, derive_mp_contract_code

    existing = existing or {}
    for field in PROJECT_COVER_WRITABLE:
        if field in data:
            continue
        if field in existing:
            data[field] = existing[field]
        elif field == 'tender_sum':
            data[field] = 0
        else:
            data[field] = None
    if not data.get('mp_contract_code'):
        data['mp_contract_code'] = derive_mp_contract_code(
            data.get('quotation_no') or existing.get('quotation_no'),
            data.get('project_code') or existing.get('project_code'),
        )
    if not data.get('qs_in_charge'):
        data['qs_in_charge'] = data.get('person_in_charge') or existing.get('person_in_charge')
    mode = data.get('retention_release_mode')
    if mode is not None:
        data['retention_release_mode'] = (mode or 'na').strip().lower() or 'na'
    return data


_PROJECT_INSERT_COLS = (
    'project_code', 'project_name', 'project_name_en', 'project_name_zh',
    'client', 'main_contractor', 'contract_amount', 'labour_allocation',
    'start_date', 'status', 'notes',
    'quotation_no', 'person_code', 'person_in_charge', 'site_period_text',
)


def _project_insert_sql():
    from project_cover import PROJECT_COVER_WRITABLE
    cols = list(_PROJECT_INSERT_COLS) + list(PROJECT_COVER_WRITABLE)
    placeholders = ', '.join(f':{c}' for c in cols)
    return f"INSERT INTO projects ({', '.join(cols)}) VALUES ({placeholders})", cols


def _primary_quotation_join(alias='qr'):
    """每個 project 只 JOIN 一筆 Master List，避免多配對時 Summary 重複列"""
    return f"""
        LEFT JOIN quotation_registry {alias} ON {alias}.id = (
            SELECT id FROM quotation_registry
            WHERE project_id = p.id
            ORDER BY quote_date DESC, quotation_no
            LIMIT 1
        )
    """


def _enrich_project(row):
    """合併 Master List 配對欄位（報價編號、負責人）及工程分類標籤"""
    d = dict(row)
    if not d.get('quotation_no') and d.get('reg_quotation_no'):
        d['quotation_no'] = d['reg_quotation_no']
    if not d.get('person_code') and d.get('reg_person_code'):
        d['person_code'] = d['reg_person_code']
    if not d.get('person_in_charge') and d.get('reg_person_in_charge'):
        d['person_in_charge'] = d['reg_person_in_charge']
    for k in ('reg_quotation_no', 'reg_person_code', 'reg_person_in_charge'):
        d.pop(k, None)
    _attach_project_category_labels(d)
    return d


def _attach_project_category_labels(project: dict, conn=None) -> dict:
    l2 = (project.get('category_l2_code') or '').strip()
    if not l2:
        project.setdefault('category_l1_label', None)
        project.setdefault('category_l2_label', None)
        return project
    own_conn = conn is None
    if own_conn:
        conn = get_conn()
    row = conn.execute(
        "SELECT * FROM engineering_categories WHERE l2_code=?",
        (l2,),
    ).fetchone()
    if own_conn:
        conn.close()
    if row:
        from engineering_category_ref import category_display_label
        cat = dict(row)
        project['category_l1_label'] = category_display_label(cat, 'l1')
        project['category_l2_label'] = category_display_label(cat, 'l2')
        if not project.get('category_l1_code'):
            project['category_l1_code'] = cat.get('l1_code')
    else:
        project.setdefault('category_l1_label', None)
        project.setdefault('category_l2_label', l2)
    return project


def get_all_projects():
    conn = get_conn()
    rows = conn.execute(f"""
        SELECT p.*,
               qr.quotation_no AS reg_quotation_no,
               qr.person_code AS reg_person_code,
               qr.person_in_charge AS reg_person_in_charge,
               (SELECT COUNT(*) FROM subcontractors sc WHERE sc.project_id = p.id) AS sc_count,
               (SELECT COALESCE(SUM(pr.paid_amount), 0)
                FROM payment_records pr
                WHERE pr.project_id = p.id AND (pr.revoked_at IS NULL OR pr.revoked_at = '')) AS total_paid
        FROM projects p
        {_primary_quotation_join()}
        ORDER BY p.created_at DESC
    """).fetchall()
    conn.close()
    return [_enrich_project(r) for r in rows]


def get_project(project_id):
    conn = get_conn()
    row = conn.execute(f"""
        SELECT p.*,
               qr.quotation_no AS reg_quotation_no,
               qr.person_code AS reg_person_code,
               qr.person_in_charge AS reg_person_in_charge
        FROM projects p
        {_primary_quotation_join()}
        WHERE p.id=?
    """, (project_id,)).fetchone()
    if not row:
        conn.close()
        return None
    mp_rows = conn.execute("""
        SELECT mp_contract_code, seq_no, is_primary
        FROM project_mp_contracts WHERE project_id=?
        ORDER BY seq_no, id
    """, (project_id,)).fetchall()
    conn.close()
    d = _enrich_project(row)
    codes = [r['mp_contract_code'] for r in mp_rows]
    d['mp_contract_codes'] = codes
    from project_cover import format_mp_contract_label
    d['mp_contract_label'], _ = format_mp_contract_label(mp_rows, d.get('mp_contract_code'))
    return d


def _maybe_link_quotation(quotation_no, project_id, sync_project_code=True):
    """僅當 Master List 存在該報價編號時才配對"""
    if not quotation_no:
        return
    if get_quotation_by_no(quotation_no):
        link_quotation_to_project(quotation_no, project_id, sync_project_code=sync_project_code)


def _find_project_for_summary(conn, row):
    """依會計編號 / MP合約編號 / project_code 配對既有項目"""
    from project_cover import derive_mp_contract_code

    acc = (row.get('account_code') or '').strip()
    mp = (row.get('mp_contract_code') or '').strip().upper()
    if acc:
        hit = conn.execute(
            "SELECT id FROM projects WHERE account_code=? COLLATE NOCASE LIMIT 1",
            (acc,),
        ).fetchone()
        if hit:
            return hit['id']
    if mp:
        hit = conn.execute(
            "SELECT id FROM projects WHERE UPPER(mp_contract_code)=? LIMIT 1",
            (mp,),
        ).fetchone()
        if hit:
            return hit['id']
        hit = conn.execute(
            "SELECT id FROM projects WHERE UPPER(project_code)=? LIMIT 1",
            (mp,),
        ).fetchone()
        if hit:
            return hit['id']
        for prow in conn.execute(
            "SELECT id, project_code, quotation_no FROM projects"
        ).fetchall():
            derived = derive_mp_contract_code(prow['quotation_no'], prow['project_code'])
            if derived and derived.upper() == mp:
                return prow['id']
    return None


def get_project_mp_contracts(project_id):
    conn = get_conn()
    rows = conn.execute("""
        SELECT id, project_id, mp_contract_code, seq_no, is_primary, contract_amount, notes
        FROM project_mp_contracts
        WHERE project_id=?
        ORDER BY seq_no, id
    """, (project_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def replace_project_mp_contracts(project_id, codes, amounts=None):
    """
    一個會計項目下多個 MP 合約編號（如 N23 有 Q0231_24…）
    codes: 有序 list；第一個為 is_primary，並回寫 projects.mp_contract_code
    """
    conn = get_conn()
    conn.execute("DELETE FROM project_mp_contracts WHERE project_id=?", (project_id,))
    normalized = []
    for raw in codes or []:
        c = (raw or '').strip().upper()
        if c and c not in normalized:
            normalized.append(c)
    amounts = amounts or {}
    for i, code in enumerate(normalized):
        conn.execute("""
            INSERT INTO project_mp_contracts
                (project_id, mp_contract_code, seq_no, is_primary, contract_amount)
            VALUES (?, ?, ?, ?, ?)
        """, (
            project_id, code, i + 1, 1 if i == 0 else 0,
            amounts.get(code),
        ))
    if normalized:
        conn.execute(
            "UPDATE projects SET mp_contract_code=? WHERE id=?",
            (normalized[0], project_id),
        )
    conn.commit()
    conn.close()
    return normalized


def upsert_summary_project(row, update_existing=True):
    """Summary 單列 upsert → projects"""
    mp = (row.get('mp_contract_code') or '').strip().upper() or None
    acc = (row.get('account_code') or '').strip() or None
    title = (row.get('project_name_zh') or '').strip()
    client = (row.get('client') or '').strip() or None
    client2 = (row.get('client_secondary') or '').strip() or None
    mc = (row.get('main_contractor') or '').strip() or None
    work_type = row.get('work_type')
    amount = float(row.get('contract_amount') or 0)
    notes = row.get('notes')
    mp_codes = row.get('mp_contract_codes') or ([mp] if mp else [])

    conn = get_conn()
    pid = _find_project_for_summary(conn, row)
    action = 'skipped'

    if pid:
        if not update_existing:
            conn.close()
            return {'action': 'skipped', 'project_id': pid, 'account_code': acc, 'mp_contract_code': mp}
        existing = dict(conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone())
        data = dict(existing)
        if mp:
            data['mp_contract_code'] = mp
        if acc:
            data['account_code'] = acc
        if title:
            data['project_name_zh'] = title
            if data.get('project_name_en'):
                data['project_name'] = f"{data['project_name_en']} · {title}"
            else:
                data['project_name'] = title
        if client:
            data['client'] = client.rstrip('/').strip()
        if client2:
            data['client_secondary'] = client2.rstrip('/').strip()
        if mc:
            data['main_contractor'] = mc
        if work_type:
            data['work_type'] = work_type
        if amount:
            data['contract_amount'] = amount
        if notes and not existing.get('notes'):
            data['notes'] = notes
        conn.close()
        update_project(pid, data)
        replace_project_mp_contracts(pid, mp_codes)
        action = 'updated'
    else:
        code = mp or acc or title[:40]
        payload = {
            'project_code': code,
            'project_name_zh': title or code,
            'project_name_en': None,
            'client': client.rstrip('/').strip() if client else None,
            'client_secondary': client2.rstrip('/').strip() if client2 else None,
            'main_contractor': mc,
            'contract_amount': amount,
            'work_type': work_type,
            'account_code': acc,
            'mp_contract_code': mp,
            'status': 'Active',
            'notes': notes,
            'labour_allocation': 0,
            'start_date': None,
            'quotation_no': None,
            'person_code': None,
            'person_in_charge': None,
            'site_period_text': None,
        }
        conn.close()
        pid = create_project(payload)
        replace_project_mp_contracts(pid, mp_codes)
        action = 'created'

    return {
        'action': action,
        'project_id': pid,
        'account_code': acc,
        'mp_contract_code': mp,
        'mp_contract_codes': mp_codes,
        'main_contract_title': title,
    }


def create_project(data):
    mp_codes = data.pop('mp_contract_codes', None)
    data = _normalize_project_fields(dict(data))
    data.setdefault('quotation_no', None)
    data.setdefault('person_code', None)
    data.setdefault('person_in_charge', None)
    data.setdefault('labour_allocation', 0)
    data.setdefault('site_period_text', None)
    data = _project_cover_defaults(data)
    from master_ref import enrich_person_fields
    enrich_person_fields(data)
    conn = get_conn()
    sql, _cols = _project_insert_sql()
    cur = conn.execute(sql, data)
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    if mp_codes is not None:
        replace_project_mp_contracts(new_id, mp_codes)
    elif data.get('mp_contract_code'):
        replace_project_mp_contracts(new_id, [data['mp_contract_code']])
    if data.get('quotation_no'):
        _maybe_link_quotation(data['quotation_no'], new_id, sync_project_code=True)
    return new_id


def update_project(project_id, data):
    mp_codes = data.pop('mp_contract_codes', None)
    existing = get_project(project_id) or {}
    data = _normalize_project_fields(dict(data))
    data.setdefault('quotation_no', None)
    data.setdefault('person_code', None)
    data.setdefault('person_in_charge', None)
    if 'labour_allocation' not in data:
        data['labour_allocation'] = existing.get('labour_allocation') or 0
    if 'site_period_text' not in data:
        data['site_period_text'] = existing.get('site_period_text')
    data = _project_cover_defaults(data, existing)
    from master_ref import enrich_person_fields
    enrich_person_fields(data)
    from project_cover import PROJECT_COVER_WRITABLE
    set_parts = [
        'project_code=:project_code', 'project_name=:project_name',
        'project_name_en=:project_name_en', 'project_name_zh=:project_name_zh',
        'client=:client', 'main_contractor=:main_contractor',
        'contract_amount=:contract_amount', 'labour_allocation=:labour_allocation',
        'start_date=:start_date', 'status=:status', 'notes=:notes',
        'quotation_no=:quotation_no', 'person_code=:person_code',
        'person_in_charge=:person_in_charge', 'site_period_text=:site_period_text',
    ]
    set_parts.extend(f'{f}=:{f}' for f in PROJECT_COVER_WRITABLE)
    conn = get_conn()
    conn.execute(
        f"UPDATE projects SET {', '.join(set_parts)} WHERE id=:id",
        {**data, 'id': project_id},
    )
    conn.commit()
    conn.close()
    if mp_codes is not None:
        normalized = replace_project_mp_contracts(project_id, mp_codes)
        if normalized:
            data['mp_contract_code'] = normalized[0]
    qno = data.get('quotation_no')
    if qno:
        _maybe_link_quotation(qno, project_id, sync_project_code=True)


def update_project_doc_library_url(project_id, url):
    conn = get_conn()
    val = (url or '').strip() or None
    conn.execute("UPDATE projects SET doc_library_url=? WHERE id=?", (val, project_id))
    conn.commit()
    conn.close()


def delete_project(project_id):
    conn = get_conn()
    conn.execute("DELETE FROM projects WHERE id=?", (project_id,))
    conn.commit()
    conn.close()


def set_project_labour_allocation(project_id, labour):
    """更新項目人工分攤 (C1)"""
    conn = get_conn()
    conn.execute(
        "UPDATE projects SET labour_allocation=? WHERE id=?",
        (float(labour or 0), project_id),
    )
    conn.commit()
    conn.close()


def get_company_summary():
    """第2頁 Summary — 全公司項目總表"""
    from project_cover import compute_settlement, format_summary_row

    conn = get_conn()
    projects = conn.execute(f"""
        SELECT p.*,
               qr.quotation_no AS reg_quotation_no,
               qr.person_code AS reg_person_code,
               qr.person_in_charge AS reg_person_in_charge,
               (SELECT COUNT(*) FROM quotation_registry lq WHERE lq.project_id = p.id) AS linked_quotation_count,
               (SELECT COUNT(*) FROM subcontractors sc WHERE sc.project_id = p.id) AS sc_count,
               (SELECT COALESCE(SUM(pr.paid_amount), 0)
                FROM payment_records pr
                WHERE pr.project_id = p.id AND (pr.revoked_at IS NULL OR pr.revoked_at = '')) AS total_paid
        FROM projects p
        {_primary_quotation_join()}
        ORDER BY COALESCE(p.account_code, ''), p.mp_contract_code, p.project_code
    """).fetchall()
    rows = []
    for prow in projects:
        project = _enrich_project(prow)
        pid = project['id']
        sc_rows = conn.execute(
            "SELECT sc_no, contract_amount, is_excluded FROM subcontractors WHERE project_id=?",
            (pid,),
        ).fetchall()
        settlement = compute_settlement(project, [dict(s) for s in sc_rows])
        mp_rows = conn.execute("""
            SELECT mp_contract_code, seq_no, is_primary
            FROM project_mp_contracts WHERE project_id=?
            ORDER BY seq_no, id
        """, (pid,)).fetchall()
        project['mp_contract_codes'] = [dict(r) for r in mp_rows]
        rows.append(format_summary_row(project, settlement))
    conn.close()
    return rows


def get_cover_page(project_id):
    """Cover Page 主檔（第4–6頁）含 A–E 結算"""
    from project_cover import build_cover_page

    project = get_project(project_id)
    if not project:
        return None
    conn = get_conn()
    sc_rows = conn.execute(
        "SELECT sc_no, contract_amount, is_excluded FROM subcontractors WHERE project_id=?",
        (project_id,),
    ).fetchall()
    docs = conn.execute(
        """SELECT id, doc_category, file_path, original_filename, notes, created_at
           FROM project_documents WHERE project_id=? ORDER BY created_at DESC""",
        (project_id,),
    ).fetchall()
    conn.close()
    return build_cover_page(
        project,
        [dict(s) for s in sc_rows],
        [dict(d) for d in docs],
    )


def _sc_vo_totals_for_project(project_id):
    conn = get_conn()
    vo = conn.execute("""
        SELECT COALESCE(SUM(amount), 0) FROM sc_vo_records
        WHERE project_id=? AND record_type='vo'
    """, (project_id,)).fetchone()[0]
    ded = conn.execute("""
        SELECT COALESCE(SUM(amount), 0) FROM sc_vo_records
        WHERE project_id=? AND record_type='deduction'
    """, (project_id,)).fetchone()[0]
    conn.close()
    return {'vo_total': float(vo or 0), 'deduction_total': float(ded or 0)}


def get_main_con_fac(project_id):
    from main_fac import build_main_con_fac

    project = get_project(project_id)
    if not project:
        return None
    vo_totals = _sc_vo_totals_for_project(project_id)
    interim_items = get_interim_payments(project_id)
    return build_main_con_fac(project, vo_totals, interim_items)


def _sc_vo_for_sc(project_id, sc_no):
    from sc_fac import _match_sc_no
    records = get_sc_vo_records(project_id)
    return [r for r in records if _match_sc_no(r.get('sc_no'), sc_no)]


def get_sc_fac(project_id, sc_id):
    from sc_fac import build_sc_fac

    project = get_project(project_id)
    sc = get_subcontractor(sc_id)
    if not project or not sc or sc.get('project_id') != project_id:
        return None
    if sc.get('is_excluded'):
        return None
    sc_no = sc.get('sc_no')
    vo_records = _sc_vo_for_sc(project_id, sc_no)
    payments = [
        p for p in get_payments(project_id, {'sc_no': sc_no})
        if not p.get('revoked_at')
    ]
    interim_count = count_interim_certs_for_sc(project_id, sc_no)
    all_scs = get_subcontractors(project_id)
    return build_sc_fac(project, sc, vo_records, payments, interim_count, project_subcontractors=all_scs)


def list_sc_fac_items(project_id):
    from sc_contract_ref import classify_contract_align, project_orphan_refs

    project = get_project(project_id)
    all_scs = get_subcontractors(project_id)
    items = []
    for sc in all_scs:
        if sc.get('is_excluded'):
            continue
        fac = get_sc_fac(project_id, sc['id'])
        if not fac:
            continue
        st = fac['settlement']
        meta = fac.get('appendix_meta') or {}
        sub_no = (fac.get('header') or {}).get('sub_contract_no') or '—'
        items.append({
            'sc_id': sc['id'],
            'sc_no': sc.get('sc_no'),
            'company_name_en': sc.get('company_name_en'),
            'company_name_zh': sc.get('company_name_zh'),
            'sub_contract_no': sub_no,
            'contract_align': classify_contract_align(sc, sub_no),
            'original_sum': st.get('original_sum'),
            'variations': st.get('variations'),
            'final_sum': st.get('final_sum'),
            'total_paid': st.get('total_paid'),
            'outstanding': st.get('outstanding'),
            'has_appendix_vo': bool(meta.get('has_vo')),
            'has_appendix_contra': bool(meta.get('has_contra')),
        })
    alignment = {
        'aligned': sum(1 for i in items if i['contract_align'] == 'aligned'),
        'missing': sum(1 for i in items if i['contract_align'] == 'missing'),
        'na': sum(1 for i in items if i['contract_align'] == 'na'),
        'excel_unlinked': len(project_orphan_refs(project, all_scs)) if project else 0,
        'orphans': project_orphan_refs(project, all_scs)[:8] if project else [],
    }
    return {
        'items': items,
        'contract_registry': get_sc_contract_registry_status(),
        'alignment': alignment,
    }


def sc_contract_registry_count():
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM sc_contract_registry").fetchone()[0]
    conn.close()
    return n


def engineering_category_count():
    conn = get_conn()
    n = conn.execute("SELECT COUNT(*) FROM engineering_categories").fetchone()[0]
    conn.close()
    return n


def sync_engineering_categories(filepath=None):
    """從 R1 Excel 同步 engineering_categories"""
    from engineering_category_ref import find_ref_file, parse_category_workbook

    path = filepath or find_ref_file()
    records = parse_category_workbook(path)
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_conn()
    new_n = upd_n = 0
    for rec in records:
        existing = conn.execute(
            "SELECT l2_code FROM engineering_categories WHERE l2_code=?",
            (rec['l2_code'],),
        ).fetchone()
        conn.execute("""
            INSERT INTO engineering_categories (
                l2_code, l1_code, l1_name_zh, l1_name_en,
                l2_name_zh, l2_name_en, scope, sort_order, source_file, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(l2_code) DO UPDATE SET
                l1_code=excluded.l1_code,
                l1_name_zh=excluded.l1_name_zh,
                l1_name_en=excluded.l1_name_en,
                l2_name_zh=excluded.l2_name_zh,
                l2_name_en=excluded.l2_name_en,
                scope=excluded.scope,
                sort_order=excluded.sort_order,
                source_file=excluded.source_file,
                updated_at=excluded.updated_at
        """, (
            rec['l2_code'], rec['l1_code'], rec['l1_name_zh'], rec['l1_name_en'],
            rec['l2_name_zh'], rec['l2_name_en'], rec.get('scope'),
            rec.get('sort_order', 0), rec.get('source_file'), now,
        ))
        if existing:
            upd_n += 1
        else:
            new_n += 1
    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM engineering_categories").fetchone()[0]
    conn.close()
    return {
        'ok': True,
        'source_file': os.path.basename(path) if path else None,
        'rows_read': len(records),
        'rows_new': new_n,
        'rows_updated': upd_n,
        'total': total,
    }


def list_engineering_categories():
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM engineering_categories ORDER BY sort_order, l2_code
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_engineering_categories_tree():
    """一級 → 二級樹狀結構（前端下拉用）"""
    rows = list_engineering_categories()
    tree = []
    by_l1 = {}
    for r in rows:
        l1 = r['l1_code']
        if l1 not in by_l1:
            from engineering_category_ref import category_display_label
            node = {
                'l1_code': l1,
                'l1_name_zh': r.get('l1_name_zh'),
                'l1_name_en': r.get('l1_name_en'),
                'l1_label': category_display_label(r, 'l1'),
                'children': [],
            }
            by_l1[l1] = node
            tree.append(node)
        by_l1[l1]['children'].append({
            'l2_code': r['l2_code'],
            'l2_name_zh': r.get('l2_name_zh'),
            'l2_name_en': r.get('l2_name_en'),
            'l2_label': f"{r['l2_code']} {(r.get('l2_name_zh') or r.get('l2_name_en') or '').strip()}".strip(),
            'scope': r.get('scope'),
        })
    return tree


def master_trade_category_count():
    conn = get_conn()
    n = conn.execute(
        "SELECT COUNT(*) FROM master_trade_categories WHERE is_active=1"
    ).fetchone()[0]
    conn.close()
    return n


def list_master_trade_categories(active_only=True, field_type=None):
    conn = get_conn()
    clauses = []
    params = []
    if active_only:
        clauses.append('is_active=1')
    if field_type:
        clauses.append('field_type=?')
        params.append(field_type)
    q = "SELECT * FROM master_trade_categories"
    if clauses:
        q += " WHERE " + " AND ".join(clauses)
    q += " ORDER BY sort_order, use_count DESC, name_zh"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_master_trade_options_grouped():
    rows = list_master_trade_categories(active_only=True)
    scope = [r for r in rows if r.get('field_type') == 'scope']
    override = [r for r in rows if r.get('field_type') == 'override']
    by_group = {}
    for r in scope:
        g = (r.get('group_name') or '').strip() or '未分類'
        by_group.setdefault(g, []).append(r)
    scope_groups = []
    seen = set()
    for ov in override:
        g = ov['name_zh']
        if g in by_group:
            scope_groups.append({
                'group_name': g,
                'use_count': sum(x.get('use_count') or 0 for x in by_group[g]),
                'children': by_group[g],
            })
            seen.add(g)
    if '未分類' in by_group:
        scope_groups.append({
            'group_name': '未分類',
            'use_count': sum(x.get('use_count') or 0 for x in by_group['未分類']),
            'children': by_group['未分類'],
        })
        seen.add('未分類')
    for g, children in sorted(by_group.items(), key=lambda x: (-sum(c.get('use_count') or 0 for c in x[1]), x[0])):
        if g not in seen:
            scope_groups.append({
                'group_name': g,
                'use_count': sum(x.get('use_count') or 0 for x in children),
                'children': children,
            })
    return {
        'scope_options': scope,
        'override_options': override,
        'eng_category_options': override,
        'scope_groups': scope_groups,
        'rows': rows,
    }


def sync_master_trade_categories(filepath=None):
    """從 Ref Master List Excel 報價／標書 I、J 欄同步選項"""
    from master_trade_ref import parse_trade_options_from_ref

    records = parse_trade_options_from_ref()
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = get_conn()
    new_n = upd_n = 0
    scope_n = override_n = catalog_n = extra_n = 0
    source_file = None
    for rec in records:
        source_file = rec.get('source_file') or source_file
        existing = conn.execute(
            "SELECT id FROM master_trade_categories WHERE field_type=? AND name_zh=?",
            (rec['field_type'], rec['name_zh']),
        ).fetchone()
        conn.execute("""
            INSERT INTO master_trade_categories (
                field_type, name_zh, group_name, use_count, sort_order, is_active, source_file, updated_at
            ) VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT(field_type, name_zh) DO UPDATE SET
                group_name=excluded.group_name,
                use_count=excluded.use_count,
                sort_order=excluded.sort_order,
                is_active=1,
                source_file=excluded.source_file,
                updated_at=excluded.updated_at
        """, (
            rec['field_type'], rec['name_zh'], rec.get('group_name'),
            rec.get('use_count', 0), rec.get('sort_order', 0), rec.get('source_file'), now,
        ))
        if rec['field_type'] == 'scope':
            scope_n += 1
        else:
            override_n += 1
            from master_trade_ref import EXTRA_CATALOG_GROUP
            if rec.get('group_name') == EXTRA_CATALOG_GROUP:
                extra_n += 1
            else:
                catalog_n += 1
        if existing:
            upd_n += 1
        else:
            new_n += 1
    conn.commit()
    total = conn.execute(
        "SELECT COUNT(*) FROM master_trade_categories WHERE is_active=1"
    ).fetchone()[0]
    conn.close()
    return {
        'ok': True,
        'source_file': source_file,
        'rows_read': len(records),
        'rows_new': new_n,
        'rows_updated': upd_n,
        'scope_count': scope_n,
        'override_count': override_n,
        'catalog_count': catalog_n,
        'extra_count': extra_n,
        'total': total,
    }


def create_master_trade_category(data):
    field_type = (data.get('field_type') or '').strip()
    name_zh = (data.get('name_zh') or '').strip()
    if field_type not in ('scope', 'override'):
        raise ValueError('field_type 須為 scope 或 override')
    if not name_zh:
        raise ValueError('請填寫名稱')
    group_name = (data.get('group_name') or '').strip() or None
    if field_type == 'scope' and group_name == '':
        group_name = None
    sort_order = data.get('sort_order')
    if sort_order is None:
        conn = get_conn()
        sort_order = conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM master_trade_categories WHERE field_type=?",
            (field_type,),
        ).fetchone()[0]
        conn.close()
    conn = get_conn()
    try:
        cur = conn.execute("""
            INSERT INTO master_trade_categories (
                field_type, name_zh, group_name, use_count, sort_order, is_active
            ) VALUES (?, ?, ?, 0, ?, 1)
        """, (field_type, name_zh, group_name, int(sort_order)))
        conn.commit()
        row_id = cur.lastrowid
    except Exception as e:
        conn.close()
        if 'UNIQUE' in str(e):
            raise ValueError('此欄位類型下已有相同名稱') from e
        raise
    row = conn.execute(
        "SELECT * FROM master_trade_categories WHERE id=?", (row_id,)
    ).fetchone()
    conn.close()
    return dict(row)


def update_master_trade_category(row_id, data):
    conn = get_conn()
    existing = conn.execute(
        "SELECT * FROM master_trade_categories WHERE id=?", (row_id,)
    ).fetchone()
    if not existing:
        conn.close()
        return None
    field_type = (data.get('field_type') or existing['field_type'] or '').strip()
    name_zh = (data.get('name_zh') or existing['name_zh'] or '').strip()
    if field_type not in ('scope', 'override') or not name_zh:
        conn.close()
        raise ValueError('請填寫欄位類型與名稱')
    group_name = data.get('group_name')
    if group_name is not None:
        group_name = str(group_name).strip() or None
    else:
        group_name = existing['group_name']
    if field_type != 'scope':
        group_name = None
    sort_order = data.get('sort_order', existing['sort_order'])
    is_active = data.get('is_active', existing['is_active'])
    try:
        conn.execute("""
            UPDATE master_trade_categories SET
                field_type=?, name_zh=?, group_name=?, sort_order=?, is_active=?,
                updated_at=datetime('now', 'localtime')
            WHERE id=?
        """, (field_type, name_zh, group_name, int(sort_order), int(is_active), row_id))
        conn.commit()
    except Exception as e:
        conn.close()
        if 'UNIQUE' in str(e):
            raise ValueError('此欄位類型下已有相同名稱') from e
        raise
    row = conn.execute(
        "SELECT * FROM master_trade_categories WHERE id=?", (row_id,)
    ).fetchone()
    conn.close()
    return dict(row)


def deactivate_master_trade_category(row_id):
    conn = get_conn()
    existing = conn.execute(
        "SELECT id FROM master_trade_categories WHERE id=?", (row_id,)
    ).fetchone()
    if not existing:
        conn.close()
        return False
    conn.execute(
        "UPDATE master_trade_categories SET is_active=0, updated_at=datetime('now', 'localtime') WHERE id=?",
        (row_id,),
    )
    conn.commit()
    conn.close()
    return True


def suggest_project_category(project_id):
    row = get_project(project_id)
    if not row:
        return None
    from engineering_category_ref import suggest_category_l2
    l2 = suggest_category_l2(row)
    if not l2:
        return {'l2_code': None, 'l1_code': None}
    conn = get_conn()
    cat = conn.execute(
        "SELECT l1_code, l2_code, l2_name_zh, l2_name_en FROM engineering_categories WHERE l2_code=?",
        (l2,),
    ).fetchone()
    conn.close()
    if not cat:
        return {'l2_code': l2, 'l1_code': l2.split('.')[0] if '.' in l2 else None}
    return dict(cat)


def auto_classify_projects(only_empty=True, dry_run=False):
    """依項目名稱關鍵字自動填入 category_l1/l2_code"""
    from engineering_category_ref import suggest_category_l2

    conn = get_conn()
    rows = conn.execute("SELECT * FROM projects ORDER BY id").fetchall()
    results = []
    updated = skipped = 0
    for row in rows:
        p = dict(row)
        if only_empty and (p.get('category_l2_code') or '').strip():
            skipped += 1
            continue
        l2 = suggest_category_l2(p)
        if not l2:
            results.append({
                'project_id': p['id'],
                'project_code': p.get('project_code'),
                'action': 'unmatched',
            })
            continue
        cat = conn.execute(
            "SELECT l1_code FROM engineering_categories WHERE l2_code=?",
            (l2,),
        ).fetchone()
        l1 = cat['l1_code'] if cat else (l2.split('.')[0] if '.' in l2 else None)
        title = (p.get('project_name_zh') or p.get('project_name_en') or '')[:40]
        entry = {
            'project_id': p['id'],
            'project_code': p.get('project_code'),
            'title': title,
            'l1_code': l1,
            'l2_code': l2,
            'action': 'classified',
        }
        results.append(entry)
        if not dry_run:
            conn.execute("""
                UPDATE projects SET category_l1_code=?, category_l2_code=?
                WHERE id=?
            """, (l1, l2, p['id']))
            updated += 1
    if not dry_run:
        conn.commit()
    conn.close()
    return {
        'updated': updated,
        'skipped': skipped,
        'unmatched': sum(1 for r in results if r['action'] == 'unmatched'),
        'results': results,
        'dry_run': dry_run,
    }


def list_sc_contract_registry_rows():
    conn = get_conn()
    rows = conn.execute("""
        SELECT id, sub_contract_no, legacy_contract_no, company, works,
               project_code, project_core, person_in_charge, person_code,
               amount, countersign, partner, tender_minutes,
               final_account, final_account_statement, iso_flag, remark,
               sheet, source_file, updated_at
        FROM sc_contract_registry
        ORDER BY sub_contract_no
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_sc_contract_registry_status():
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM sc_contract_registry").fetchone()[0]
    last = conn.execute("""
        SELECT source_file, rows_read, rows_new, rows_updated, imported_at
        FROM sc_contract_imports ORDER BY id DESC LIMIT 1
    """).fetchone()
    conn.close()
    last_import = dict(last) if last else None
    return {
        'row_count': count,
        'last_import': last_import,
    }


def _scr_sync_values(r, source_file=None):
    return (
        r.get('legacy_contract_no'),
        r.get('company'),
        r.get('works'),
        r.get('project_code'),
        r.get('project_core'),
        r.get('person_in_charge'),
        r.get('person_code'),
        r.get('amount') or 0,
        r.get('countersign'),
        r.get('partner'),
        r.get('tender_minutes'),
        r.get('final_account'),
        r.get('final_account_statement'),
        r.get('iso_flag'),
        r.get('remark'),
        r.get('sheet'),
        source_file or r.get('source_file'),
    )


def sync_sc_contract_registry(rows, source_file=None):
    conn = get_conn()
    new_n = 0
    upd_n = 0
    for r in rows:
        ex = conn.execute(
            "SELECT id FROM sc_contract_registry WHERE sub_contract_no=?",
            (r['sub_contract_no'],),
        ).fetchone()
        fields = _scr_sync_values(r, source_file)
        if ex:
            conn.execute("""
                UPDATE sc_contract_registry SET
                    legacy_contract_no=?, company=?, works=?, project_code=?, project_core=?,
                    person_in_charge=?, person_code=?, amount=?,
                    countersign=?, partner=?, tender_minutes=?,
                    final_account=?, final_account_statement=?, iso_flag=?, remark=?,
                    sheet=?, source_file=?,
                    updated_at=datetime('now', 'localtime')
                WHERE sub_contract_no=?
            """, (*fields, r['sub_contract_no']))
            upd_n += 1
        else:
            conn.execute("""
                INSERT INTO sc_contract_registry (
                    sub_contract_no, legacy_contract_no, company, works, project_code, project_core,
                    person_in_charge, person_code, amount,
                    countersign, partner, tender_minutes,
                    final_account, final_account_statement, iso_flag, remark,
                    sheet, source_file
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (r['sub_contract_no'], *fields))
            new_n += 1
    conn.execute("""
        INSERT INTO sc_contract_imports (source_file, rows_read, rows_new, rows_updated)
        VALUES (?, ?, ?, ?)
    """, (source_file, len(rows), new_n, upd_n))
    conn.commit()
    conn.close()
    return {
        'rows_read': len(rows),
        'rows_new': new_n,
        'rows_updated': upd_n,
        'source_file': source_file,
    }


def search_sc_contract_registry(
    q=None, project_core=None, sheet=None, person=None, company=None, limit=2000,
):
    conn = get_conn()
    sql = """
        SELECT id, sub_contract_no, legacy_contract_no, company, works,
               project_code, project_core, person_in_charge, person_code,
               amount, countersign, partner, tender_minutes,
               final_account, final_account_statement, iso_flag, remark,
               sheet, source_file, updated_at
        FROM sc_contract_registry WHERE 1=1
    """
    params = []
    if project_core:
        sql += " AND project_core=?"
        params.append(project_core.strip().upper())
    if sheet:
        sql += " AND sheet=?"
        params.append(str(sheet).strip())
    if person:
        sql += " AND (person_in_charge=? OR person_code=?)"
        p = person.strip()
        params.extend([p, p.lower()])
    if company:
        sql += " AND company=?"
        params.append(company.strip())
    if q:
        like = f'%{q.strip()}%'
        sql += """ AND (
            sub_contract_no LIKE ? OR company LIKE ? OR works LIKE ?
            OR project_code LIKE ? OR project_core LIKE ?
            OR person_in_charge LIKE ? OR person_code LIKE ?
            OR partner LIKE ? OR remark LIKE ?
        )"""
        params.extend([like] * 9)
    sql += " ORDER BY sheet DESC, sub_contract_no LIMIT ?"
    params.append(int(limit))
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_sc_contract_registry_filters():
    conn = get_conn()
    years = [
        r[0] for r in conn.execute("""
            SELECT DISTINCT sheet FROM sc_contract_registry
            WHERE sheet IS NOT NULL AND sheet != ''
            ORDER BY sheet DESC
        """).fetchall()
    ]
    persons = [
        r[0] for r in conn.execute("""
            SELECT DISTINCT person_in_charge FROM sc_contract_registry
            WHERE person_in_charge IS NOT NULL AND TRIM(person_in_charge) != ''
            ORDER BY person_in_charge
        """).fetchall()
    ]
    companies = [
        r[0] for r in conn.execute("""
            SELECT DISTINCT company FROM sc_contract_registry
            WHERE company IS NOT NULL AND TRIM(company) != ''
            ORDER BY company
        """).fetchall()
    ]
    conn.close()
    return {'years': years, 'persons': persons, 'companies': companies}


def get_sc_contract_registry_row(sub_contract_no):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM sc_contract_registry WHERE sub_contract_no=?",
        (sub_contract_no,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def save_sc_contract_registry_row(data):
    from sc_contract_ref import (
        _build_registry_row,
        _project_core,
        extract_person_code_from_ms_c,
        invalidate_cache,
        normalize_ms_c_input,
        validate_ms_c_input,
    )

    ok, msg = validate_ms_c_input(data.get('sub_contract_no'))
    if not ok:
        raise ValueError(msg)
    sub_no = msg or normalize_ms_c_input(data.get('sub_contract_no'))
    if not sub_no:
        raise ValueError('請填寫 MS/C 分判合約編號')

    project_code = (data.get('project_code') or '').strip()
    from sc_contract_ref import _is_legacy_contract_no
    if not project_code and not _is_legacy_contract_no(sub_no):
        raise ValueError('請填寫項目編號')

    conn = get_conn()
    ex = conn.execute(
        "SELECT id, legacy_contract_no FROM sc_contract_registry WHERE sub_contract_no=?",
        (sub_no,),
    ).fetchone()
    legacy_contract_no = data.get('legacy_contract_no')
    if ex and 'legacy_contract_no' not in data:
        legacy_contract_no = ex['legacy_contract_no']

    row = _build_registry_row(
        sub_no,
        data.get('company'),
        data.get('works'),
        project_code,
        legacy_contract_no=legacy_contract_no,
        person_in_charge=data.get('person_in_charge'),
        amount=data.get('amount'),
        countersign=data.get('countersign'),
        partner=data.get('partner'),
        tender_minutes=data.get('tender_minutes'),
        final_account=data.get('final_account'),
        final_account_statement=data.get('final_account_statement'),
        iso_flag=data.get('iso_flag'),
        remark=data.get('remark'),
        sheet=data.get('sheet'),
        source_file=(data.get('source_file') or '').strip() or 'UI',
    )
    if not row:
        raise ValueError('資料不完整')
    if data.get('person_code'):
        row['person_code'] = str(data['person_code']).strip().lower()
    elif not row.get('person_code'):
        row['person_code'] = extract_person_code_from_ms_c(sub_no)
    row['project_core'] = _project_core(project_code)

    fields = _scr_sync_values(row, row.get('source_file'))
    if ex:
        conn.execute("""
            UPDATE sc_contract_registry SET
                legacy_contract_no=?, company=?, works=?, project_code=?, project_core=?,
                person_in_charge=?, person_code=?, amount=?,
                countersign=?, partner=?, tender_minutes=?,
                final_account=?, final_account_statement=?, iso_flag=?, remark=?,
                sheet=?, source_file=?,
                updated_at=datetime('now', 'localtime')
            WHERE sub_contract_no=?
        """, (*fields, sub_no))
    else:
        conn.execute("""
            INSERT INTO sc_contract_registry (
                sub_contract_no, legacy_contract_no, company, works, project_code, project_core,
                person_in_charge, person_code, amount,
                countersign, partner, tender_minutes,
                final_account, final_account_statement, iso_flag, remark,
                sheet, source_file
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (sub_no, *fields))
    conn.commit()
    conn.close()
    invalidate_cache()
    return get_sc_contract_registry_row(sub_no)


def delete_sc_contract_registry_row(sub_contract_no):
    from sc_contract_ref import invalidate_cache

    conn = get_conn()
    cur = conn.execute(
        "DELETE FROM sc_contract_registry WHERE sub_contract_no=?",
        (sub_contract_no,),
    )
    conn.commit()
    conn.close()
    invalidate_cache()
    return cur.rowcount > 0


def update_main_con_fac(project_id, data):
    from main_fac import MAIN_FAC_WRITABLE

    project = get_project(project_id)
    if not project:
        return False
    payload = {}
    for key in MAIN_FAC_WRITABLE:
        if key in data:
            val = data[key]
            if val == '' or val is None:
                payload[key] = None
            elif key.endswith('_override'):
                payload[key] = float(val) if val != '' else None
            elif key in (
                'fac_remeasurement_b', 'fac_provisional_qty_e', 'fac_provisional_sums_f',
                'fac_fluctuations_g', 'fac_lad_rate', 'fac_lad_max',
            ):
                payload[key] = float(val or 0)
            else:
                payload[key] = val
    if not payload:
        return True
    set_sql = ', '.join(f'{k}=:{k}' for k in payload)
    conn = get_conn()
    conn.execute(f"UPDATE projects SET {set_sql} WHERE id=:id", {**payload, 'id': project_id})
    conn.commit()
    conn.close()
    return True


def update_main_fac_attachment(project_id, att_type, file_path, original_name):
    mapping = {
        'statement': ('fac_statement_path', 'fac_statement_name'),
        'pc_cert': ('fac_pc_cert_path', 'fac_pc_cert_name'),
        'mg_cert': ('fac_mg_cert_path', 'fac_mg_cert_name'),
    }
    if att_type not in mapping:
        return False
    path_col, name_col = mapping[att_type]
    conn = get_conn()
    row = conn.execute("SELECT id FROM projects WHERE id=?", (project_id,)).fetchone()
    if not row:
        conn.close()
        return False
    conn.execute(
        f"UPDATE projects SET {path_col}=?, {name_col}=? WHERE id=?",
        (file_path, original_name, project_id),
    )
    conn.commit()
    conn.close()
    return True


def get_project_documents(project_id):
    conn = get_conn()
    rows = conn.execute(
        """SELECT id, project_id, doc_category, file_path, original_filename,
                  notes, created_at
           FROM project_documents WHERE project_id=?
           ORDER BY created_at DESC""",
        (project_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_project_document(project_id, doc_category, file_path, original_filename=None, notes=None):
    conn = get_conn()
    cur = conn.execute("""
        INSERT INTO project_documents (project_id, doc_category, file_path, original_filename, notes)
        VALUES (?, ?, ?, ?, ?)
    """, (project_id, doc_category, file_path, original_filename, notes))
    conn.commit()
    doc_id = cur.lastrowid
    conn.close()
    return doc_id


def delete_project_document(doc_id):
    conn = get_conn()
    conn.execute("DELETE FROM project_documents WHERE id=?", (doc_id,))
    conn.commit()
    conn.close()


# ─── ISO Documents ─────────────────────────────────────────────────────

def _iso_sc_rows_from_conn(conn, project_id):
    """分判 ISO 表格列（輕量查詢，不含付款匯總）"""
    rows = conn.execute("""
        SELECT id, sc_no, parent_sc_no, company_name_en, company_name_zh,
               contract_sum, contract_amount, is_excluded
        FROM subcontractors WHERE project_id=?
        ORDER BY COALESCE(parent_sc_no, sc_no), sc_no
    """, (project_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if d.get('is_excluded'):
            continue
        sc_no = (d.get('sc_no') or '').strip().upper()
        if sc_no.startswith('M-') or re.match(r'^M\d', sc_no):
            continue
        if sc_no.startswith('O-') or re.match(r'^O\d', sc_no):
            continue
        parent = (d.get('parent_sc_no') or '').strip().upper()
        if parent and parent != sc_no:
            continue
        out.append(d)
    return out


def _iso_sc_rows(project_id):
    conn = get_conn()
    try:
        return _iso_sc_rows_from_conn(conn, project_id)
    finally:
        conn.close()


def get_iso_documents_board(project_id):
    conn = get_conn()
    project = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    if not project:
        conn.close()
        return None
    project = dict(project)

    file_rows = conn.execute("""
        SELECT id, scope, subcontractor_id, doc_slot, file_path, original_filename,
               storage_type, external_url, link_label, updated_at
        FROM iso_document_files WHERE project_id=?
    """, (project_id,)).fetchall()

    version_counts = {}
    for r in conn.execute("""
        SELECT scope, subcontractor_id, doc_slot, COUNT(*) AS n
        FROM iso_document_versions WHERE project_id=?
        GROUP BY scope, IFNULL(subcontractor_id, 0), doc_slot
    """, (project_id,)).fetchall():
        d = dict(r)
        key = (d['scope'], d.get('subcontractor_id') or 0, d['doc_slot'])
        version_counts[key] = d['n']

    sc_list = _iso_sc_rows_from_conn(conn, project_id)
    conn.close()

    def _enrich(d):
        key = (d['scope'], d.get('subcontractor_id') or 0, d['doc_slot'])
        d['version_count'] = version_counts.get(key, 0)
        if not d.get('storage_type'):
            d['storage_type'] = 'link' if d.get('external_url') else 'file'
        return d

    main_files = {}
    sc_files = {}
    for r in file_rows:
        d = _enrich(dict(r))
        slot = d['doc_slot']
        if d['scope'] == 'main':
            main_files[slot] = d
        elif d['scope'] == 'subcontractor' and d.get('subcontractor_id'):
            sc_files.setdefault(d['subcontractor_id'], {})[slot] = d

    sc_rows = []
    for sc in sc_list:
        amt = float(sc.get('contract_sum') or sc.get('contract_amount') or 0)
        sc_rows.append({
            'id': sc['id'],
            'sc_no': sc.get('sc_no'),
            'company_name_zh': sc.get('company_name_zh') or sc.get('company_name_en') or sc.get('sc_no'),
            'contract_amount': amt,
            'files': sc_files.get(sc['id'], {}),
        })

    return {
        'project': {
            'id': project['id'],
            'project_code': project.get('project_code'),
            'project_name_zh': project.get('project_name_zh') or project.get('project_name_en'),
            'contract_amount': float(project.get('contract_amount') or 0),
            'supplemental_contract_amount': float(project.get('supplemental_contract_amount') or 0),
            'doc_library_url': (project.get('doc_library_url') or '').strip() or None,
        },
        'doc_library': {
            'project_url': (project.get('doc_library_url') or '').strip() or None,
            'global_url': (get_setting('doc_library_url', '') or '').strip() or None,
        },
        'main_files': main_files,
        'subcontractors': sc_rows,
    }


def get_iso_slot_file_path(project_id, scope, doc_slot, subcontractor_id=None):
    conn = get_conn()
    row = conn.execute("""
        SELECT file_path FROM iso_document_files
        WHERE project_id=? AND scope=? AND IFNULL(subcontractor_id, 0)=IFNULL(?, 0) AND doc_slot=?
    """, (project_id, scope, subcontractor_id, doc_slot)).fetchone()
    conn.close()
    return row['file_path'] if row else None


def upsert_iso_document(
    project_id, scope, doc_slot, file_path, original_filename=None, subcontractor_id=None,
    external_url=None, storage_type='file', link_label=None,
):
    if scope == 'main':
        if doc_slot not in ISO_MAIN_SLOTS:
            raise ValueError('無效的 doc_slot')
        subcontractor_id = None
    elif scope == 'subcontractor':
        if doc_slot not in ISO_SC_SLOTS:
            raise ValueError('無效的 doc_slot')
        if not subcontractor_id:
            raise ValueError('缺少 subcontractor_id')
        sc = get_subcontractor(subcontractor_id)
        if not sc or sc.get('project_id') != project_id:
            raise ValueError('分判不存在')
    else:
        raise ValueError('無效的 scope')

    storage_type = (storage_type or 'file').strip().lower()
    if storage_type == 'link':
        external_url = (external_url or '').strip()
        if not external_url:
            raise ValueError('缺少連結 URL')
        if not external_url.lower().startswith(('http://', 'https://')):
            raise ValueError('連結須以 http:// 或 https:// 開頭')
        file_path = ''
        link_label = (link_label or original_filename or '').strip() or None
        original_filename = link_label
    else:
        storage_type = 'file'
        file_path = (file_path or '').strip()
        if not file_path:
            raise ValueError('缺少 file_path')
        external_url = None
        link_label = None

    conn = get_conn()
    _archive_iso_slot(conn, project_id, scope, doc_slot, subcontractor_id)
    conn.execute("""
        INSERT INTO iso_document_files
            (project_id, scope, subcontractor_id, doc_slot, file_path, original_filename,
             storage_type, external_url, link_label, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
        ON CONFLICT(project_id, scope, IFNULL(subcontractor_id, 0), doc_slot)
        DO UPDATE SET
            file_path=excluded.file_path,
            original_filename=excluded.original_filename,
            storage_type=excluded.storage_type,
            external_url=excluded.external_url,
            link_label=excluded.link_label,
            updated_at=datetime('now', 'localtime')
    """, (
        project_id, scope, subcontractor_id, doc_slot, file_path, original_filename,
        storage_type, external_url, link_label,
    ))
    row = conn.execute("""
        SELECT id, scope, subcontractor_id, doc_slot, file_path, original_filename,
               storage_type, external_url, link_label, updated_at
        FROM iso_document_files
        WHERE project_id=? AND scope=? AND IFNULL(subcontractor_id, 0)=IFNULL(?, 0) AND doc_slot=?
    """, (project_id, scope, subcontractor_id, doc_slot)).fetchone()
    ver = conn.execute("""
        SELECT COUNT(*) AS n FROM iso_document_versions
        WHERE project_id=? AND scope=? AND IFNULL(subcontractor_id, 0)=IFNULL(?, 0) AND doc_slot=?
    """, (project_id, scope, subcontractor_id, doc_slot)).fetchone()
    conn.commit()
    conn.close()
    out = dict(row) if row else None
    if out:
        out['version_count'] = ver['n'] if ver else 0
    return out


def list_iso_document_versions(project_id, scope, doc_slot, subcontractor_id=None):
    conn = get_conn()
    rows = conn.execute("""
        SELECT id, file_path, original_filename, external_url, storage_type, archived_at
        FROM iso_document_versions
        WHERE project_id=? AND scope=? AND IFNULL(subcontractor_id, 0)=IFNULL(?, 0) AND doc_slot=?
        ORDER BY archived_at DESC
    """, (project_id, scope, subcontractor_id, doc_slot)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_iso_document(doc_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM iso_document_files WHERE id=?", (doc_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_iso_document(doc_id):
    conn = get_conn()
    row = conn.execute("""
        SELECT project_id, scope, subcontractor_id, doc_slot, file_path
        FROM iso_document_files WHERE id=?
    """, (doc_id,)).fetchone()
    if row:
        d = dict(row)
        _archive_iso_slot(conn, d['project_id'], d['scope'], d['doc_slot'], d.get('subcontractor_id'))
    conn.execute("DELETE FROM iso_document_files WHERE id=?", (doc_id,))
    conn.commit()
    conn.close()
    return row['file_path'] if row else None


def update_iso_supplemental_amount(project_id, amount):
    conn = get_conn()
    conn.execute(
        "UPDATE projects SET supplemental_contract_amount=? WHERE id=?",
        (float(amount or 0), project_id),
    )
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
            AND (pr.revoked_at IS NULL OR pr.revoked_at = '')
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


def get_subcontractor_by_sc_no(project_id, sc_no):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM subcontractors WHERE project_id=? AND sc_no=?",
        (project_id, sc_no),
    ).fetchone()
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
    data.setdefault('sc_entry_type', 'quotation')
    data.setdefault('retention_sum', None)
    data.setdefault('sub_contract_no', None)
    if data.get('sc_entry_type') == 'contract':
        data['quotation_date'] = None
        data['oa_status'] = None
        data['oa_no'] = None
    else:
        data['retention_sum'] = None

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
        if 'sub_contract_no' not in data and old.get('sub_contract_no'):
            data['sub_contract_no'] = old['sub_contract_no']
        conn.execute("""
            UPDATE subcontractors SET
                quotation_no=:quotation_no, company_name_en=:company_name_en,
                company_name_zh=:company_name_zh, description=:description,
                contract_sum=:contract_sum, vo_amount=:vo_amount,
                contract_amount=:contract_amount, parent_sc_no=:parent_sc_no,
                payment_note=:payment_note,
                oa_status=:oa_status, oa_ref=:oa_ref, oa_no=:oa_no,
                quotation_saved=:quotation_saved, quotation_date=:quotation_date,
                oa_date=:oa_date, is_excluded=:is_excluded,
                sc_entry_type=:sc_entry_type, retention_sum=:retention_sum,
                sub_contract_no=:sub_contract_no
            WHERE project_id=:project_id AND sc_no=:sc_no
        """, data)
        sc_id = existing['id']
    else:
        cur = conn.execute("""
            INSERT INTO subcontractors (project_id, sc_no, quotation_no, company_name_en,
                company_name_zh, description, contract_sum, vo_amount, contract_amount,
                parent_sc_no, payment_note,
                oa_status, oa_ref, oa_no, quotation_saved, quotation_date, oa_date, is_excluded,
                sc_entry_type, retention_sum, sub_contract_no)
            VALUES (:project_id, :sc_no, :quotation_no, :company_name_en,
                :company_name_zh, :description, :contract_sum, :vo_amount, :contract_amount,
                :parent_sc_no, :payment_note,
                :oa_status, :oa_ref, :oa_no, :quotation_saved, :quotation_date, :oa_date, :is_excluded,
                :sc_entry_type, :retention_sum, :sub_contract_no)
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
    return _enrich_payment_rows(rows)


def _sc_contract_total(conn, project_id, sc_no, contract_amount_hint=None):
    """判項合約總額（原判 + VO）；優先用記錄上的 contract_amount"""
    if contract_amount_hint is not None and float(contract_amount_hint or 0) > 0:
        return float(contract_amount_hint)
    row = conn.execute("""
        SELECT contract_amount, contract_sum, vo_amount FROM subcontractors
        WHERE project_id=? AND sc_no=?
    """, (project_id, sc_no)).fetchone()
    if not row:
        return 0.0
    base = float(row['contract_sum'] or row['contract_amount'] or 0)
    vo = float(row['vo_amount'] or 0)
    return base + vo


def _sc_active_paid_total(conn, project_id, sc_no):
    row = conn.execute("""
        SELECT COALESCE(SUM(paid_amount), 0) FROM payment_records
        WHERE project_id=? AND sc_no=?
          AND (revoked_at IS NULL OR revoked_at = '')
    """, (project_id, sc_no)).fetchone()
    return float(row[0] or 0)


def _sc_remainder_balance(conn, project_id, sc_no, contract_amount_hint=None):
    """撤回後判項餘額（不含已撤回糧款）"""
    total = _sc_contract_total(conn, project_id, sc_no, contract_amount_hint)
    paid = _sc_active_paid_total(conn, project_id, sc_no)
    return max(0.0, total - paid)


def _interim_remainder_on_submit(conn, project_id, sc_no, this_pay, contract_amount_hint=None, exclude_payment_id=None):
    """提交／還原計算書後該筆應顯示的餘額"""
    total = _sc_contract_total(conn, project_id, sc_no, contract_amount_hint)
    sql = """
        SELECT COALESCE(SUM(paid_amount), 0) FROM payment_records
        WHERE project_id=? AND sc_no=?
          AND (revoked_at IS NULL OR revoked_at = '')
    """
    params = [project_id, sc_no]
    if exclude_payment_id:
        sql += " AND id<>?"
        params.append(exclude_payment_id)
    prev = float(conn.execute(sql, params).fetchone()[0] or 0)
    return max(0.0, total - prev - float(this_pay or 0))


def _load_cert_json(raw):
    if not raw:
        return {}
    try:
        return json.loads(raw) if isinstance(raw, str) else dict(raw)
    except (TypeError, json.JSONDecodeError):
        return {}


def _pre_submit_from_cert_json(d):
    stored = _load_cert_json(d.get('interim_cert_json'))
    if not stored:
        return None, None
    prev = stored.get('previous_paid')
    if prev is None:
        prev = stored.get('pre_submit_sc_paid')
    pre_rem = stored.get('pre_submit_sc_remainder')
    return prev, pre_rem


def _cert_net_payment(stored):
    """計算書 json 內今期實付（列級）"""
    for key in ('net_payment', 'paid_amount'):
        val = stored.get(key)
        if val is not None and float(val or 0) > 0:
            return float(val)
    return None


def _infer_row_snapshot_from_cert(stored, row_dict):
    """從 cert json 推斷普通付款原列（修復缺快照的誤提交／重新提交污染）"""
    if not stored or stored.get('original_row_snapshot'):
        return None
    if stored.get('pre_submit_payment_type') == 'interim_cert':
        return None
    contract = float(
        stored.get('pre_submit_row_contract')
        or row_dict.get('contract_amount')
        or stored.get('contract_amount') or 0
    )
    if contract <= 0:
        return None
    cert_net = _cert_net_payment(stored)
    sc_paid = stored.get('pre_submit_sc_paid')
    sc_paid_f = float(sc_paid) if sc_paid is not None else None
    row_paid_db = float(row_dict.get('paid_amount') or 0)

    # SC 快照被污染：cert 內今期實付 < json 內 pre_submit_sc_paid
    if cert_net is not None and sc_paid_f is not None and cert_net < sc_paid_f - 0.02:
        row_paid = cert_net
        row_rem = max(0.0, round(contract - row_paid, 2))
        return {
            'payment_type': 'normal',
            'paid': row_paid,
            'remainder': row_rem,
            'contract': contract,
        }

    # 首次轉換：sc_paid 仍為原列已付，cert 今期大於原列
    if (
        cert_net is not None and sc_paid_f is not None
        and cert_net > sc_paid_f + 0.02 and sc_paid_f > 0.01
    ):
        row_paid = sc_paid_f
        row_rem = max(0.0, round(contract - row_paid, 2))
        return {
            'payment_type': 'normal',
            'paid': row_paid,
            'remainder': row_rem,
            'contract': contract,
        }

    # 軟撤回列：DB 已付與 SC 快照不符
    if (
        row_paid_db > 0.01 and sc_paid_f is not None
        and sc_paid_f > 0.01 and abs(row_paid_db - sc_paid_f) > 0.02
    ):
        if cert_net is not None and abs(cert_net - row_paid_db) < 0.02:
            row_paid = row_paid_db
        elif cert_net is not None and cert_net < sc_paid_f - 0.02:
            row_paid = cert_net
        else:
            row_paid = row_paid_db
        row_rem = max(0.0, round(contract - row_paid, 2))
        return {
            'payment_type': 'normal',
            'paid': row_paid,
            'remainder': row_rem,
            'contract': contract,
        }
    return None


def _persist_row_snapshot(conn, payment_id, stored, snap):
    stored['original_row_snapshot'] = snap
    stored['pre_submit_payment_type'] = snap.get('payment_type') or 'normal'
    stored['pre_submit_row_paid'] = snap['paid']
    if snap.get('remainder') is not None:
        stored['pre_submit_row_remainder'] = snap['remainder']
    if snap.get('contract') is not None:
        stored['pre_submit_row_contract'] = snap['contract']
    conn.execute(
        "UPDATE payment_records SET interim_cert_json=? WHERE id=?",
        (json.dumps(stored, ensure_ascii=False), payment_id),
    )
    return stored


def _inject_row_pre_submit(stored, existing_row):
    """普通付款改提交計算書時，記錄原列數值供還原（僅首次寫入）"""
    if not isinstance(stored, dict):
        stored = {}
    if stored.get('original_row_snapshot'):
        return stored
    if stored.get('pre_submit_row_paid') is not None:
        snap = {
            'payment_type': stored.get('pre_submit_payment_type') or 'normal',
            'paid': float(stored['pre_submit_row_paid']),
            'remainder': float(stored.get('pre_submit_row_remainder') or 0),
            'contract': float(stored.get('pre_submit_row_contract') or 0),
        }
        stored['original_row_snapshot'] = snap
        return stored
    if stored.get('pre_submit_payment_type') == 'interim_cert':
        return stored
    ex = dict(existing_row)
    prev_type = ex.get('payment_type') or 'normal'
    if prev_type == 'interim_cert':
        return stored
    snap = {
        'payment_type': prev_type,
        'paid': float(ex.get('paid_amount') or 0),
        'remainder': float(ex.get('remainder_amount') or 0),
        'contract': float(ex.get('contract_amount') or 0),
    }
    stored['original_row_snapshot'] = snap
    stored['pre_submit_payment_type'] = snap['payment_type']
    stored['pre_submit_row_paid'] = snap['paid']
    stored['pre_submit_row_remainder'] = snap['remainder']
    stored['pre_submit_row_contract'] = snap['contract']
    return stored


def _preserve_row_pre_submit(existing_raw, new_stored):
    """重新提交計算書時保留首次提交前快照（舊值優先，不可覆蓋）"""
    if not isinstance(new_stored, dict):
        new_stored = {}
    old = _load_cert_json(existing_raw)
    for key in (
        'original_row_snapshot',
        'pre_submit_payment_type', 'pre_submit_row_paid',
        'pre_submit_row_remainder', 'pre_submit_row_contract',
        'pre_submit_sc_paid', 'pre_submit_sc_remainder', 'previous_paid',
    ):
        if key in old and old[key] is not None:
            new_stored[key] = old[key]
    return new_stored


def _row_pre_submit_from_cert(stored, conn=None, row=None):
    """還原時取提交前該列狀態（含舊記錄推斷）"""
    if not stored:
        return None
    orig = stored.get('original_row_snapshot')
    if isinstance(orig, dict) and orig.get('payment_type') and orig.get('paid') is not None:
        return {
            'payment_type': orig.get('payment_type'),
            'paid': float(orig['paid']),
            'remainder': float(orig['remainder']) if orig.get('remainder') is not None else None,
            'contract': float(orig['contract']) if orig.get('contract') is not None else None,
        }
    ptype = stored.get('pre_submit_payment_type')
    if ptype == 'interim_cert':
        ptype = None
    paid = stored.get('pre_submit_row_paid')
    rem = stored.get('pre_submit_row_remainder')
    contract = stored.get('pre_submit_row_contract')
    if ptype is not None and paid is not None:
        return {
            'payment_type': ptype,
            'paid': float(paid),
            'remainder': float(rem) if rem is not None else None,
            'contract': float(contract) if contract is not None else None,
        }
    inferred = _infer_row_snapshot_from_cert(stored, row)
    if inferred and inferred.get('payment_type') == 'normal':
        return inferred
    if conn is None or row is None:
        return None
    sc_paid = stored.get('pre_submit_sc_paid')
    if sc_paid is None:
        return None
    pid, sc_no = row['project_id'], row['sc_no']
    others = conn.execute("""
        SELECT COALESCE(SUM(paid_amount), 0) FROM payment_records
        WHERE project_id=? AND sc_no=? AND id<>?
          AND (revoked_at IS NULL OR revoked_at = '')
    """, (pid, sc_no, row['id'])).fetchone()[0]
    if float(others or 0) > 0.01:
        return None
    sc_rem = stored.get('pre_submit_sc_remainder')
    cur_pay = float(row.get('paid_amount') or 0)
    contract = float(row.get('contract_amount') or 0)
    sc_paid_f = float(sc_paid)
    if contract > 0 and sc_rem is not None:
        sc_rem_f = float(sc_rem)
        inferred = max(0.0, round(contract - sc_rem_f, 2))
        if abs(sc_paid_f - cur_pay) < 0.02 and inferred > 0.01 and abs(inferred - cur_pay) > 0.02:
            sc_paid_f = inferred
    return {
        'payment_type': 'normal',
        'paid': sc_paid_f,
        'remainder': float(sc_rem) if sc_rem is not None else None,
        'contract': contract or None,
    }


def _backfill_original_row_snapshot(conn, payment_id, row_dict, stored):
    """舊記錄補建原列快照（待重新提交列一次性修復）"""
    if stored.get('original_row_snapshot'):
        return stored
    if stored.get('pre_submit_row_paid') is not None:
        snap = {
            'payment_type': stored.get('pre_submit_payment_type') or 'normal',
            'paid': float(stored['pre_submit_row_paid']),
            'remainder': float(stored.get('pre_submit_row_remainder') or 0),
            'contract': float(stored.get('pre_submit_row_contract') or row_dict.get('contract_amount') or 0),
        }
        stored['original_row_snapshot'] = snap
        conn.execute(
            "UPDATE payment_records SET interim_cert_json=? WHERE id=?",
            (json.dumps(stored, ensure_ascii=False), payment_id),
        )
        return stored
    inferred = _infer_row_snapshot_from_cert(stored, row_dict)
    if inferred:
        return _persist_row_snapshot(conn, payment_id, stored, inferred)
    contract = float(stored.get('pre_submit_row_contract') or row_dict.get('contract_amount') or 0)
    sc_rem = stored.get('pre_submit_sc_remainder')
    cur_pay = float(row_dict.get('paid_amount') or 0)
    sc_paid = stored.get('pre_submit_sc_paid')
    if contract > 0 and sc_rem is not None:
        sc_rem_f = float(sc_rem)
        inferred_paid = max(0.0, round(contract - sc_rem_f, 2))
        paid_corrupted = sc_paid is not None and abs(float(sc_paid) - cur_pay) < 0.02
        if inferred_paid > 0 and (paid_corrupted or sc_paid is None):
            snap = {
                'payment_type': 'normal',
                'paid': inferred_paid,
                'remainder': sc_rem_f,
                'contract': contract,
            }
            stored['original_row_snapshot'] = snap
            stored['pre_submit_payment_type'] = 'normal'
            stored['pre_submit_row_paid'] = inferred_paid
            stored['pre_submit_row_remainder'] = sc_rem_f
            stored['pre_submit_row_contract'] = contract
            if paid_corrupted:
                stored['pre_submit_sc_paid'] = inferred_paid
                stored['previous_paid'] = inferred_paid
            conn.execute(
                "UPDATE payment_records SET interim_cert_json=? WHERE id=?",
                (json.dumps(stored, ensure_ascii=False), payment_id),
            )
            return stored
    snap = _row_pre_submit_from_cert(stored, conn, row_dict)
    if snap and snap.get('payment_type') == 'normal':
        return _persist_row_snapshot(conn, payment_id, stored, snap)
    return stored


def _compute_pre_submit_snapshot(conn, row):
    """提交前判項累計／餘額（撤回時還原顯示；舊記錄可反推）"""
    d = dict(row)
    pre_paid, pre_rem = _pre_submit_from_cert_json(d)
    if pre_paid is not None and pre_rem is not None:
        return float(pre_paid), float(pre_rem)
    pid, sc_no = d['project_id'], d['sc_no']
    hint = float(d.get('contract_amount') or 0) or None
    total = _sc_contract_total(conn, pid, sc_no, hint)
    active = _sc_active_paid_total(conn, pid, sc_no)
    this_pay = float(d.get('paid_amount') or 0)
    pre_paid = max(0.0, active - this_pay)
    pre_rem = max(0.0, total - pre_paid)
    return pre_paid, pre_rem


def _ensure_pre_submit_in_cert_json(conn, payment_id, pre_paid, pre_rem):
    row = conn.execute(
        "SELECT interim_cert_json FROM payment_records WHERE id=?", (payment_id,),
    ).fetchone()
    if not row:
        return
    stored = {}
    if row['interim_cert_json']:
        try:
            stored = json.loads(row['interim_cert_json'])
        except json.JSONDecodeError:
            stored = {}
    changed = False
    cur_pay = None
    pay_row = conn.execute(
        "SELECT paid_amount FROM payment_records WHERE id=?", (payment_id,),
    ).fetchone()
    if pay_row:
        cur_pay = float(pay_row['paid_amount'] or 0)
    if stored.get('pre_submit_sc_paid') is None and pre_paid is not None:
        if cur_pay is None or abs(float(pre_paid) - cur_pay) > 0.02:
            stored['pre_submit_sc_paid'] = pre_paid
            stored['previous_paid'] = pre_paid
            changed = True
    if stored.get('pre_submit_sc_remainder') is None and pre_rem is not None:
        stored['pre_submit_sc_remainder'] = pre_rem
        changed = True
    if changed:
        conn.execute(
            "UPDATE payment_records SET interim_cert_json=? WHERE id=?",
            (json.dumps(stored, ensure_ascii=False), payment_id),
        )


def _enrich_payment_rows(rows):
    conn = get_conn()
    out = []
    for r in rows:
        d = dict(r)
        if d.get('payment_type') == 'interim_cert' and d.get('revoked_at'):
            stored = _load_cert_json(d.get('interim_cert_json'))
            stored = _backfill_original_row_snapshot(conn, d['id'], d, stored)
            snap = _row_pre_submit_from_cert(stored, conn, d)
            d['can_revert_to_normal'] = bool(snap and snap.get('payment_type') == 'normal')
            if d['can_revert_to_normal'] and snap.get('paid') is not None:
                d['paid_amount'] = snap['paid']
                if snap.get('remainder') is not None:
                    d['remainder_amount'] = snap['remainder']
                if snap.get('contract') is not None:
                    d['contract_amount'] = snap['contract']
            else:
                d['can_revert_to_normal'] = False
                pre_paid, pre_rem = _pre_submit_from_cert_json(d)
                if pre_paid is None or pre_rem is None:
                    pre_paid, pre_rem = _compute_pre_submit_snapshot(conn, d)
                d['pre_submit_sc_paid'] = pre_paid
                d['pre_submit_sc_remainder'] = pre_rem
                d['remainder_amount'] = pre_rem
                d['remainder_restored'] = True
        else:
            d['can_revert_to_normal'] = False
        out.append(d)
    conn.commit()
    conn.close()
    return out


def get_payment(payment_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM payment_records WHERE id=?", (payment_id,)).fetchone()
    conn.close()
    if not row:
        return None
    enriched = _enrich_payment_rows([row])
    return parse_payment_row(enriched[0]) if enriched else None


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
    data.setdefault('payment_type', 'normal')
    data.setdefault('backcharge_amount', 0)
    conn = get_conn()
    # 計算餘額
    if 'remainder_amount' not in data or data['remainder_amount'] is None:
        ca = float(data.get('contract_amount') or 0)
        pa = float(data.get('paid_amount') or 0)
        data['remainder_amount'] = ca - pa

    if not data.get('seq_no'):
        data['seq_no'] = get_next_seq_no(data['project_id'])

    data.setdefault('payment_type', 'normal')
    data.setdefault('backcharge_amount', 0)
    data.setdefault('deduction_total', 0)
    data.setdefault('deduction_ids_json', None)
    data.setdefault('vo_ids_json', None)
    data.setdefault('interim_cert_json', None)
    if data.get('deduction_ids') is not None:
        data['deduction_ids_json'] = json.dumps(data.pop('deduction_ids') or [])
    if data.get('vo_ids') is not None:
        data['vo_ids_json'] = json.dumps(data.pop('vo_ids') or [])
    if isinstance(data.get('interim_cert_json'), dict):
        data['interim_cert_json'] = json.dumps(data['interim_cert_json'])

    cur = conn.execute("""
        INSERT INTO payment_records (
            project_id, sc_id, seq_no, invoice_date, invoice_no, quotation_no,
            sc_no, company_name_en, company_name_zh, description,
            contract_amount, paid_amount, remainder_amount,
            oa_ref, oa_no, mc_ip_no, bc_to_sub, sub_ip_no, remark, pdf_path, ocr_status,
            payment_type, backcharge_amount, deduction_ids_json, deduction_total,
            vo_ids_json, interim_cert_json
        ) VALUES (
            :project_id, :sc_id, :seq_no, :invoice_date, :invoice_no, :quotation_no,
            :sc_no, :company_name_en, :company_name_zh, :description,
            :contract_amount, :paid_amount, :remainder_amount,
            :oa_ref, :oa_no, :mc_ip_no, :bc_to_sub, :sub_ip_no, :remark, :pdf_path, :ocr_status,
            :payment_type, :backcharge_amount, :deduction_ids_json, :deduction_total,
            :vo_ids_json, :interim_cert_json
        )
    """, data)
    conn.commit()
    new_id = cur.lastrowid
    _apply_payment_sc_vo_records(conn, new_id, data.get('vo_ids_json'), data.get('deduction_ids_json'))
    conn.commit()
    conn.close()
    if data.get('pdf_path'):
        add_sc_document(
            data['project_id'], data.get('sc_id'), data.get('sc_no'), 'invoice',
            data['pdf_path'], ocr_id=data.get('ocr_id'),
        )
    return new_id


def update_payment(payment_id, data):
    data.setdefault('payment_type', 'normal')
    data.setdefault('backcharge_amount', 0)
    data.setdefault('deduction_total', 0)
    if data.get('deduction_ids') is not None:
        data['deduction_ids_json'] = json.dumps(data.pop('deduction_ids') or [])
    if data.get('vo_ids') is not None:
        data['vo_ids_json'] = json.dumps(data.pop('vo_ids') or [])
    if isinstance(data.get('interim_cert_json'), dict):
        data['interim_cert_json'] = json.dumps(data['interim_cert_json'])
    data['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    data['id'] = payment_id
    conn = get_conn()
    existing = conn.execute(
        "SELECT * FROM payment_records WHERE id=?", (payment_id,),
    ).fetchone()
    if not existing:
        conn.close()
        raise ValueError('記錄不存在')
    if existing['revoked_at']:
        conn.close()
        raise ValueError('已撤回的計算書不可修改')
    if data.get('payment_type') == 'interim_cert':
        cert = _load_cert_json(data.get('interim_cert_json'))
        if existing['payment_type'] != 'interim_cert':
            cert = _inject_row_pre_submit(cert, existing)
        else:
            cert = _preserve_row_pre_submit(existing['interim_cert_json'], cert)
        data['interim_cert_json'] = json.dumps(cert, ensure_ascii=False)
    conn.execute("""
        UPDATE payment_records SET
            invoice_date=:invoice_date, invoice_no=:invoice_no, quotation_no=:quotation_no,
            sc_no=:sc_no, company_name_en=:company_name_en, company_name_zh=:company_name_zh,
            description=:description, contract_amount=:contract_amount,
            paid_amount=:paid_amount, remainder_amount=:remainder_amount,
            oa_ref=:oa_ref, oa_no=:oa_no, mc_ip_no=:mc_ip_no,
            bc_to_sub=:bc_to_sub, sub_ip_no=:sub_ip_no, remark=:remark,
            payment_type=:payment_type, backcharge_amount=:backcharge_amount,
            deduction_ids_json=:deduction_ids_json, deduction_total=:deduction_total,
            vo_ids_json=:vo_ids_json, interim_cert_json=:interim_cert_json,
            updated_at=:updated_at
        WHERE id=:id
    """, data)
    conn.execute(
        "UPDATE sc_vo_records SET applied_payment_id=NULL WHERE applied_payment_id=?",
        (payment_id,),
    )
    _apply_payment_sc_vo_records(conn, payment_id, data.get('vo_ids_json'), data.get('deduction_ids_json'))
    conn.commit()
    conn.close()


def _parse_id_json(raw):
    if not raw:
        return []
    try:
        ids = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, json.JSONDecodeError):
        return []
    return [int(x) for x in (ids or []) if x is not None]


def _apply_payment_sc_vo_records(conn, payment_id, vo_ids_json, deduction_ids_json):
    all_ids = _parse_id_json(vo_ids_json) + _parse_id_json(deduction_ids_json)
    for rid in all_ids:
        conn.execute(
            "UPDATE sc_vo_records SET applied_payment_id=? WHERE id=?",
            (payment_id, rid),
        )


def _apply_payment_deductions(conn, payment_id, deduction_ids_json):
    _apply_payment_sc_vo_records(conn, payment_id, None, deduction_ids_json)


def _applied_payment_summary(row):
    """由 JOIN 欄位組裝套用中的付款／計算書摘要（供 VO 登記列表顯示）"""
    pid = row.get('applied_payment_id')
    if not pid:
        return None
    app_no = None
    raw = row.get('applied_pay_cert_json')
    if raw:
        try:
            stored = json.loads(raw)
            app_no = stored.get('application_no')
        except (TypeError, json.JSONDecodeError):
            app_no = None
    pay_type = row.get('applied_pay_type') or 'normal'
    revoked = row.get('applied_pay_revoked_at')
    seq_no = row.get('applied_pay_seq_no')
    invoice_date = row.get('applied_pay_invoice_date')
    if pay_type == 'interim_cert':
        kind = '中期糧款計算書'
        detail = app_no or (f'#{seq_no}' if seq_no else f'#{pid}')
    else:
        kind = '付款登記'
        detail = f'#{seq_no}' if seq_no else f'#{pid}'
    if invoice_date:
        detail = f'{detail} · {str(invoice_date)[:10]}'
    if revoked:
        detail = f'{detail}（已撤回）'
    return {
        'id': pid,
        'payment_type': pay_type,
        'seq_no': seq_no,
        'invoice_date': invoice_date,
        'application_no': app_no,
        'revoked_at': revoked,
        'sc_no': row.get('applied_pay_sc_no'),
        'kind_label': kind,
        'detail_label': detail,
        'display_label': f'{kind} {detail}',
    }


def _strip_applied_pay_join(row):
    d = dict(row)
    d['applied_payment'] = _applied_payment_summary(d)
    for k in (
        'applied_pay_seq_no', 'applied_pay_type', 'applied_pay_invoice_date',
        'applied_pay_revoked_at', 'applied_pay_cert_json', 'applied_pay_sc_no',
    ):
        d.pop(k, None)
    return d


def get_sc_vo_records(project_id, sc_no=None, unapplied_only=False):
    conn = get_conn()
    sql = """
        SELECT svr.*,
               pr.seq_no AS applied_pay_seq_no,
               pr.payment_type AS applied_pay_type,
               pr.invoice_date AS applied_pay_invoice_date,
               pr.revoked_at AS applied_pay_revoked_at,
               pr.interim_cert_json AS applied_pay_cert_json,
               pr.sc_no AS applied_pay_sc_no
        FROM sc_vo_records svr
        LEFT JOIN payment_records pr ON pr.id = svr.applied_payment_id
        WHERE svr.project_id=?
    """
    params = [project_id]
    if sc_no:
        sql += " AND svr.sc_no=?"
        params.append(sc_no)
    if unapplied_only:
        sql += " AND svr.applied_payment_id IS NULL"
    sql += " ORDER BY svr.sc_no, svr.ref_no, svr.id"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_strip_applied_pay_join(r) for r in rows]


def get_sc_vo_records_by_ids(record_ids):
    if not record_ids:
        return []
    conn = get_conn()
    placeholders = ','.join('?' * len(record_ids))
    rows = conn.execute(
        f"SELECT * FROM sc_vo_records WHERE id IN ({placeholders})",
        list(record_ids),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def count_interim_certs_for_sc(project_id, sc_no):
    conn = get_conn()
    n = conn.execute("""
        SELECT COUNT(*) FROM payment_records
        WHERE project_id=? AND sc_no=? AND payment_type='interim_cert'
          AND (revoked_at IS NULL OR revoked_at = '')
    """, (project_id, sc_no)).fetchone()[0]
    conn.close()
    return int(n or 0)


def _line_amount_from_model(model, label_prefix):
    if not model:
        return 0.0
    for line in model.get('lines') or []:
        lbl = (line.get('label') or '')
        if lbl.startswith(label_prefix):
            return float(line.get('cum_current') or 0)
    return 0.0


def get_previous_interim_state(project_id, sc_no, exclude_payment_id=None):
    """取上一期中期糧款計算書累計狀態（對齊駿昇 Excel 欄位）"""
    conn = get_conn()
    sql = """
        SELECT id, paid_amount, interim_cert_json FROM payment_records
        WHERE project_id=? AND sc_no=? AND payment_type='interim_cert'
          AND (revoked_at IS NULL OR revoked_at = '')
    """
    params = [project_id, sc_no]
    if exclude_payment_id:
        sql += " AND id<>?"
        params.append(exclude_payment_id)
    sql += " ORDER BY invoice_date DESC, id DESC LIMIT 1"
    row = conn.execute(sql, params).fetchone()
    conn.close()
    if not row:
        return {
            'a_cum': 0.0, 'b_cum': 0.0, 'ret_cum': 0.0,
            'total_cum': 0.0, 'net_paid_total': 0.0,
            'standard_cums': {},
        }
    model = None
    if row['interim_cert_json']:
        try:
            stored = json.loads(row['interim_cert_json'])
            model = stored.get('model') or stored.get('model_snapshot')
        except json.JSONDecodeError:
            model = None
    if not model and row['interim_cert_json']:
        try:
            from interim_cert_report import build_interim_cert_model
            model = build_interim_cert_model(json.loads(row['interim_cert_json']))
        except Exception:
            model = None
    a_cum = _line_amount_from_model(model, 'A.')
    b_cum = _line_amount_from_model(model, 'B.')
    ret_cum = _line_amount_from_model(model, '減:保固金')
    total_cum = _line_amount_from_model(model, '總計')
    conn = get_conn()
    net_paid = conn.execute("""
        SELECT COALESCE(SUM(paid_amount), 0) FROM payment_records
        WHERE project_id=? AND sc_no=? AND payment_type='interim_cert'
          AND (revoked_at IS NULL OR revoked_at = '')
    """, (project_id, sc_no)).fetchone()[0]
    conn.close()
    standard_cums = {}
    if model:
        from sc_vo_templates import get_cert_standard_lines
        for tpl in get_cert_standard_lines():
            lbl = tpl['cert_label']
            for line in model.get('lines') or []:
                if line.get('label') == lbl:
                    standard_cums[tpl['code']] = float(line.get('cum_current') or 0)
                    break
    return {
        'a_cum': a_cum,
        'b_cum': b_cum,
        'ret_cum': ret_cum,
        'total_cum': total_cum or float(net_paid or 0),
        'net_paid_total': float(net_paid or 0),
        'last_payment_id': row['id'],
        'standard_cums': standard_cums,
        'model': model,
    }


def sum_sc_vo_amount(project_id, sc_no, record_type='vo'):
    conn = get_conn()
    row = conn.execute("""
        SELECT COALESCE(SUM(amount), 0) AS total FROM sc_vo_records
        WHERE project_id=? AND sc_no=? AND record_type=?
    """, (project_id, sc_no, record_type)).fetchone()
    conn.close()
    return float(row['total'] or 0)


def sync_sc_vo_amount(project_id, sc_no):
    """同步 subcontractors.vo_amount = 所有 VO 後加項總和"""
    total = sum_sc_vo_amount(project_id, sc_no, 'vo')
    conn = get_conn()
    conn.execute("""
        UPDATE subcontractors SET vo_amount=?
        WHERE project_id=? AND sc_no=?
    """, (total, project_id, sc_no))
    conn.commit()
    conn.close()
    return total


def get_next_svr_seq_no(project_id):
    conn = get_conn()
    count = conn.execute(
        "SELECT COUNT(*) FROM sc_vo_records WHERE project_id = ?",
        (project_id,),
    ).fetchone()[0]
    conn.close()
    return str(count + 1)


def _svr_ref_prefix(record_type):
    return 'VO' if record_type == 'vo' else 'CC'


def _parse_svr_ref_serial(ref_no, prefix):
    if not ref_no:
        return None
    s = str(ref_no).strip().upper()
    p = prefix.upper()
    m = re.match(rf'^{re.escape(p)}[-\s]?(\d+)$', s)
    if m:
        return int(m.group(1))
    return None


_SVR_REF_PLACEHOLDERS = frozenset({'VO', 'CC', 'MAT', 'PN', 'BC', 'ADV'})


def _is_svr_ref_placeholder(ref_no, record_type):
    """範本 ref_no（如 VO、CC）或空白 — 需自動建議 VO-001 / CC-001"""
    if not ref_no or not str(ref_no).strip():
        return True
    s = str(ref_no).strip().upper()
    prefix = _svr_ref_prefix(record_type).upper()
    if _parse_svr_ref_serial(s, prefix) is not None:
        return False
    return s in _SVR_REF_PLACEHOLDERS or s == prefix


def _resolve_svr_ref_no(data, existing=None, exclude_id=None):
    """若 ref 為空白或僅前綴佔位，按判項自動編號"""
    rt = data.get('record_type') or (existing and existing.get('record_type')) or 'deduction'
    ref = data.get('ref_no')
    if ref is None and existing:
        ref = existing.get('ref_no')
    ref = (ref or '').strip()
    pid = data.get('project_id') or (existing and existing.get('project_id'))
    sc_no = data.get('sc_no') or (existing and existing.get('sc_no'))
    rid = exclude_id or data.get('id') or (existing and existing.get('id'))
    if not _is_svr_ref_placeholder(ref, rt):
        return ref or None
    if pid and sc_no:
        return suggest_next_svr_ref_no(pid, sc_no, rt, exclude_id=rid)
    return ref or None


def suggest_next_svr_ref_no(project_id, sc_no, record_type, exclude_id=None):
    """按判項 + 類型建議下一個 VO-xxx / CC-xxx（各自獨立序號）"""
    prefix = _svr_ref_prefix(record_type)
    rt = 'vo' if record_type == 'vo' else 'deduction'
    conn = get_conn()
    sql = """
        SELECT id, ref_no FROM sc_vo_records
        WHERE project_id=? AND sc_no=? AND record_type=?
    """
    params = [project_id, sc_no, rt]
    if exclude_id:
        sql += " AND id<>?"
        params.append(exclude_id)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    max_n = 0
    for r in rows:
        n = _parse_svr_ref_serial(r['ref_no'], prefix)
        if n is not None:
            max_n = max(max_n, n)
    return f"{prefix}-{max_n + 1:03d}"


def _normalize_svr_amount(record_type, amount):
    amt = float(amount or 0)
    if record_type == 'vo' and amt < 0:
        return abs(amt)
    if record_type == 'deduction' and amt > 0:
        return -abs(amt)
    return amt


def _svr_row_payload(data, existing=None):
    """合併 sc_vo_records 可寫入欄位（existing 為 sqlite Row）"""
    ex = dict(existing) if existing else {}
    rt = data.get('record_type') or ex.get('record_type') or 'deduction'
    amt_src = data.get('amount') if data.get('amount') is not None else ex.get('amount')
    payload = {
        'sc_id': data.get('sc_id', ex.get('sc_id')),
        'sc_no': data.get('sc_no', ex.get('sc_no')),
        'record_type': rt,
        'ref_no': data.get('ref_no', ex.get('ref_no')),
        'description': data.get('description', ex.get('description')),
        'amount': _normalize_svr_amount(rt, amt_src),
        'line_code': data.get('line_code', ex.get('line_code')),
        'seq_no': data.get('seq_no', ex.get('seq_no')),
        'invoice_date': data.get('invoice_date', ex.get('invoice_date')),
        'invoice_no': data.get('invoice_no', ex.get('invoice_no')),
        'quotation_no': data.get('quotation_no', ex.get('quotation_no')),
        'company_name_en': data.get('company_name_en', ex.get('company_name_en')),
        'company_name_zh': data.get('company_name_zh', ex.get('company_name_zh')),
        'service_description': data.get('service_description', ex.get('service_description')),
        'oa_ref': data.get('oa_ref', ex.get('oa_ref')),
        'oa_no': data.get('oa_no', ex.get('oa_no')),
        'remark': data.get('remark', ex.get('remark')),
        'main_contract_vo_no': data.get('main_contract_vo_no', ex.get('main_contract_vo_no')),
        'approval_attachment': data.get('approval_attachment', ex.get('approval_attachment')),
        'approval_attachment_name': data.get('approval_attachment_name', ex.get('approval_attachment_name')),
        'quotation_attachment': data.get('quotation_attachment', ex.get('quotation_attachment')),
        'quotation_attachment_name': data.get('quotation_attachment_name', ex.get('quotation_attachment_name')),
    }
    return payload


def seed_sc_vo_template_catalog(conn=None):
    """首次建庫寫入內建範本"""
    from sc_vo_templates import default_catalog_seed_rows, invalidate_template_cache
    own = conn is None
    if own:
        conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM sc_vo_template_catalog").fetchone()[0]
    if count:
        if own:
            conn.close()
        return 0
    for row in default_catalog_seed_rows():
        conn.execute("""
            INSERT INTO sc_vo_template_catalog (
                code, source, record_type, ref_no, description, cert_label,
                group_name, direction, sort_order, is_builtin, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row['code'], row['source'], row.get('record_type'),
            row.get('ref_no'), row.get('description'), row.get('cert_label'),
            row.get('group_name'), row.get('direction'),
            row.get('sort_order') or 0, row.get('is_builtin') or 0,
            row.get('is_active', 1),
        ))
    conn.commit()
    invalidate_template_cache()
    if own:
        conn.close()
    return len(default_catalog_seed_rows())


def list_sc_vo_template_catalog(source=None, active_only=True):
    conn = get_conn()
    sql = "SELECT * FROM sc_vo_template_catalog WHERE source != 'system'"
    params = []
    if source:
        sql += " AND source=?"
        params.append(source)
    if active_only:
        sql += " AND is_active=1"
    sql += " ORDER BY source, sort_order, code"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_sc_vo_template_catalog(code):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM sc_vo_template_catalog WHERE code=?",
        ((code or '').strip(),),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def _normalize_template_code(code):
    s = re.sub(r'[^a-z0-9_]+', '_', (code or '').strip().lower())
    s = re.sub(r'_+', '_', s).strip('_')
    return s or None


def upsert_sc_vo_template_catalog(data):
    from sc_vo_templates import invalidate_template_cache
    code = _normalize_template_code(data.get('code'))
    if not code:
        raise ValueError('缺少範本代碼')
    source = (data.get('source') or 'sc_vo').strip()
    if source not in ('sc_vo', 'cert_standard'):
        raise ValueError('source 須為 sc_vo 或 cert_standard')
    existing = get_sc_vo_template_catalog(code)
    if source == 'sc_vo':
        record_type = data.get('record_type') or (existing or {}).get('record_type') or 'deduction'
        if record_type not in ('vo', 'deduction'):
            raise ValueError('record_type 須為 vo 或 deduction')
        direction = None
        group_name = data.get('group_name') or data.get('group') or record_type
    else:
        direction = data.get('direction') or (existing or {}).get('direction') or 'ded'
        if direction not in ('add', 'ded'):
            raise ValueError('direction 須為 add 或 ded')
        record_type = direction
        group_name = data.get('group_name') or data.get('group') or 'standard'
    description = (data.get('description') or '').strip() or None
    cert_label = (data.get('cert_label') or '').strip() or None
    ref_no = (data.get('ref_no') or '').strip() or None
    sort_order = int(data.get('sort_order') or (existing or {}).get('sort_order') or 0)
    is_active = 1 if data.get('is_active', True) else 0
    conn = get_conn()
    if existing:
        conn.execute("""
            UPDATE sc_vo_template_catalog SET
                source=?, record_type=?, ref_no=?, description=?, cert_label=?,
                group_name=?, direction=?, sort_order=?, is_active=?,
                updated_at=datetime('now', 'localtime')
            WHERE code=?
        """, (
            source, record_type, ref_no, description, cert_label,
            group_name, direction, sort_order, is_active, code,
        ))
    else:
        conn.execute("""
            INSERT INTO sc_vo_template_catalog (
                code, source, record_type, ref_no, description, cert_label,
                group_name, direction, sort_order, is_builtin, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        """, (
            code, source, record_type, ref_no, description, cert_label,
            group_name, direction, sort_order, is_active,
        ))
    conn.commit()
    conn.close()
    invalidate_template_cache()
    return get_sc_vo_template_catalog(code)


def delete_sc_vo_template_catalog(code):
    from sc_vo_templates import invalidate_template_cache
    code = (code or '').strip()
    row = get_sc_vo_template_catalog(code)
    if not row:
        raise ValueError('找不到範本')
    if row.get('is_builtin'):
        raise ValueError('內建範本不可刪除，可改為停用')
    conn = get_conn()
    in_use = conn.execute(
        "SELECT COUNT(*) FROM sc_vo_records WHERE line_code=?",
        (code,),
    ).fetchone()[0]
    if in_use:
        conn.close()
        raise ValueError('已有登記記錄使用此範本，不可刪除')
    conn.execute("DELETE FROM sc_vo_template_catalog WHERE code=?", (code,))
    conn.commit()
    conn.close()
    invalidate_template_cache()
    return True


def create_sc_vo_record(data):
    data.setdefault('record_type', 'deduction')
    data.setdefault('ref_no', None)
    data.setdefault('description', None)
    data.setdefault('amount', 0)
    data.setdefault('line_code', None)
    from sc_vo_templates import get_template
    tpl = get_template(data.get('line_code'))
    if tpl and not (data.get('ref_no') or '').strip():
        data['ref_no'] = tpl.get('ref_no')
    if tpl and not data.get('description'):
        data['description'] = tpl.get('description')
    if tpl and not data.get('record_type'):
        data['record_type'] = tpl.get('record_type')
    data['ref_no'] = _resolve_svr_ref_no(data)
    if not data.get('seq_no') and data.get('project_id'):
        data['seq_no'] = get_next_svr_seq_no(data['project_id'])
    row = _svr_row_payload(data)
    row['project_id'] = data['project_id']
    conn = get_conn()
    cur = conn.execute("""
        INSERT INTO sc_vo_records (
            project_id, sc_id, sc_no, record_type, ref_no, description, amount, line_code,
            seq_no, invoice_date, invoice_no, quotation_no,
            company_name_en, company_name_zh, service_description,
            oa_ref, oa_no, remark, main_contract_vo_no,
            approval_attachment, approval_attachment_name,
            quotation_attachment, quotation_attachment_name
        ) VALUES (
            :project_id, :sc_id, :sc_no, :record_type, :ref_no, :description, :amount, :line_code,
            :seq_no, :invoice_date, :invoice_no, :quotation_no,
            :company_name_en, :company_name_zh, :service_description,
            :oa_ref, :oa_no, :remark, :main_contract_vo_no,
            :approval_attachment, :approval_attachment_name,
            :quotation_attachment, :quotation_attachment_name
        )
    """, row)
    conn.commit()
    new_id = cur.lastrowid
    if row['record_type'] == 'vo':
        sync_sc_vo_amount(data['project_id'], data['sc_no'])
    conn.close()
    return new_id


def update_sc_vo_record(record_id, data):
    conn = get_conn()
    existing = conn.execute("SELECT * FROM sc_vo_records WHERE id=?", (record_id,)).fetchone()
    if not existing:
        conn.close()
        return False
    merged = {**dict(existing), **data, 'project_id': existing['project_id']}
    data['ref_no'] = _resolve_svr_ref_no(merged, existing=existing, exclude_id=record_id)
    row = _svr_row_payload(data, existing)
    row['id'] = record_id
    conn.execute("""
        UPDATE sc_vo_records SET
            sc_id=:sc_id, sc_no=:sc_no, record_type=:record_type,
            ref_no=:ref_no, description=:description, amount=:amount, line_code=:line_code,
            seq_no=:seq_no, invoice_date=:invoice_date, invoice_no=:invoice_no,
            quotation_no=:quotation_no, company_name_en=:company_name_en,
            company_name_zh=:company_name_zh, service_description=:service_description,
            oa_ref=:oa_ref, oa_no=:oa_no, remark=:remark,
            main_contract_vo_no=:main_contract_vo_no,
            approval_attachment=:approval_attachment,
            approval_attachment_name=:approval_attachment_name,
            quotation_attachment=:quotation_attachment,
            quotation_attachment_name=:quotation_attachment_name
        WHERE id=:id
    """, row)
    conn.commit()
    conn.close()
    sync_sc_vo_amount(existing['project_id'], existing['sc_no'])
    if row.get('sc_no') and row['sc_no'] != existing['sc_no']:
        sync_sc_vo_amount(existing['project_id'], row['sc_no'])
    return True


def update_sc_vo_attachment(record_id, att_type, file_path, original_name):
    conn = get_conn()
    existing = conn.execute("SELECT id FROM sc_vo_records WHERE id=?", (record_id,)).fetchone()
    if not existing:
        conn.close()
        return False
    if att_type == 'approval':
        conn.execute("""
            UPDATE sc_vo_records SET approval_attachment=?, approval_attachment_name=?
            WHERE id=?
        """, (file_path, original_name, record_id))
    elif att_type == 'quotation':
        conn.execute("""
            UPDATE sc_vo_records SET quotation_attachment=?, quotation_attachment_name=?
            WHERE id=?
        """, (file_path, original_name, record_id))
    else:
        conn.close()
        return False
    conn.commit()
    conn.close()
    return True


def delete_sc_vo_record(record_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM sc_vo_records WHERE id=?", (record_id,)).fetchone()
    if not row:
        conn.close()
        return False
    if row['applied_payment_id']:
        conn.close()
        raise ValueError('已套用於糧款計算書，不能刪除')
    conn.execute("DELETE FROM sc_vo_records WHERE id=?", (record_id,))
    conn.commit()
    conn.close()
    if row['record_type'] == 'vo':
        sync_sc_vo_amount(row['project_id'], row['sc_no'])
    return True


def get_sc_vo_record(record_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM sc_vo_records WHERE id=?", (record_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def parse_payment_row(row):
    if not row:
        return row
    d = dict(row)
    if d.get('deduction_ids_json'):
        try:
            d['deduction_ids'] = json.loads(d['deduction_ids_json'])
        except json.JSONDecodeError:
            d['deduction_ids'] = []
    if d.get('vo_ids_json'):
        try:
            d['vo_ids'] = json.loads(d['vo_ids_json'])
        except json.JSONDecodeError:
            d['vo_ids'] = []
    if d.get('interim_cert_json'):
        try:
            d['interim_cert'] = json.loads(d['interim_cert_json'])
        except json.JSONDecodeError:
            d['interim_cert'] = None
    return d


def revoke_interim_cert(payment_id):
    """還原計算書至提交前：普通付款列恢復原數值；純糧款列標記撤回"""
    conn = get_conn()
    row = conn.execute("""
        SELECT id, project_id, payment_type, revoked_at, sc_no, contract_amount,
               paid_amount, remainder_amount, interim_cert_json
        FROM payment_records WHERE id=?
    """, (payment_id,)).fetchone()
    if not row:
        conn.close()
        raise ValueError('記錄不存在')
    if row['payment_type'] != 'interim_cert':
        conn.close()
        raise ValueError('僅中期糧款計算書可還原')
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    row_dict = dict(row)
    if row['revoked_at']:
        stored = _load_cert_json(row['interim_cert_json'])
        stored = _backfill_original_row_snapshot(conn, payment_id, row_dict, stored)
        row_snap = _row_pre_submit_from_cert(stored, conn, row_dict)
        if not (row_snap and row_snap.get('payment_type') == 'normal'):
            conn.close()
            raise ValueError('此計算書已還原')
        stored['revoked_cert_archived_at'] = now
        conn.execute(
            "UPDATE sc_vo_records SET applied_payment_id=NULL WHERE applied_payment_id=?",
            (payment_id,),
        )
        rem = row_snap['remainder']
        if rem is None:
            rem = float(row_dict.get('remainder_amount') or 0)
        contract = row_snap.get('contract')
        if contract is None:
            contract = float(row_dict.get('contract_amount') or 0)
        conn.execute("""
            UPDATE payment_records SET
                payment_type='normal',
                paid_amount=?,
                remainder_amount=?,
                contract_amount=?,
                revoked_at=NULL,
                vo_ids_json=NULL,
                deduction_ids_json=NULL,
                deduction_total=0,
                interim_cert_json=?,
                updated_at=?
            WHERE id=?
        """, (
            row_snap['paid'],
            rem,
            contract,
            json.dumps(stored, ensure_ascii=False),
            now,
            payment_id,
        ))
        conn.commit()
        conn.close()
        return True
    pre_paid, pre_rem = _compute_pre_submit_snapshot(conn, row)
    _ensure_pre_submit_in_cert_json(conn, payment_id, pre_paid, pre_rem)
    fresh = conn.execute(
        "SELECT interim_cert_json FROM payment_records WHERE id=?", (payment_id,),
    ).fetchone()
    stored = _load_cert_json(fresh['interim_cert_json'] if fresh else None)
    stored = _backfill_original_row_snapshot(conn, payment_id, row_dict, stored)
    stored['revoked_cert_archived_at'] = now
    row_snap = _row_pre_submit_from_cert(stored, conn, row_dict)
    conn.execute(
        "UPDATE sc_vo_records SET applied_payment_id=NULL WHERE applied_payment_id=?",
        (payment_id,),
    )
    if row_snap and row_snap.get('payment_type') == 'normal':
        rem = row_snap['remainder']
        if rem is None:
            rem = float(row_dict.get('remainder_amount') or 0)
        contract = row_snap.get('contract')
        if contract is None:
            contract = float(row_dict.get('contract_amount') or 0)
        conn.execute("""
            UPDATE payment_records SET
                payment_type='normal',
                paid_amount=?,
                remainder_amount=?,
                contract_amount=?,
                revoked_at=NULL,
                vo_ids_json=NULL,
                deduction_ids_json=NULL,
                deduction_total=0,
                interim_cert_json=?,
                updated_at=?
            WHERE id=?
        """, (
            row_snap['paid'],
            rem,
            contract,
            json.dumps(stored, ensure_ascii=False),
            now,
            payment_id,
        ))
    else:
        conn.execute(
            "UPDATE payment_records SET revoked_at=?, remainder_amount=?, "
            "interim_cert_json=?, updated_at=? WHERE id=?",
            (now, pre_rem, json.dumps(stored, ensure_ascii=False), now, payment_id),
        )
    conn.commit()
    conn.close()
    return True


def _assert_sc_vo_ids_available(conn, record_ids, payment_id):
    """還原計算書前確認 VO／扣款未被其他糧款占用"""
    conflicts = []
    for rid in record_ids:
        row = conn.execute(
            "SELECT id, ref_no, applied_payment_id FROM sc_vo_records WHERE id=?",
            (rid,),
        ).fetchone()
        if not row:
            conflicts.append(f'登記 #{rid} 不存在')
            continue
        aid = row['applied_payment_id']
        if aid and aid != payment_id:
            ref = row['ref_no'] or f'#{rid}'
            conflicts.append(f'{ref} 已套用於糧款 #{aid}')
    if conflicts:
        raise ValueError('無法還原：' + '；'.join(conflicts))


def restore_interim_cert(payment_id):
    """還原已撤回的中期糧款計算書：重新計入累計並套用原 VO／扣款"""
    conn = get_conn()
    row = conn.execute("""
        SELECT id, project_id, payment_type, revoked_at, sc_no, contract_amount,
               paid_amount, vo_ids_json, deduction_ids_json, interim_cert_json
        FROM payment_records WHERE id=?
    """, (payment_id,)).fetchone()
    if not row:
        conn.close()
        raise ValueError('記錄不存在')
    if row['payment_type'] != 'interim_cert':
        conn.close()
        raise ValueError('僅中期糧款計算書可還原')
    if not row['revoked_at']:
        conn.close()
        raise ValueError('此計算書未撤回')
    row_dict = dict(row)
    stored = _load_cert_json(row['interim_cert_json'])
    stored = _backfill_original_row_snapshot(conn, payment_id, row_dict, stored)
    if stored != _load_cert_json(row['interim_cert_json']):
        conn.execute(
            "UPDATE payment_records SET interim_cert_json=? WHERE id=?",
            (json.dumps(stored, ensure_ascii=False), payment_id),
        )
    all_ids = _parse_id_json(row['vo_ids_json']) + _parse_id_json(row['deduction_ids_json'])
    _assert_sc_vo_ids_available(conn, all_ids, payment_id)
    hint = float(row['contract_amount'] or 0) or None
    remainder = _interim_remainder_on_submit(
        conn, row['project_id'], row['sc_no'], row['paid_amount'],
        contract_amount_hint=hint, exclude_payment_id=payment_id,
    )
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute(
        "UPDATE payment_records SET revoked_at=NULL, remainder_amount=?, updated_at=? WHERE id=?",
        (remainder, now, payment_id),
    )
    _apply_payment_sc_vo_records(conn, payment_id, row['vo_ids_json'], row['deduction_ids_json'])
    conn.commit()
    conn.close()
    return True


def delete_payment(payment_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT project_id, payment_type, revoked_at FROM payment_records WHERE id=?",
        (payment_id,),
    ).fetchone()
    if not row:
        conn.close()
        return False
    if row['payment_type'] == 'interim_cert' and not row['revoked_at']:
        conn.close()
        raise ValueError('請先使用「還原」退回提交前')
    project_id = row['project_id']
    conn.execute(
        "UPDATE sc_vo_records SET applied_payment_id=NULL WHERE applied_payment_id=?",
        (payment_id,),
    )
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


def replace_subcontractors_for_project(project_id):
    """清除項目分判商（Excel 重新同步用；須先清除付款記錄）"""
    conn = get_conn()
    conn.execute("DELETE FROM subcontractors WHERE project_id=?", (project_id,))
    conn.commit()
    conn.close()


# ─── 地盤糧期狀況 (Interim Payments) ───────────────────────────────────

def _format_receipt_date_display(iso_date):
    if not iso_date:
        return ''
    s = str(iso_date).strip()[:10]
    if len(s) != 10:
        return str(iso_date)
    try:
        from datetime import datetime
        d = datetime.strptime(s, '%Y-%m-%d')
        return f'{d.day}/{d.month}/{d.year}'
    except ValueError:
        return s


def format_ip_receipt_display(row):
    """收款記錄顯示（支票：#828310 , 003, 22/3/2025；過數：備註 · 日期）"""
    method = (row.get('receipt_method') or '').strip()
    cheque_no = (row.get('receipt_cheque_no') or '').strip()
    bank = (row.get('receipt_bank') or '').strip()
    note = (row.get('receipt_note') or '').strip()
    date_disp = _format_receipt_date_display(row.get('receipt_date'))

    if method == 'transfer' or (not cheque_no and note):
        label = note or '過數'
        return f'{label} · {date_disp}' if date_disp else label

    if cheque_no or bank or method == 'cheque':
        no = cheque_no
        if no and not no.startswith('#'):
            no = f'#{no.lstrip("#")}'
        if no and bank and date_disp:
            return f'{no} , {bank}, {date_disp}'
        if no and bank:
            return f'{no} , {bank}'
        if no and date_disp:
            return f'{no}, {date_disp}'
        return no or bank or date_disp or None

    if date_disp:
        return date_disp
    return None


def enrich_interim_payment(row):
    r = dict(row)
    r['receipt_display'] = format_ip_receipt_display(r)
    return r


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


def set_subcontractor_trade_labels(project_id, labels):
    """Summary row 41 工種簡稱 → subcontractors.trade_label"""
    if not labels:
        return
    conn = get_conn()
    for sc_no, label in labels.items():
        sc = (sc_no or '').strip().upper()
        lbl = (label or '').strip()
        if not sc or not lbl:
            continue
        conn.execute(
            "UPDATE subcontractors SET trade_label=? WHERE project_id=? AND UPPER(sc_no)=?",
            (lbl, project_id, sc),
        )
    conn.commit()
    conn.close()


def get_ip_sc_drilldown(project_id, ip_no, sc_no):
    """分包糧期 cell drill-down：矩陣金額 vs 付款登記明細"""
    ip_key = (ip_no or '').strip().upper()
    sc_key = (sc_no or '').strip().upper()
    conn = get_conn()
    row = conn.execute("""
        SELECT amount FROM interim_payment_sc_lines
        WHERE project_id=? AND UPPER(ip_no)=? AND UPPER(sc_no)=?
    """, (project_id, ip_key, sc_key)).fetchone()
    matrix_amt = float(row['amount']) if row else 0.0
    payments = conn.execute("""
        SELECT id, seq_no, invoice_date, invoice_no, description,
               paid_amount, sub_ip_no, mc_ip_no, sc_no
        FROM payment_records
        WHERE project_id=? AND UPPER(sc_no)=? AND UPPER(sub_ip_no)=?
          AND (revoked_at IS NULL OR revoked_at = '')
        ORDER BY CAST(seq_no AS INTEGER), seq_no
    """, (project_id, sc_key, ip_key)).fetchall()
    conn.close()
    items = [dict(r) for r in payments]
    records_total = sum(float(p.get('paid_amount') or 0) for p in items)
    diff = matrix_amt - records_total
    return {
        'ip_no': ip_key,
        'sc_no': sc_key,
        'matrix_amount': matrix_amt,
        'records_total': records_total,
        'diff': diff,
        'match': abs(diff) < 0.02,
        'payments': items,
    }


def replace_interim_payment_sc_lines(project_id, lines):
    """取代項目全部分包糧期明細（Excel Summary 矩陣）"""
    conn = get_conn()
    conn.execute("DELETE FROM interim_payment_sc_lines WHERE project_id=?", (project_id,))
    for ln in lines or []:
        sc_no = (ln.get('sc_no') or '').strip()
        ip_no = (ln.get('ip_no') or '').strip().upper()
        amt = float(ln.get('amount') or 0)
        if not sc_no or not ip_no or not amt:
            continue
        conn.execute("""
            INSERT INTO interim_payment_sc_lines (project_id, ip_no, sc_no, amount)
            VALUES (?, ?, ?, ?)
        """, (project_id, ip_no, sc_no.upper(), amt))
    conn.commit()
    conn.close()


def get_interim_payment_sc_lines(project_id):
    conn = get_conn()
    rows = conn.execute("""
        SELECT ip_no, sc_no, amount FROM interim_payment_sc_lines
        WHERE project_id=? ORDER BY ip_no, sc_no
    """, (project_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def build_ip_sc_matrix(project_id, ip_items=None):
    """分包糧期矩陣：columns + 每期各 SC 金額 + 分判商主檔對照"""
    if ip_items is None:
        ip_items = get_interim_payments(project_id)
    lines = get_interim_payment_sc_lines(project_id)
    if not lines and not ip_items:
        return {'columns': [], 'columns_detail': [], 'rows': [], 'column_totals': {}}

    sc_set = set()
    by_ip = {}
    for ln in lines:
        ip_no = (ln['ip_no'] or '').upper()
        sc_no = (ln['sc_no'] or '').upper()
        sc_set.add(sc_no)
        by_ip.setdefault(ip_no, {})[sc_no] = ln['amount'] or 0

    columns = sorted(sc_set, key=lambda s: (s.replace('SC-', ''), s))
    rows = []
    column_totals = {sc: 0.0 for sc in columns}
    for it in ip_items:
        ip_no = (it.get('ip_no') or '').upper()
        cells = {sc: by_ip.get(ip_no, {}).get(sc, 0) for sc in columns}
        row_total = it.get('subcon_paid') or sum(cells.values())
        for sc, amt in cells.items():
            column_totals[sc] += amt or 0
        rows.append({
            'ip_no': ip_no,
            'cells': cells,
            'total': row_total,
            'subcon_paid_pct': it.get('subcon_paid_pct'),
        })

    conn = get_conn()
    sc_rows = conn.execute("""
        SELECT sc.sc_no, sc.company_name_en, sc.company_name_zh, sc.description,
               sc.trade_label, sc.contract_amount,
               COALESCE(SUM(pr.paid_amount), 0) AS total_paid_records
        FROM subcontractors sc
        LEFT JOIN payment_records pr ON pr.project_id = sc.project_id
            AND (pr.sc_id = sc.id OR pr.sc_no = sc.sc_no)
            AND (pr.revoked_at IS NULL OR pr.revoked_at = '')
        WHERE sc.project_id = ? AND NOT sc.is_excluded
        GROUP BY sc.id
    """, (project_id,)).fetchall()
    conn.close()
    sc_map = {(r['sc_no'] or '').upper(): dict(r) for r in sc_rows}

    columns_detail = []
    for sc in columns:
        info = sc_map.get(sc, {})
        contract = float(info.get('contract_amount') or 0)
        paid_records = float(info.get('total_paid_records') or 0)
        paid_matrix = float(column_totals.get(sc) or 0)
        remainder = contract - paid_records
        columns_detail.append({
            'sc_no': sc,
            'trade_label': info.get('trade_label'),
            'company_name_en': info.get('company_name_en'),
            'company_name_zh': info.get('company_name_zh'),
            'description': info.get('description'),
            'contract_amount': contract,
            'total_paid_matrix': paid_matrix,
            'total_paid_records': paid_records,
            'remainder': remainder,
            'matrix_match': abs(paid_matrix - paid_records) < 0.02,
            'overpaid': remainder < -0.02,
        })

    overpaid = [d for d in columns_detail if d.get('overpaid')]
    return {
        'columns': columns,
        'columns_detail': columns_detail,
        'rows': rows,
        'column_totals': column_totals,
        'summary': {
            'total_contract': sum(d['contract_amount'] for d in columns_detail),
            'total_paid_matrix': sum(column_totals.values()),
            'total_paid_records': sum(d['total_paid_records'] for d in columns_detail),
            'all_matrix_match': all(d['matrix_match'] for d in columns_detail),
            'overpaid_count': len(overpaid),
            'overpaid_sc': [d['sc_no'] for d in overpaid],
        },
    }


def replace_interim_payments(project_id, items, meta=None, sc_lines=None):
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
    if sc_lines is not None:
        replace_interim_payment_sc_lines(project_id, sc_lines)


def get_interim_payments(project_id):
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM interim_payments WHERE project_id=?
        ORDER BY seq_no, ip_no
    """, (project_id,)).fetchall()
    conn.close()
    return [enrich_interim_payment(r) for r in rows]


def get_ip_period_summary(project_id):
    """地盤糧期狀況（項目概覽用）"""
    project = get_project(project_id)
    if not project:
        return None
    items = calc_ip_cumulative_pcts(
        get_interim_payments(project_id),
        project.get('contract_amount'),
    )
    sc_matrix = build_ip_sc_matrix(project_id, items)
    return {
        'site_period_text': project.get('site_period_text'),
        'project_name_en': project.get('project_name_en'),
        'project_name_zh': project.get('project_name_zh'),
        'project_name': project.get('project_name'),
        'project_code': project.get('project_code'),
        'contract_amount': project.get('contract_amount') or 0,
        'items': items,
        'sc_matrix': sc_matrix,
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
    return enrich_interim_payment(row) if row else None


def set_ip_receipt_attachment(ip_id, file_path, original_filename=None):
    conn = get_conn()
    conn.execute("""
        UPDATE interim_payments
        SET receipt_attachment=?, receipt_attachment_name=?
        WHERE id=?
    """, (file_path, original_filename, ip_id))
    conn.commit()
    conn.close()


def clear_ip_receipt_attachment(ip_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT receipt_attachment FROM interim_payments WHERE id=?", (ip_id,)
    ).fetchone()
    conn.execute("""
        UPDATE interim_payments
        SET receipt_attachment=NULL, receipt_attachment_name=NULL
        WHERE id=?
    """, (ip_id,))
    conn.commit()
    conn.close()
    return row['receipt_attachment'] if row else None


def set_ip_cert_attachment(ip_id, file_path, original_filename=None):
    conn = get_conn()
    conn.execute("""
        UPDATE interim_payments
        SET ip_cert_attachment=?, ip_cert_attachment_name=?
        WHERE id=?
    """, (file_path, original_filename, ip_id))
    conn.commit()
    conn.close()


def clear_ip_cert_attachment(ip_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT ip_cert_attachment FROM interim_payments WHERE id=?", (ip_id,)
    ).fetchone()
    conn.execute("""
        UPDATE interim_payments
        SET ip_cert_attachment=NULL, ip_cert_attachment_name=NULL
        WHERE id=?
    """, (ip_id,))
    conn.commit()
    conn.close()
    return row['ip_cert_attachment'] if row else None


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
    for f in ['applied_date', 'certificate_date', 'subcon_cert_date', 'receipt_date']:
        data.setdefault(f, None)
    for f in ['application_amount', 'certified_income', 'subcon_paid']:
        data.setdefault(f, 0)
    for f in ['receipt_method', 'receipt_cheque_no', 'receipt_bank', 'receipt_note',
              'receipt_attachment', 'receipt_attachment_name']:
        data.setdefault(f, None)
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
                subcon_paid=:subcon_paid, subcon_cert_date=:subcon_cert_date,
                receipt_method=:receipt_method, receipt_cheque_no=:receipt_cheque_no,
                receipt_bank=:receipt_bank, receipt_date=:receipt_date,
                receipt_note=:receipt_note
            WHERE id=:id AND project_id=:project_id
        """, data)
        ip_id = data['id']
    else:
        cur = conn.execute("""
            INSERT INTO interim_payments (
                project_id, ip_no, seq_no, applied_date,
                application_amount, certified_income, certificate_date,
                subcon_paid, subcon_cert_date,
                receipt_method, receipt_cheque_no, receipt_bank, receipt_date, receipt_note
            ) VALUES (
                :project_id, :ip_no, :seq_no, :applied_date,
                :application_amount, :certified_income, :certificate_date,
                :subcon_paid, :subcon_cert_date,
                :receipt_method, :receipt_cheque_no, :receipt_bank, :receipt_date, :receipt_note
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
    ip_row = conn.execute(
        "SELECT ip_no FROM interim_payments WHERE id=?", (ip_id,)
    ).fetchone()
    ip_no = ip_row['ip_no'] if ip_row else None
    conn.execute("DELETE FROM interim_payments WHERE id=?", (ip_id,))
    if ip_no:
        conn.execute(
            "DELETE FROM interim_payment_sc_lines WHERE project_id=? AND ip_no=?",
            (project_id, ip_no),
        )
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

    # 按分判商統計（名稱取自 subcontractors，付款取自 payment_records）
    sc_stats = conn.execute("""
        SELECT sc.sc_no, sc.company_name_en, sc.company_name_zh, sc.description,
               sc.contract_amount,
               COALESCE(pay.total_paid, 0) AS total_paid,
               sc.contract_amount - COALESCE(pay.total_paid, 0) AS remainder,
               COALESCE(pay.payment_count, 0) AS payment_count
        FROM subcontractors sc
        LEFT JOIN (
            SELECT sc_no, SUM(paid_amount) AS total_paid, COUNT(*) AS payment_count
            FROM payment_records
            WHERE project_id = ? AND (revoked_at IS NULL OR revoked_at = '')
            GROUP BY sc_no
        ) pay ON pay.sc_no = sc.sc_no
        WHERE sc.project_id = ? AND NOT sc.is_excluded
        ORDER BY sc.sc_no
    """, (project_id, project_id)).fetchall()

    # 總計
    totals = conn.execute("""
        SELECT SUM(paid_amount) AS total_paid,
               SUM(remainder_amount) AS total_remainder
        FROM payment_records
        WHERE project_id=? AND (revoked_at IS NULL OR revoked_at = '')
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


def list_master_field_suggestions(limit=300):
    """Master List 常見屋苑/地點、業主名稱（依使用次數排序）。"""
    limit = max(1, min(int(limit or 300), 500))
    conn = get_conn()

    def _top_values(column):
        rows = conn.execute(f"""
            SELECT TRIM({column}) AS val, COUNT(*) AS cnt
            FROM quotation_registry
            WHERE {column} IS NOT NULL AND TRIM({column}) != ''
            GROUP BY TRIM({column})
            ORDER BY cnt DESC, val COLLATE NOCASE
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]

    result = {
        'site_names': _top_values('site_name'),
        'client_names': _top_values('client_name'),
    }
    conn.close()
    return result


def upsert_quotation_registry(data):
    data = dict(data)
    data.setdefault('project_id', None)
    data.setdefault('person_code', None)
    data.setdefault('trade_scope', None)
    data.setdefault('trade_override', None)
    from master_trade_ref import resolve_trade_category
    data['trade_category'] = resolve_trade_category(
        data.get('trade_scope'), data.get('trade_override'), data.get('trade_category'),
    )
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
                awarded=:awarded, site_name=:site_name,
                trade_scope=:trade_scope, trade_override=:trade_override,
                trade_category=:trade_category,
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
                site_name, trade_scope, trade_override, trade_category,
                description, person_code, person_in_charge, client_name,
                quoted_amount, margin_pct, awarded_amount, contract_days,
                start_date, completion_date, subcon_type, subcon_company,
                subcon_amount, profit_amount, profit_pct, checklist_json,
                project_id, source_file, source_sheet, last_sync_at
            ) VALUES (
                :quotation_no, :source_year, :quote_date, :doc_type, :awarded,
                :site_name, :trade_scope, :trade_override, :trade_category,
                :description, :person_code, :person_in_charge, :client_name,
                :quoted_amount, :margin_pct, :awarded_amount, :contract_days,
                :start_date, :completion_date, :subcon_type, :subcon_company,
                :subcon_amount, :profit_amount, :profit_pct, :checklist_json,
                :project_id, :source_file, :source_sheet, :last_sync_at
            )
        """, data)
    conn.commit()
    conn.close()


def link_quotation_to_project(quotation_no, project_id, sync_project_code=True):
    """配對 Master List ↔ 工程項目（可多筆報價指向同一項目，如 N23 下多個 MP）"""
    qr = get_quotation_by_no(quotation_no)
    if not qr:
        raise ValueError(f'找不到報價記錄: {quotation_no}')
    conn = get_conn()
    conn.execute(
        "UPDATE quotation_registry SET project_id=? WHERE quotation_no=?",
        (project_id, quotation_no),
    )
    pic = qr.get('person_in_charge')
    if sync_project_code:
        proj = dict(conn.execute(
            "SELECT project_code, mp_contract_code, account_code, quotation_no, person_in_charge "
            "FROM projects WHERE id=?",
            (project_id,),
        ).fetchone())
        has_anchor = (proj.get('mp_contract_code') or proj.get('account_code') or '').strip()
        sets = []
        params = []
        if not (proj.get('quotation_no') or '').strip():
            sets.append('quotation_no=?')
            params.append(quotation_no)
        if pic and not (proj.get('person_in_charge') or '').strip():
            sets.extend(['person_in_charge=?', 'person_code=NULL'])
            params.append(pic)
        if not has_anchor:
            sets.append('project_code=?')
            params.append(quotation_no)
        if sets:
            conn.execute(
                f"UPDATE projects SET {', '.join(sets)} WHERE id=?",
                (*params, project_id),
            )
    else:
        proj = dict(conn.execute(
            "SELECT quotation_no, person_in_charge FROM projects WHERE id=?",
            (project_id,),
        ).fetchone())
        sets = []
        params = []
        if not (proj.get('quotation_no') or '').strip():
            sets.append('quotation_no=?')
            params.append(quotation_no)
        if pic and not (proj.get('person_in_charge') or '').strip():
            sets.extend(['person_in_charge=?', 'person_code=NULL'])
            params.append(pic)
        if sets:
            conn.execute(
                f"UPDATE projects SET {', '.join(sets)} WHERE id=?",
                (*params, project_id),
            )
    conn.commit()
    conn.close()


def count_quotations_for_project(project_id):
    conn = get_conn()
    n = conn.execute(
        "SELECT COUNT(*) AS c FROM quotation_registry WHERE project_id=?",
        (project_id,),
    ).fetchone()['c']
    conn.close()
    return n


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
        remaining = conn.execute(
            "SELECT COUNT(*) AS c FROM quotation_registry WHERE project_id=?",
            (project_id,),
        ).fetchone()['c']
        if remaining == 0:
            conn.execute("""
                UPDATE projects SET quotation_no=NULL, person_code=NULL, person_in_charge=NULL
                WHERE id=?
            """, (project_id,))
    conn.commit()
    conn.close()


def preview_auto_link_quotations(source_year=None):
    conn = get_conn()
    try:
        from master_link import auto_link_quotations
        return auto_link_quotations(conn, source_year=source_year, dry_run=True)
    finally:
        conn.close()


def run_auto_link_quotations(source_year=None):
    conn = get_conn()
    try:
        from master_link import auto_link_quotations
        return auto_link_quotations(conn, source_year=source_year, dry_run=False)
    finally:
        conn.close()


def suggest_project_for_quotation(quotation_no):
    conn = get_conn()
    try:
        from master_link import REASON_LABELS, find_project_for_quotation
        pid, reason = find_project_for_quotation(quotation_no, conn)
        if not pid:
            return None
        row = conn.execute(
            "SELECT id, project_code, project_name, project_name_zh FROM projects WHERE id=?",
            (pid,),
        ).fetchone()
        if not row:
            return None
        return {
            **dict(row),
            'reason': reason,
            'reason_label': REASON_LABELS.get(reason, reason),
        }
    finally:
        conn.close()


MASTER_EDITABLE_FIELDS = (
    'quote_date', 'doc_type', 'awarded', 'site_name',
    'trade_scope', 'trade_override', 'trade_category', 'description',
    'person_code', 'person_in_charge', 'client_name', 'quoted_amount', 'margin_pct',
    'awarded_amount', 'contract_days', 'start_date', 'completion_date',
    'subcon_type', 'subcon_company', 'subcon_amount', 'profit_amount', 'profit_pct',
    'checklist_json',
)


def _infer_quotation_source_year(quotation_no, quote_date=None):
    import re
    qno = str(quotation_no or '')
    m = re.search(r'/(\d{2})(?:/|$)', qno)
    if m:
        yy = int(m.group(1))
        return 2000 + yy if yy < 80 else 1900 + yy
    m = re.search(r'(20\d{2})', qno)
    if m:
        return int(m.group(1))
    if quote_date:
        try:
            return int(str(quote_date)[:4])
        except ValueError:
            pass
    return datetime.now().year


def _blank_master_registry_row(quotation_no, patch=None):
    rec = {
        'quotation_no': quotation_no,
        'source_year': _infer_quotation_source_year(quotation_no, (patch or {}).get('quote_date')),
        'source_file': 'UI',
        'source_sheet': None,
        'project_id': None,
        'quote_date': None,
        'doc_type': '報價',
        'awarded': None,
        'site_name': None,
        'trade_scope': None,
        'trade_override': None,
        'trade_category': None,
        'description': None,
        'person_code': None,
        'person_in_charge': None,
        'client_name': None,
        'quoted_amount': None,
        'margin_pct': None,
        'awarded_amount': None,
        'contract_days': None,
        'start_date': None,
        'completion_date': None,
        'subcon_type': None,
        'subcon_company': None,
        'subcon_amount': None,
        'profit_amount': None,
        'profit_pct': None,
        'checklist_json': None,
    }
    if patch:
        rec.update(patch)
    rec['source_year'] = rec.get('source_year') or _infer_quotation_source_year(
        quotation_no, rec.get('quote_date')
    )
    return rec


def create_quotation_registry(quotation_no, data):
    qno = (quotation_no or '').strip()
    if not qno:
        raise ValueError('請填寫報價編號')
    if get_quotation_by_no(qno):
        raise ValueError(f'報價編號已存在：{qno}')
    patch = {k: data[k] for k in MASTER_EDITABLE_FIELDS if k in data}
    if 'checklist_json' in patch:
        patch['checklist_json'] = _normalize_checklist_json(patch['checklist_json'])
    rec = _blank_master_registry_row(qno, patch)
    upsert_quotation_registry(rec)
    return get_quotation_by_no(qno)


def _format_quotation_seq_num(n):
    n = int(n)
    return str(n) if n >= 1000 else f'{n:03d}'


def suggest_next_quotation_no(doc_type, source_year=None, person_code=None):
    """下一個 MS/Q###/yy/code 或 MS/T###/yy/code（序號依同類型＋年份遞增；≥1000 為 4 位）。"""
    import re
    from master_ref import normalize_person_code

    if doc_type == '標書':
        letter = 'T'
    elif doc_type == '報價':
        letter = 'Q'
    else:
        return None

    year = int(source_year or datetime.now().year)
    yy = str(year % 100).zfill(2)
    pc = normalize_person_code(person_code) if person_code else None

    conn = get_conn()
    rows = conn.execute(
        "SELECT quotation_no FROM quotation_registry WHERE upper(quotation_no) GLOB ?",
        (f'MS/{letter}*',),
    ).fetchall()
    conn.close()

    pat = re.compile(rf'^MS/{letter}(\d+)/{yy}(?:/([a-z]{{2,4}}))?$', re.I)
    max_seq = 0
    for r in rows:
        q = (r['quotation_no'] or '').strip()
        m = pat.match(q)
        if m:
            max_seq = max(max_seq, int(m.group(1)))

    next_seq = max_seq + 1
    seq_str = _format_quotation_seq_num(next_seq)
    qno = f'MS/{letter}{seq_str}/{yy}'
    if pc:
        qno += f'/{pc}'
    return {
        'quotation_no': qno,
        'doc_type': doc_type,
        'letter': letter,
        'seq': next_seq,
        'seq_str': seq_str,
        'seq_digits': 4 if next_seq >= 1000 else 3,
        'year': year,
        'person_code': pc,
    }


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
        SELECT qr.*, p.project_code, p.project_name, p.account_code, p.mp_contract_code
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


def list_master_registry_years():
    """Master List 年份清單（輕量；供下拉選單）"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT source_year, COUNT(*) AS cnt
        FROM quotation_registry
        WHERE source_year IS NOT NULL
        GROUP BY source_year
        ORDER BY source_year DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


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
            key = n.lower()
            if not key:
                continue
            prev = staff_by_lower.get(key)
            if prev is None or (not prev.get('is_active') and s.get('is_active')):
                staff_by_lower[key] = s
        key = _staff_canonical_name(s).lower()
        if key:
            prev = staff_by_lower.get(key)
            if prev is None or (not prev.get('is_active') and s.get('is_active')):
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
            'pic_key': key,
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


def list_quotations_for_roster_person(person_label, limit=100, offset=0, sort_dir='desc'):
    """依項目負責人（Master List pic_key）列出報價／標書"""
    conn = get_conn()
    label = (person_label or '').strip()
    if not label:
        conn.close()
        return {'items': [], 'total': 0, 'person_name': None, 'pic_key': None}
    key = label.lower()
    by_person = _registry_by_person(conn)
    roster = next(
        (p for p in by_person if p['person_name'].lower() == key or p['pic_key'] == key),
        None,
    )
    pic_key = roster['pic_key'] if roster else key
    person_name = roster['person_name'] if roster else label
    filt = ' AND lower(trim(qr.person_in_charge)) = ?'
    params = [pic_key]
    order_sql = _registry_order_sql('quote_date', sort_dir)
    sql = f"""
        SELECT qr.*, p.project_code, p.project_name, p.account_code, p.mp_contract_code
        FROM quotation_registry qr
        LEFT JOIN projects p ON p.id = qr.project_id
        WHERE 1=1{filt}
        ORDER BY {order_sql} LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])
    rows = conn.execute(sql, params).fetchall()
    total = conn.execute(
        f'SELECT COUNT(*) FROM quotation_registry qr WHERE 1=1{filt}',
        params[:-2],
    ).fetchone()[0]
    conn.close()
    return {
        'items': [dict(r) for r in rows],
        'total': total,
        'person_name': person_name,
        'pic_key': pic_key,
    }


def list_staff_by_access_role(active_only=False, access_role='qs'):
    """staff_members 表依權限角色（如 QS 群組）"""
    role = (access_role or 'qs').strip().lower()
    if role not in STAFF_ACCESS_ROLES:
        raise ValueError(f'無效角色: {access_role}')
    conn = get_conn()
    sql = "SELECT * FROM staff_members WHERE access_role=?"
    params = [role]
    if active_only:
        sql += " AND is_active=1"
    sql += " ORDER BY name_en COLLATE NOCASE, name_zh COLLATE NOCASE"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d['person_name'] = d.get('name_en') or d.get('name_zh')
        d['in_staff_table'] = True
        out.append(d)
    return out


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
