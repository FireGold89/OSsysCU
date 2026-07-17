"""打包本機 uploads/ 為 zip 上傳至 Zeabur（需 RESTORE_TOKEN）"""
import io
import os
import sys
import zipfile

import requests

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(REPO, '.env')
UPLOADS_DIR = os.path.join(REPO, 'uploads')
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


def build_zip():
    if not os.path.isdir(UPLOADS_DIR):
        print(f'ERROR: 找不到 {UPLOADS_DIR}')
        sys.exit(1)
    buf = io.BytesIO()
    count = 0
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(os.listdir(UPLOADS_DIR)):
            path = os.path.join(UPLOADS_DIR, name)
            if not os.path.isfile(path):
                continue
            zf.write(path, arcname=name)
            count += 1
    if not count:
        print('ERROR: uploads 資料夾為空')
        sys.exit(1)
    buf.seek(0)
    return buf, count


def main():
    load_env()
    token = os.environ.get('RESTORE_TOKEN', '').strip()
    if not token:
        print('ERROR: 請設定 RESTORE_TOKEN（環境變數或 .env）')
        sys.exit(1)

    zbuf, count = build_zip()
    size = zbuf.getbuffer().nbytes
    print(f'打包 {count} 個檔案 ({size:,} bytes) → {PROD_URL} ...')
    r = requests.post(
        f'{PROD_URL}/api/system/restore-uploads',
        headers={'X-Restore-Token': token},
        data={'token': token},
        files={'file': ('uploads.zip', zbuf, 'application/zip')},
        timeout=300,
    )
    print(r.status_code, r.text)
    if not r.ok:
        sys.exit(1)
    print('uploads 同步完成')


if __name__ == '__main__':
    main()
