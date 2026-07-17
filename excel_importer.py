"""
excel_importer.py — 相容入口（轉呼叫 excel_importer_payment）

地盤 Payment Status Table 匯入請用:
  python excel_importer_payment.py

公司 Master List 匯入請用:
  python master_list_importer.py
"""
from excel_importer_payment import (  # noqa: F401
    import_excel,
    sync_excel_data,
    import_site_ip_period,
    read_contract_amount,
    read_labour_allocation,
    sync_contract_amount_from_excel,
    sync_labour_allocation_from_excel,
)
