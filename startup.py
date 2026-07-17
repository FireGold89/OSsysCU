"""應用啟動初始化（本機 python app.py 與 Gunicorn 共用）"""
import os
import threading

import database as db
from config import BASE_DIR, DATA_DIR, DB_PATH, migrate_legacy_data

APP_VERSION = '2026-07-17-master-year-filter'


def _preload_pdf_font():
    try:
        from qs_report_pdf import ensure_pdf_font
        ensure_pdf_font()
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


def run():
    migrate_legacy_data()
    print(f'[STARTUP] version={APP_VERSION}')
    print(f'[STARTUP] DATA_DIR={DATA_DIR}')
    print(f'[STARTUP] DB_PATH={DB_PATH} (exists={os.path.exists(DB_PATH)})')
    if os.path.exists(DB_PATH):
        print(f'[STARTUP] DB size={os.path.getsize(DB_PATH)} bytes')

    db.init_db()

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
