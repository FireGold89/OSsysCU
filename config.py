"""路徑與部署設定（本機與 Zeabur 共用）"""
import os
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _resolve_data_dir():
    env = (os.environ.get('DATA_DIR') or '').strip()
    if env:
        return env
    # Docker / Zeabur 容器：固定用 Volume 掛載點
    if os.path.exists('/.dockerenv'):
        return '/data'
    return BASE_DIR


DATA_DIR = _resolve_data_dir()
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, 'uploads'), exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, 'qs_system.db')
UPLOAD_DIR = os.path.join(DATA_DIR, 'uploads')
FRONTEND_DIR = os.path.join(BASE_DIR, 'frontend')


def migrate_legacy_data():
    """若舊版誤寫入 /app，啟動時搬到 /data（僅在目標尚無資料時）"""
    if DATA_DIR == BASE_DIR:
        return

    legacy_db = os.path.join(BASE_DIR, 'qs_system.db')
    if os.path.exists(legacy_db) and not os.path.exists(DB_PATH):
        shutil.copy2(legacy_db, DB_PATH)
        print(f'[遷移] 資料庫: {legacy_db} → {DB_PATH}')

    legacy_uploads = os.path.join(BASE_DIR, 'uploads')
    if os.path.isdir(legacy_uploads):
        for name in os.listdir(legacy_uploads):
            src = os.path.join(legacy_uploads, name)
            dst = os.path.join(UPLOAD_DIR, name)
            if os.path.isfile(src) and not os.path.exists(dst):
                shutil.copy2(src, dst)
        print(f'[遷移] 已同步 uploads → {UPLOAD_DIR}')
