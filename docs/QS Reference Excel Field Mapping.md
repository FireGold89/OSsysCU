# QS 參考 Excel 逐欄對照

> 四份 QS 主管參考檔與 OSsysCU 資料庫欄位對照。  
> 總覽見 [QS Reference Excel Overview.md](./QS%20Reference%20Excel%20Overview.md)。

**圖例：** ✅ 已支援 · ⚠️ 部分／需填／衍生 · ❌ 未有

**Code 入口：**

- Payment：`excel_importer_payment.py`
- Master List：`master_list_importer.py`、`master_finance.py`
- Cover／FAC：`project_cover.py`、`main_fac.py`、`sc_fac.py`

---

## 表 1：Payment Status（地盤付款表）

**參考檔：** `Ref/From QS/MS_Q1059_25 - Main contract Works Payment Status Table R6.xlsx`

### Sheet A — Summary（糧期 + 項目摘要）

| Excel 位置／表頭 | DB 表.欄位 | 狀態 |
|------------------|------------|------|
| 首列 `(Project No. MS_Q1059_25)` | `projects.project_code` | ✅ |
| 項目英文名（MTR 長字串等） | `projects.project_name_en` | ✅ |
| `合約金額`／`建造金額`／`承建金額`／Contract | `projects.contract_amount` | ✅ |
| `總承建`／Main Contractor | `projects.main_contractor` | ✅ |
| 工期 B,C 欄文字 | `projects.site_period_text` | ✅ |
| `(C1)` 人工／調撥 | `projects.labour_allocation` | ✅ |
| 表尾 `總收入` | `projects.ip_total_income` | ✅ |
| 表尾 `總支出` | `projects.ip_total_expenditure` | ✅ |
| 表尾 `墊支` | `projects.ip_advance` | ✅ |
| IP-01… 序號 (A) | `interim_payments.ip_no` | ✅ |
| Applied Date (B) | `interim_payments.applied_date` | ✅ |
| Application Amount (C) | `interim_payments.application_amount` | ✅ |
| Certified Income (E) | `interim_payments.certified_income` | ✅ |
| Certificate Date (G) | `interim_payments.certificate_date` | ✅ |
| 各 SC 欄（表頭 sc_no） | `interim_payment_sc_lines` | ✅ |
| SC 合計／% | `interim_payments.subcon_paid`／`subcon_paid_pct` | ✅ |
| SC 表頭上一行工種 | `subcontractors.trade_label` | ✅ |
| 收票／支票欄（若有） | `interim_payments.receipt_*` | ⚠️ 視 Excel 版型 |

### Sheet B — 代支工程, 物料（付款明細）

| Excel 表頭 | DB 表.欄位 | 狀態 |
|------------|------------|------|
| No. | `payment_records.seq_no` | ✅ |
| Link | — | ❌ 不匯入 |
| Invoice Date | `payment_records.invoice_date` | ✅ |
| Invoice No. | `payment_records.invoice_no` | ✅ |
| Quotation No. | `payment_records.quotation_no` | ✅ |
| Sub-contractors' No | `payment_records.sc_no` | ✅ |
| Company Name | `payment_records.company_name_en` | ✅ |
| Company Name (in Chinese) | `payment_records.company_name_zh` | ✅ |
| Description | `payment_records.description` | ✅ |
| Contract Amount (HK$) | `payment_records.contract_amount` | ✅ |
| Paid Amount (HK$) | `payment_records.paid_amount` | ✅ |
| Remainder Amount (HK$) | `payment_records.remainder_amount` | ✅ |
| OA日期 | — | ⚠️ 付款表此欄未 map |
| OA編號 | `payment_records.oa_no`（OA狀→`oa_ref`） | ⚠️ 部分 |
| MC IP-No. | `payment_records.mc_ip_no` | ✅ |
| B/C to sub-contractor | `payment_records.bc_to_sub` | ✅ |
| Sub-IP No. | `payment_records.sub_ip_no` | ✅ |
| Reamrk | `payment_records.remark` | ✅ |

### Sheet C — Project Summary（分判匯總）

| 欄索引 | Excel | DB 表.欄位 | 狀態 |
|--------|-------|------------|------|
| B | Sub No. | `subcontractors.sc_no` | ✅ |
| C | Quotation | `subcontractors.quotation_no` | ✅ |
| D/E | 公司名中英 | `company_name_en`／`company_name_zh` | ✅ |
| F | Description | `subcontractors.description` | ✅ |
| G | `*` | `subcontractors.is_excluded` | ✅ |
| H | Contract Sum | `subcontractors.contract_sum` | ✅ |
| I | VO | `subcontractors.vo_amount` | ✅ |
| J | Revised | `subcontractors.contract_amount` | ✅ |
| K | Payment Note | `subcontractors.payment_note` | ✅ |
| L–O | OA 狀／編／日期 | `oa_status`／`oa_ref`／`oa_no`／`oa_date` | ✅ |
| P | Quotation Saved | `subcontractors.quotation_saved` | ✅ |

### Sheet D/E — 東寶Budget、東寶扣數

