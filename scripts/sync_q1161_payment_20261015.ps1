# Sync MS/Q1161/25 from QS Excel (2026-10-15). Preserves IP-03 subcon_paid hold (995,000).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
$env:DATA_DIR = if ($env:DATA_DIR) { $env:DATA_DIR } else { "_data" }
$Excel = Join-Path $Root "Ref\Payment\2025\MS_Q1161_25 - Main contract Works Payment Status Table_r1_20261015.xlsx"
if (-not (Test-Path $Excel)) { throw "找不到: $Excel" }
python -c @"
import os
os.environ.setdefault('DATA_DIR', r'$env:DATA_DIR')
import database as db
from excel_importer_payment import sync_excel_data, import_site_ip_period
import openpyxl
from excel_importer_payment import safe_date

PID = 4
EXCEL = r'$Excel'
db.init_db()
sync_excel_data(EXCEL, project_id=PID)
conn = db.get_conn()
conn.execute(
    'UPDATE interim_payments SET subcon_paid=?, subcon_cert_date=? WHERE project_id=? AND ip_no=?',
    (995000.0, None, PID, 'IP-03'),
)
conn.commit()
conn.close()
db._recalc_and_save_ip_pcts(PID)
wb = openpyxl.load_workbook(EXCEL, data_only=True, read_only=True)
ws = wb['Summary']
start, end = safe_date(ws.cell(5, 7).value), safe_date(ws.cell(5, 8).value)
wb.close()
if start and end:
    p = db.get_project(PID) or {}
    p['site_period_text'] = f'{start} 至 {end}'
    db.update_project(PID, p)
import_site_ip_period(EXCEL, PID)
conn = db.get_conn()
conn.execute(
    'UPDATE interim_payments SET subcon_paid=?, subcon_cert_date=? WHERE project_id=? AND ip_no=?',
    (995000.0, None, PID, 'IP-03'),
)
conn.commit()
conn.close()
db._recalc_and_save_ip_pcts(PID)
print('[OK] Q1161 synced; IP-03 subcon_paid held at 995000')
"@
