"""
sc_contract_importer.py — 分判工程合約編號 Ref Excel → sc_contract_registry

獨立執行:
  python sc_contract_importer.py sync
  python sc_contract_importer.py status
"""
from __future__ import annotations

import os
import sys

import database as db
from sc_contract_ref import _find_ref_workbook, _load_rows_from_workbook, invalidate_cache


def sync_from_ref(path: str | None = None) -> dict:
    path = path or _find_ref_workbook()
    if not path or not os.path.isfile(path):
        return {'ok': False, 'error': '找不到 Ref/分判工程合約編號 *.xlsx'}
    rows = _load_rows_from_workbook(path)
    if not rows:
        return {'ok': False, 'error': 'Excel 無有效 MS/C 資料列', 'source_file': path}
    result = db.sync_sc_contract_registry(rows, source_file=path)
    invalidate_cache()
    result['ok'] = True
    return result


def main():
    cmd = (sys.argv[1] if len(sys.argv) > 1 else 'sync').lower()
    if cmd == 'status':
        print(db.get_sc_contract_registry_status())
        return
    r = sync_from_ref()
    print(r)


if __name__ == '__main__':
    main()
