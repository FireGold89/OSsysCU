#!/usr/bin/env python3
"""上傳本機 qs_system.db 至 Zeabur 生產（需 RESTORE_TOKEN；舊版另需 admin 登入）"""
import json
import os
import sys

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(ROOT, 'qs_system.db')
BASE_URL = os.environ.get('OSSYS_URL', 'https://ossys.zeabur.app').rstrip('/')


def _load_dotenv():
    path = os.path.join(ROOT, '.env')
    if not os.path.isfile(path):
        return
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


def _status(session):
    r = session.get(f'{BASE_URL}/api/system/status', timeout=60)
    r.raise_for_status()
    data = r.json().get('data') or {}
    return data


def main():
    _load_dotenv()
    db_path = os.environ.get('DB_PATH', DEFAULT_DB)
    admin_user = os.environ.get('APP_ADMIN_USER', 'admin')
    admin_pass = os.environ.get('APP_ADMIN_PASSWORD', '')
    restore_token = os.environ.get('RESTORE_TOKEN', '')

    if not os.path.isfile(db_path):
        print(f'找不到資料庫: {db_path}', file=sys.stderr)
        sys.exit(1)
    if not restore_token:
        print('請在 .env 或環境變數設定 RESTORE_TOKEN（與 Zeabur Variables 相同）', file=sys.stderr)
        sys.exit(1)

    size_mb = os.path.getsize(db_path) / (1024 * 1024)
    print(f'目標: {BASE_URL}')
    print(f'本機 DB: {db_path} ({size_mb:.2f} MB)')

    session = requests.Session()
    before = _status(session)
    print(f'還原前: projects={before.get("project_count")} payments={before.get("payment_count")} '
          f'version={before.get("app_version")}')

    headers = {'X-Restore-Token': restore_token}
    with open(db_path, 'rb') as fh:
        up = session.post(
            f'{BASE_URL}/api/system/restore-db',
            headers=headers,
            files={'file': ('qs_system.db', fh, 'application/octet-stream')},
            timeout=300,
        )
    result = up.json()
    if not result.get('success') and result.get('error') == '請先登入' and admin_pass:
        login_r = session.post(
            f'{BASE_URL}/api/auth/login',
            json={'username': admin_user, 'password': admin_pass},
            timeout=60,
        )
        body = login_r.json()
        if not body.get('success'):
            print(f'admin 登入失敗: {body.get("error")}', file=sys.stderr)
            sys.exit(1)
        print(f'admin 登入成功: {body.get("data", {}).get("username")}')
        with open(db_path, 'rb') as fh:
            up = session.post(
                f'{BASE_URL}/api/system/restore-db',
                headers=headers,
                files={'file': ('qs_system.db', fh, 'application/octet-stream')},
                timeout=300,
            )
        result = up.json()
    elif not result.get('success') and result.get('error') == '請先登入':
        print('伺服器尚未更新：restore-db 需 admin 登入。請部署含 auth token  bypass 的版本，或设 APP_ADMIN_PASSWORD', file=sys.stderr)
        sys.exit(1)

    if not result.get('success'):
        print(f'還原失敗: {result.get("error")}', file=sys.stderr)
        sys.exit(1)

    data = result.get('data') or {}
    print(f'還原成功: {data.get("message")} project_count={data.get("project_count")}')

    after = _status(session)
    print(f'還原後: projects={after.get("project_count")} payments={after.get("payment_count")} '
          f'db_size={after.get("db_size_bytes")}')


if __name__ == '__main__':
    main()
