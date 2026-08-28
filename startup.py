"""應用啟動初始化（本機 python app.py 與 Gunicorn 共用）"""
import os
import threading

import database as db
from config import BASE_DIR, DATA_DIR, DB_PATH, migrate_legacy_data

APP_VERSION = 'v2-20260828-baseline'

# V2 試用環境標識（Zeabur Variables 可覆寫 DEPLOYMENT_TIER=production 還原為無標籤）
DEPLOYMENT_TIER = (os.environ.get('DEPLOYMENT_TIER') or 'v2').strip().lower()
DEPLOYMENT_LABEL = 'V2 試用環境' if DEPLOYMENT_TIER == 'v2' else ''


def _preload_pdf_font():
    try:
        from qs_report_pdf import ensure_pdf_font, ensure_pdf_font_bold
        ensure_pdf_font()
        ensure_pdf_font_bold()
        print('[STARTUP] PDF 中文字型已就緒')
    except Exception as e:
        print(f'[STARTUP] PDF 字型預載警告: {e}')


def _sync_excel_background():
    """僅在空庫時自動匯入預設 Payment Excel；勿對所有項目覆寫同一檔案。"""
    excel_name = 'MS_Q1241_24 - Main contract Works Payment Status Table - R5.xlsx'
    excel_path = os.path.join(BASE_DIR, excel_name)
    if not os.path.exists(excel_path):
        return
    projects = db.get_all_projects()
    if not projects:
        print('\n[初始化] 偵測到Excel文件，自動匯入...')
        from excel_importer import import_excel
        try:
            import_excel(excel_path)
            print('[初始化] Excel匯入完成!')
        except Exception as e:
            print(f'[初始化] Excel匯入警告: {e}')


def _sync_sc_contract_background():
    """DB 無資料時自動從 Ref Excel 同步分判合約編號"""
    try:
        if db.sc_contract_registry_count() > 0:
            return
        from sc_contract_importer import sync_from_ref
        r = sync_from_ref()
        if r.get('ok'):
            print(f"[STARTUP] sc_contract_registry synced: {r.get('rows_read')} rows")
        else:
            print(f"[STARTUP] sc_contract_registry skip: {r.get('error')}")
    except Exception as e:
        print(f'[STARTUP] sc_contract_registry warn: {e}')


def _sync_engineering_categories_background():
    """DB 無資料時自動從 R1 Excel 同步工程標準分類"""
    try:
        if db.engineering_category_count() > 0:
            return
        r = db.sync_engineering_categories()
        if r.get('ok'):
            print(f"[STARTUP] engineering_categories synced: {r.get('rows_read')} rows")
            ar = db.auto_classify_projects(only_empty=True, dry_run=False)
            print(f"[STARTUP] projects auto-classified: {ar.get('updated')} updated, "
                  f"{ar.get('unmatched')} unmatched")
    except Exception as e:
        print(f'[STARTUP] engineering_categories warn: {e}')


def _sync_master_trade_categories_background():
    """DB 無資料時自動從 Master List Excel「分類清單」同步工作範疇"""
    try:
        if db.master_trade_category_count() > 0:
            return
        r = db.sync_master_trade_categories()
        if r.get('ok'):
            print(f"[STARTUP] master_trade_categories synced: {r.get('rows_read')} rows")
    except Exception as e:
        print(f'[STARTUP] master_trade_categories warn: {e}')


def run():
    migrate_legacy_data()
    print(f'[STARTUP] version={APP_VERSION} tier={DEPLOYMENT_TIER or "production"}')
    print(f'[STARTUP] DATA_DIR={DATA_DIR}')
    print(f'[STARTUP] DB_PATH={DB_PATH} (exists={os.path.exists(DB_PATH)})')
    if os.path.exists(DB_PATH):
        print(f'[STARTUP] DB size={os.path.getsize(DB_PATH)} bytes')

    db.init_db()

    try:
        import auth
        if auth.is_enabled():
            users = auth.load_users()
            print(f'[STARTUP] auth=enabled users={len(users)}')
        else:
            print('[STARTUP] auth=disabled (no APP_*_PASSWORD; set Zeabur Variables in prod)')
    except Exception as e:
        print(f'[STARTUP] auth config warning: {e}')

    projects = db.get_all_projects()
    print(f'[STARTUP] projects={len(projects)}')
    threading.Thread(
        target=_sync_excel_background,
        daemon=True,
        name='excel-sync',
    ).start()
    threading.Thread(
        target=_preload_pdf_font,
        daemon=True,
        name='pdf-font-preload',
    ).start()
    threading.Thread(
        target=_sync_sc_contract_background,
        daemon=True,
        name='sc-contract-sync',
    ).start()
    threading.Thread(
        target=_sync_engineering_categories_background,
        daemon=True,
        name='eng-category-sync',
    ).start()
    threading.Thread(
        target=_sync_master_trade_categories_background,
        daemon=True,
        name='master-trade-sync',
    ).start()
