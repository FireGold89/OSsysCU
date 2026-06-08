"""路徑與部署設定（本機與 Zeabur 共用）"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get('DATA_DIR', BASE_DIR)

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(os.path.join(DATA_DIR, 'uploads'), exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, 'qs_system.db')
UPLOAD_DIR = os.path.join(DATA_DIR, 'uploads')
FRONTEND_DIR = os.path.join(BASE_DIR, 'frontend')
