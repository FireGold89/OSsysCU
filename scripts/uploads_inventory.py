#!/usr/bin/env python3
"""列出 uploads 分類統計（本機或伺服器 DATA_DIR）。用法：python scripts/uploads_inventory.py"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from config import UPLOAD_DIR
from upload_naming import GENERATED_EXPORTS, upload_storage_summary


def main():
    base = UPLOAD_DIR
    if len(sys.argv) > 1:
        base = sys.argv[1]
    print(f'UPLOAD_DIR={base}\n')
    rows = upload_storage_summary(base)
    for r in rows:
        if not r['files']:
            continue
        kb = r['bytes'] / 1024
        print(f"[{r['id']}] {r['label']} — {r['files']} 檔 · {kb:.1f} KB")
        print(f"    功能：{r['feature']}")
        print(f"    路徑：{r['path_hint']}\n")
    print('— 以下功能產生 PDF/Word 但 **不寫入 uploads**（僅下載／預覽）—')
    for g in GENERATED_EXPORTS:
        print(f"  · {g['label']}：{g['feature']}")


if __name__ == '__main__':
    main()