| 內容 | 狀態 |
|------|------|
| 東寶專項預算期數 | ❌ 無專表 |
| Contra Charge Summary | ⚠️ 部分在 `sc_vo_records`（deduction），無東寶專屬 view |

---

## 表 2：Master List（2025 報價合約主檔）

**參考檔：** `Ref/2025 Quotation & Contract number.xlsx`

### Sheet — 分類清單

| Excel 欄 | 系統對應 | 狀態 |
|----------|----------|------|
| 工程類別分類 | `master_trade_categories` 參考 | ⚠️ |
| 報價/標書 | — | ❌ |
| 項目負責人 | `staff_members` 參照 | ⚠️ |
| 外判與否 | — | ❌ |

### Sheet — 報價（3086 行 × 37 欄）

| Excel 欄 | 表頭 | DB 表.欄位 | Phase | 狀態 |
|----------|------|------------|-------|------|
| A | 日期 | `quotation_registry.quote_date` | 1 | ✅ |
| B–E | 報價編號四段 | `quotation_no` + `person_code` | 1 | ✅ |
| F | 中標 | `quotation_registry.awarded` | 1 | ✅ |
| G | 報價/標書 | `quotation_registry.doc_type` | 1 | ✅ |
| H | 屋苑/地點 | `quotation_registry.site_name` | 1 | ✅ |
| I | 工作範疇 | `quotation_registry.trade_scope` | 1 | ✅ |
| J | 工作範疇(重填) | `trade_override` → `trade_category` | 1 | ✅ |
| K | 內容 | `quotation_registry.description` | 1 | ✅ |
| L | 負責人 | `person_in_charge` + `person_code` | 1 | ✅ |
| M | 業主名稱 | `quotation_registry.client_name` | 1 | ✅ |
| N | 金額-報業主/大判 | `quoted_amount` | 1 | ✅ |
| O | 投標利潤率 % | `margin_pct` | 1 | ✅ |
| P | 中標金額 | `awarded_amount` | 1 | ✅ |
| Q–S | 已填妥會簽表 | `checklist_json` | 1 | ✅ |
| T | 合約期/工期(天) | `contract_days` | 1 | ✅ |
| U | 開工日期 | `start_date` | 1 | ✅ |
| V | 實際完工日期 | `completion_date` | 1 | ✅ |
| W | 外判與否 | `subcon_type` | 1 | ✅ |
| X | 主要分判商/供應商 | `subcon_company` + `master_qs_subcon_lines` | 1/2 | ✅ |
| Y | 分判金額 | `subcon_amount` | 1/2 | ✅ |
| Z | 利潤$ | `profit_amount` | 1 | ✅ |
| AA | 利潤% | `profit_pct` | 1 | ✅ |
| AB | 出發票日期 | `master_client_invoices.invoice_date` | 2 | ✅ |
| AC | 美博發票編號 | `master_client_invoices.invoice_no` | 2 | ✅ |
| AD | 收票日期 | `master_client_invoices.receipt_date` | 2 | ✅ |
| AE | 支票號碼,銀行,日期 | `master_cheque_records.*` | 2 | ✅ |
| AG | 外判公司(Admin) | `master_subcon_payments.subcon_company` | 2 | ✅ |
| AH | 外判金額(Admin) | `master_subcon_payments.subcon_amount` | 2 | ✅ |
| AI | 上憑單日期 | `master_subcon_payments.voucher_date` | 2 | ✅ |
| — | 連結項目 | `quotation_registry.project_id` | — | ⚠️ 配對後寫入 |

**`master_list_importer.SYNC_FIELDS`（Phase 1 diff 比對）：**

`quote_date`, `doc_type`, `awarded`, `site_name`, `trade_category`, `description`, `person_code`, `person_in_charge`, `client_name`, `quoted_amount`, `margin_pct`, `awarded_amount`, `contract_days`, `start_date`, `completion_date`, `subcon_type`, `subcon_company`, `subcon_amount`, `profit_amount`, `profit_pct`

---

## 表 3：Final Account Status List（N 項目結算總表）

**參考檔：** `Ref/From QS/N Project - Final Account Status List - r2.xlsx`（43 項 × 49 欄）

### 左側 — 項目維度（19 欄）

