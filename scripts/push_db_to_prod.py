"""上傳本機 qs_system.db 至 Zeabur 生產環境（需 .env 的 RESTORE_TOKEN）"""
import os
import sys

import requests

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(REPO, '.env')
DB_PATH = os.path.join(REPO, 'qs_system.db')
PROD_URL = os.environ.get('PROD_URL', 'https://ossys.zeabur.app')


def load_env():
    if not os.path.isfile(ENV_PATH):
        return
    with open(ENV_PATH, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, val = line.split('=', 1)
            val = val.strip().strip('"').strip("'")
            os.environ.setdefault(key.strip(), val)


def main():
    load_env()
    token = os.environ.get('RESTORE_TOKEN', '').strip()
    if not token:
        print('ERROR: 請在 .env 設定 RESTORE_TOKEN')
        sys.exit(1)
    if not os.path.isfile(DB_PATH):
        print(f'ERROR: 找不到 {DB_PATH}')
        sys.exit(1)

    size = os.path.getsize(DB_PATH)
    print(f'上傳 {DB_PATH} ({size:,} bytes) → {PROD_URL} ...')
    with open(DB_PATH, 'rb') as f:
        r = requests.post(
            f'{PROD_URL}/api/system/restore-db',
            headers={'X-Restore-Token': token},
            data={'token': token},
            files={'file': ('qs_system.db', f, 'application/octet-stream')},
            timeout=180,
        )
    print(r.status_code, r.text)
    if not r.ok:
        sys.exit(1)
    print('資料庫還原完成')


if __name__ == '__main__':
    main()
