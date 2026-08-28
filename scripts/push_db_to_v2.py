#!/usr/bin/env python3
"""上傳本機 qs_system.db 至 Zeabur V2（admin 登入 + RESTORE_TOKEN）"""
import os
import sys

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(ROOT, 'qs_system.db')
BASE_URL = os.environ.get('OSSYS_V2_URL', 'https://ossys-v2.zeabur.app').rstrip('/')


def _load_dotenv():
    for name in ('.env', 'v2.env'):
        path = os.path.join(ROOT, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, val = line.split('=', 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = val


def main():
    _load_dotenv()
    db_path = os.environ.get('DB_PATH', DEFAULT_DB)
    admin_user = os.environ.get('APP_ADMIN_USER', 'admin')
    admin_pass = os.environ.get('APP_ADMIN_PASSWORD', '')
    restore_token = os.environ.get('RESTORE_TOKEN', 'Restore8899')

    if not os.path.isfile(db_path):
        print(f'找不到資料庫: {db_path}', file=sys.stderr)
        sys.exit(1)
    if not admin_pass:
        print('請在 .env 設定 APP_ADMIN_PASSWORD', file=sys.stderr)
        sys.exit(1)

    size_mb = os.path.getsize(db_path) / (1024 * 1024)
    print(f'目標 V2: {BASE_URL}')
    print(f'本機 DB: {db_path} ({size_mb:.2f} MB)')

    session = requests.Session()
    before = session.get(f'{BASE_URL}/api/system/status', timeout=60).json().get('data') or {}
    print(f'還原前: projects={before.get("project_count")} payments={before.get("payment_count")} '
          f'version={before.get("app_version")} tier={before.get("deployment_tier")}')

    login_r = session.post(
        f'{BASE_URL}/api/auth/login',
        json={'username': admin_user, 'password': admin_pass},
        timeout=60,
    )
    login_body = login_r.json()
    if not login_body.get('success'):
        print(f'admin 登入失敗: {login_body.get("error")}', file=sys.stderr)
        sys.exit(1)
    print(f'admin 登入成功: {login_body.get("data", {}).get("username")}')

    headers = {'X-Restore-Token': restore_token}
    with open(db_path, 'rb') as fh:
        up = session.post(
            f'{BASE_URL}/api/system/restore-db',
            headers=headers,
            files={'file': ('qs_system.db', fh, 'application/octet-stream')},
            timeout=600,
        )
    try:
        result = up.json()
    except Exception:
        print(f'還原 HTTP {up.status_code}: {up.text[:300]}', file=sys.stderr)
        sys.exit(1)

    if not result.get('success'):
        print(f'還原失敗: {result.get("error")}', file=sys.stderr)
        sys.exit(1)

    data = result.get('data') or {}
    print(f'還原成功: project_count={data.get("project_count")} message={data.get("message")}')

    after = session.get(f'{BASE_URL}/api/system/status', timeout=60).json().get('data') or {}
    print(f'還原後: projects={after.get("project_count")} payments={after.get("payment_count")} '
          f'db_mb={round((after.get("db_size_bytes") or 0) / 1048576, 2)}')


if __name__ == '__main__':
    main()
