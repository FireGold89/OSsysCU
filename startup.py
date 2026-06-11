"""應用啟動初始化（本機 python app.py 與 Gunicorn 共用）"""
import os

import database as db
from config import BASE_DIR, DATA_DIR, DB_PATH, migrate_legacy_data


def run():
    migrate_legacy_data()
    print(f'[STARTUP] DATA_DIR={DATA_DIR}')
    print(f'[STARTUP] DB_PATH={DB_PATH} (exists={os.path.exists(DB_PATH)})')
    if os.path.exists(DB_PATH):
        print(f'[STARTUP] DB size={os.path.getsize(DB_PATH)} bytes')

    db.init_db()

    projects = db.get_all_projects()
    print(f'[STARTUP] projects={len(projects)}')
    excel_name = 'MS_Q1241_24 - Main contract Works Payment Status Table - R4.xlsx'
    excel_path = os.path.join(BASE_DIR, excel_name)

    if not projects:
        if os.path.exists(excel_path):
            print('\n[初始化] 偵測到Excel文件，自動匯入...')
            from excel_importer import import_excel
            try:
                import_excel(excel_path)
                print('[初始化] Excel匯入完成!')
            except Exception as e:
                print(f'[初始化] Excel匯入警告: {e}')
    elif os.path.exists(excel_path):
        from excel_importer import sync_contract_amount_from_excel, sync_excel_data
        for p in projects:
            try:
                sync_excel_data(excel_path, p['id'])
            except Exception as e:
                print(f'[初始化] Excel 同步警告: {e}')