| Excel 欄 | OSsysCU 現有欄位 | 來源 | 狀態 |
|----------|------------------|------|------|
| N Code | — | **規劃** `portfolio_projects.n_code` | ❌ |
| Project Code | `projects.project_code` | 主鍵 | ✅ |
| Project Description | `project_name_zh`／`project_name_en`／Master `description` | 多源 | ⚠️ |
| PM | `projects.project_manager` | Cover | ⚠️ 需填 |
| Commencement Date | `main_contract_commencement_date` 或 Master `start_date` | Cover/Master | ⚠️ |
| Contract Completion Date | `project_completion_date` 或 Master `completion_date` | Cover/Master | ⚠️ |
| PC Date | `projects.pc_cert_date` | Cover | ⚠️ |
| PC Cert ✔ | `fac_pc_cert_path` 有附件 或衍生 | Main FAC 附件 | ⚠️ |
| DLP Commencement Date | 衍生：`pc_cert_date + 1日` 或手動 | 計算 | ⚠️ |
| DLP (days) | `dlp_period_months × 30` 或手動天數 | Cover | ⚠️ 單位不同 |
| DLP Expiry Date | 衍生或 `dlp_cert_date` 前一日 | 計算 | ⚠️ |
| Retention to be released | Main FAC 保固金列／Cover retention | `build_fac_retention_rows` | ⚠️ |
| Defect Correction Certificate ✔ | `dlp_cert_date` 或 `fac_mg_cert_path` | Cover/Main FAC | ⚠️ |
| 預計完工日期 | — | **規劃** `portfolio_projects.expected_completion_date` | ❌ |
| Remark | `projects.notes` 或專用 remark | — | ⚠️ |
| Contract Sum | `projects.contract_amount` | Payment/Cover | ✅ |
| Project Completed/On Progress | — | **規劃** `portfolio_projects.project_progress_status` | ❌ |
| Client | `projects.client` | Payment/Master | ✅ |
| Client Final Account Status | — | **規劃** `portfolio_projects.client_fac_status` | ❌ |

### 右側 — 分判 FAC 矩陣（15 組 × 2 欄）

| Excel 欄（重複） | OSsysCU 現有 | 狀態 |
|-----------------|--------------|------|
| Name of Sub-contractor #1–15 | `subcontractors.company_name_*` | ✅ 逐項有 |
| Final Account Status #1–15 | — | ❌ 無狀態欄 |

**分判 FAC 狀態推導（規劃，若未手動填）：**

| 狀態 | 推導規則 |
|------|----------|
| Completed | `sc_fac_signed_date` 有值 或 FAC PDF 已簽 |
| On Progress | 有分判 + 已付 < 修訂合約 |
| 待簽 | 餘款≈0 但未簽 |
| — | 無此分判 |

**Select 選項（與 Excel 一致）：** `Completed` · `On Progress` · `待簽` · `—`

---

## 表 4：On Progress Projects（進度表）

**參考檔：** `Ref/From QS/On Progress Projects - Apr 2026.xlsx`（38 行 × 11 欄）

| Excel 欄 | OSsysCU 欄位 | 狀態 |
|----------|--------------|------|
| Project Code | `projects.project_code` | ✅ |
| Project Description | `project_name_*`／Master `description` | ⚠️ |
| Client | `projects.client` | ✅ |
| PM | `projects.project_manager` | ⚠️ |
| Commencement Date | `main_contract_commencement_date`／Master `start_date` | ⚠️ |
| Contract Completion Date | `project_completion_date`／Master `completion_date` | ⚠️ |
| PC Date | `pc_cert_date` | ⚠️ |
| 預計完工日期 | **規劃** `expected_completion_date` | ❌ |
| Remark | `notes` | ⚠️ |
| Contract Sum | `contract_amount` | ✅ |
| Completed / On Progress | **規劃** `project_progress_status` | ❌ |

---

## Cover Page 欄位速查（FA／進度表共用）

定義於 `project_cover.PROJECT_COVER_MIGRATIONS`：

| Cover 欄位 | 對 FA／進度表 |
|------------|---------------|
| `project_manager` | PM |
| `main_contract_commencement_date` | Commencement Date |
| `project_completion_date` | Contract Completion Date |
| `pc_cert_date` | PC Date |
| `dlp_period_months` | DLP (days) 換算 |
| `dlp_cert_date` | Defect Correction Certificate |
| `mp_fac_signed_date` | Client FA 輔助 |
| `sc_fac_signed_date` | 分判 FAC 輔助 |
| `contract_amount` | Contract Sum |

---

## Main FAC vs SC FAC 資料來源

| 概念 | Main FAC (`main_fac.py`) | SC FAC (`sc_fac.py`) |
|------|--------------------------|----------------------|
| 儲存 | `projects.fac_*` 欄位 | 無 DB 表，runtime 計算 |
| 原始合約 | `contract_amount` (a) | `subcontractors.contract_amount` |
| VO | `fac_variations_d_override` 或 VO 合計 | `sc_vo_records` type=`vo` |
| 代支 | `fac_contra_charge_j_override` 或 deduction 合計 | `sc_vo_records` type=`deduction` |
| 已付 | override 或 `ip_total_income` | `payment_records.paid_amount` 合計 |
| 附件 | `fac_statement/pc/mg_*` | PDF/DOCX 生成 |

---

## 四表覆蓋度總表

| 能力 | Payment | Master | FA 左欄 | FA 分判矩陣 | 進度表 |
|------|---------|--------|---------|-------------|--------|
| Excel 匯入 | ✅ | ✅ | ❌ | ❌ | ❌ |
| 系統內維護 | ✅ | ✅ | ⚠️ Cover 分散 | ❌ | ❌ |
| 匯出 Excel | ⚠️ 報表 | ⚠️ | ❌ | ❌ | ❌ |
| 全公司總表 View | — | Master List 頁 | ❌ | ❌ | ❌ |

UI／API 規格見 [Portfolio FAC UI Spec.md](./Portfolio%20FAC%20UI%20Spec.md)。
