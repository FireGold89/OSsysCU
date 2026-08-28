#!/usr/bin/env python3
"""上傳本機 uploads/ zip 至 Zeabur V2（admin 登入 + RESTORE_TOKEN）"""
import io
import os
import sys
import zipfile

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOADS_DIR = os.path.join(ROOT, 'uploads')
BASE_URL = os.environ.get('OSSYS_V2_URL', 'https://ossys-v2.zeabur.app').rstrip('/')


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


def _build_zip():
    if not os.path.isdir(UPLOADS_DIR):
        print(f'找不到 {UPLOADS_DIR}', file=sys.stderr)
        sys.exit(1)
    buf = io.BytesIO()
    count = 0
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(os.listdir(UPLOADS_DIR)):
            path = os.path.join(UPLOADS_DIR, name)
            if os.path.isfile(path):
                zf.write(path, arcname=name)
                count += 1
    if not count:
        print('uploads 資料夾為空，略過', file=sys.stderr)
        sys.exit(0)
    buf.seek(0)
    return buf, count


def main():
    _load_dotenv()
    token = os.environ.get('RESTORE_TOKEN', 'Restore8899')
    admin_user = os.environ.get('APP_ADMIN_USER', 'admin')
    admin_pass = os.environ.get('APP_ADMIN_PASSWORD', '')
    if not admin_pass:
        print('請在 .env 設定 APP_ADMIN_PASSWORD', file=sys.stderr)
        sys.exit(1)

    zbuf, count = _build_zip()
    print(f'目標 V2: {BASE_URL} · {count} 個檔案')

    session = requests.Session()
    login = session.post(
        f'{BASE_URL}/api/auth/login',
        json={'username': admin_user, 'password': admin_pass},
        timeout=60,
    ).json()
    if not login.get('success'):
        print(f'admin 登入失敗: {login.get("error")}', file=sys.stderr)
        sys.exit(1)

    r = session.post(
        f'{BASE_URL}/api/system/restore-uploads',
        headers={'X-Restore-Token': token},
        data={'token': token},
        files={'file': ('uploads.zip', zbuf, 'application/zip')},
        timeout=600,
    )
    print(r.status_code, r.text[:400])
    if not r.ok:
        sys.exit(1)
    after = session.get(f'{BASE_URL}/api/system/status', timeout=60).json().get('data') or {}
    print(f'upload_count={after.get("upload_count")}')


if __name__ == '__main__':
    main()
