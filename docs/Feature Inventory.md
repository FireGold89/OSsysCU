# Feature Inventory

> 功能清單依 **後端 API + 前端 JS + DB 表** 三軸對照。  
> 標註：`[Code]` = 有直接實作證據 · `[Inferred]` = 由命名／文件推論

---

## 功能矩陣

| 功能 | API 前綴 | 前端 JS | 主要 DB 表 | 狀態 |
|------|----------|---------|------------|------|
| 工程項目 | `/api/projects` | `projects.js` | `projects`, `project_documents`, `project_mp_contracts` | [Code] CRUD + Cover Page |
| 公司 Summary | `/api/company-summary` | `projects.js` | `projects` | [Code] |
| Master List | `/api/master/*` | `master_list.js` | `quotation_registry`, `master_*` | [Code] |
| 工作範疇分類 | `/api/master/trade-categories` | `master_trade.js` | `master_trade_categories` | [Code] |
| 分判 MS/C 編號 | `/api/sc-contract-registry` | `sc_contract_registry.js` | `sc_contract_registry` | [Code] |
| 工程標準分類 | `/api/engineering-categories` | `projects.js` | `engineering_categories` | [Code] |
| 分判判項 | `/api/subcontractors` | `payments.js`, `projects.js` (SC) | `subcontractors`, `sc_documents` | [Code] |
| 分判付款 | `/api/payments` | `payments.js` | `payment_records` | [Code] |
| 中期糧款計算書 | `/api/payments/interim-cert/*` | `payments.js` | `payment_records.interim_cert_json` | [Code] PDF/XLSX/DOCX |
| 分判 VO/扣款 | `/api/sc-vo-*` | `sc_vo_reg.js` | `sc_vo_records`, `sc_vo_template_catalog` | [Code] |
| 地盤糧期 IP | `/api/interim-payments` | `ip_period.js` | `interim_payments`, `interim_payment_sc_lines` | [Code] |
| 糧期核對 | `/api/projects/.../ip-reconciliation` | `ip_reconcile.js` | 跨表唯讀 | [Code] 不寫回 |
| 主合約 FAC | `/api/projects/.../main-con-fac` | `main_con_fac.js` | `projects` FAC 欄 | [Code] 表單 |
| 分判 FAC | `/api/projects/.../sc-fac` | `sc_fac.js` | 匯總自判項/VO/付款 | [Code] PDF/DOCX |
| OCR | `/api/ocr` | `ocr.js` | `ocr_extractions` | [Code] |
| 財務報表 | `/api/reports` | `reports.js` | 匯總查詢 | [Code] JSON + QS PDF |
| ISO 文件 | `/api/projects/.../iso-*` | `iso_docs.js` | `iso_document_files` | [Code] |
| 負責人名單 | `/api/staff` | `staff.js` | `staff_members` | [Code] 無權限 enforce |
| 系統設定 | `/api/settings` | `main.js` (Settings) | `settings` | [Code] |
| Excel 匯入 | `/api/import/*` | `main.js` (importModal) | 多表 | [Code] |
| 系統還原 | `/api/system/restore-*` | — | — | [Code] Token 保護 |
| BOQ 模組 | — | — | — | **不存在** [Code] |
| 分判商主檔 | — | — | — | **不存在** [Code] |
| 登入 / Audit | — | — | — | **不存在** [Code] |

---

## 各模組細節

### 工程項目 `[Code]`

- CRUD：`app.py` → `list_projects`, `create_project`, `update_project`, `delete_project`
- Cover Page：`GET /api/projects/<id>/cover-page` → `database.get_cover_page()`
- 項目金額結算（Cover 第 5 頁）：`project_cover.compute_settlement()`
- Summary 匯入：`POST /api/import/summary`, `/api/import/summary/sync` → `summary_importer.py`
- 註冊及更新頁：`App.navigate('project-settlement')` → `Projects.loadSettlement()`（`main.js`）

### Master List `[Code]`

- 報價 CRUD：`/api/master/quotations`, `/api/master/item`
- 財務子表：`/api/master/item/.../finance` → `master_finance.py`
- 自動配對：`/api/master/auto-link` → `master_link.auto_link_quotations()`
- Excel 同步：`/api/master/preview`, `/api/master/sync` → `master_list_importer.py`
- 欄位建議：`/api/master/field-suggestions` → `database.list_master_field_suggestions()`

### 分判付款 `[Code]`

- 付款類型：`payment_records.payment_type` — `normal` 或 `interim_cert`
- 發票重複檢查：`GET /api/projects/<id>/payments/check-invoice`
- 判項類型：M / SC / O（`frontend/js/main.js` → `refNoType()`）

### 分判 VO/扣款 `[Code]`

- 記錄類型：`sc_vo_records.record_type` — `'vo'` | `'deduction'`
- 模板目錄：`sc_vo_template_catalog`；種子 `sc_vo_templates.py`
- 附件上傳：`POST /api/sc-vo-records/<id>/upload`
- 套用鎖定：`sc_vo_records.applied_payment_id` → 關聯 `payment_records`

### 地盤糧期 `[Code]`

- Excel 匯入：`excel_importer_payment.import_site_ip_period()`
- 累計 %：`database.calc_ip_cumulative_pcts()`
- SC 矩陣：`interim_payment_sc_lines`
- 附件：收據、IP Cert → `interim_payments` 附件欄

### 報表 `[Code]`

- 項目摘要 JSON：`GET /api/reports/summary/<id>` → `database.get_project_summary()`
- QS PDF：`GET /api/reports/boss-pdf/<id>` → `qs_report_pdf.generate_boss_qs_report()`
- 關注事項：規則引擎 `qs_report_pdf._attention_items()`（非 AI）

### OCR `[Code]`

- 引擎列表：`GET /api/ocr/engines`
- 上傳：`POST /api/ocr/upload` → `ocr_processor.process_pdf()`
- 判項建議：`POST /api/projects/<id>/ocr/suggest-sc`

---

## 啟動時背景同步 `[Code]`

僅在 DB 空或計數為 0 時觸發（各函數內有 guard）：

| 任務 | 函數 | 來源 |
|------|------|------|
| Payment Excel | `_sync_excel_background()` | repo 根目錄預設 xlsx |
| MS/C 合約 | `_sync_sc_contract_background()` | `Ref/` Excel |
| 工程分類 | `_sync_engineering_categories_background()` | R1 Excel |
| 工作範疇 | `_sync_master_trade_categories_background()` | Master List「分類清單」 |

**證據**：`startup.py`

---

## 明確不存在 `[Code]`

| 功能 | 查證方式 |
|------|----------|
| BOQ 表 / API | `database.py` 無 CREATE TABLE boq*；`app.py` 無 /boq 路由 |
| 使用者登入 | 無 login route、無 Flask session、無 password_hash 欄 |
| Audit log 表 | `database.py` 無 audit 相關表 |
| 分判商公司主檔 | 無 `subcontractor_companies` 表；公司名存於 `subcontractors` 文字欄 |
