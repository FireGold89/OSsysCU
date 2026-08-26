# QS 系統進度會議匯報

> **會議日期**：2026-08-14  
> **系統版本**：`20260813-eng-cat`（核對：`GET /api/system/status` → `app_version`）  
> **生產環境**：https://ossys.zeabur.app  
> **對象**：管理層、QS 使用者  
> **資料來源**：`docs/` 系統分析文件（Requirements／Workflows／Architecture／Decisions 對應內容）、`PENDING.md`、code 唯讀查證  
> **機密**：本文不含密碼、Token 值、客戶敏感資料

---

## Executive Summary（一頁摘要）

### 現況一句話

OSsysCU 已具備 **Master List、工程項目、分判 MS/C、地盤付款、糧期 IP、分判 VO/扣款、中期糧款 PDF、主/分判 FAC、ISO 文件、OCR、QS 匯報 PDF** 等核心流程，可支援 QS 日常登記與匯出；**第一期 PPT 範圍內功能大致可用**。

### 整體完成度（code 證據）

| 區塊 | 完成度 | 說明 |
|------|--------|------|
| 地盤付款 / Excel 匯入 | **高** ✅ | `excel_importer_payment.py` |
| 分判付款 + 中期糧款 | **高** ✅ | `interim_cert_report.py` |
| 分判 VO/扣款（p15–18） | **高** ✅ | `sc_vo_reg.js`, `sc_vo_records` |
| Master List / MS/C | **中高** ⚠️ | CRUD + 同步已有；編號配對、財務子表待強化 |
| 主/分判 FAC | **中** ⚠️ | 表單 + 分判 PDF 已有；主合約 PDF、Phase C 待做 |
| 登入 / 權限 / Audit | **未做** ❌ | 明確 defer |
| BOQ 模組 | **未做 / 待決** ❌ | PPT 未列；待 QS 會議 |

### 三個最需管理層決策的事項

1. **A–E 利潤公式以哪套為準** — Dashboard/QS PDF 與 Cover「註冊及更新」目前可能顯示不同數字（已驗證 code 矛盾）。
2. **是否做 BOQ 模組** — PPT 第一期未列；建議先開 30 分鐘 QS 對齊會（材料已備）。
3. **上線前是否必須登入** — 現時全部業務 API 無 auth；`access_role` 僅預留欄位。

### 兩週重點（2026-08-14 → 2026-08-28）

| 優先 | 行動 | 負責 | 驗收 |
|------|------|------|------|
| P0 | QS BOQ 範圍決策會 | QS + 管理層 | Meeting Notes 勾選決策 |
| P0 | 確認 A–E 公式 canonical 來源 | QS | 書面指定 Excel 頁 / 函數 |
| P1 | 編號正規化（Q185↔Q0185）強化 | 開發 | 配對測試通過 |
| P1 | Retention 5% 規則書面化或接線 | QS + 開發 | 中期糧款與判項一致 |

### 風險概覽

| 風險 | 等級 | 緩解 |
|------|------|------|
| 無登入即全 API 可改 | **高** | 上線前決策是否加 auth |
| 報表 A–E 雙公式 | **中** | 本會議定 canonical |
| 編號 slash/underscore 誤配 | **中** | Phase 1 正規化 |
| BOQ scope creep | **中** | 先完成 QS 決策會 |

---

## 一、模組完成度及 Code 證據

圖例：**✅ 完成** · **⚠️ 部分** · **❌ 未做**

| 模組 | 狀態 | Code 證據 | 前端 |
|------|------|-----------|------|
| 工程項目 / Cover Page | ✅ | `app.py` `/api/projects/*`；`project_cover.py` | `projects.js` |
| Master List 報價 | ✅ | `/api/master/*`；`master_list_importer.py` | `master_list.js` |
| 分判 MS/C 合約登記 | ✅ | `/api/sc-contract-registry`；`sc_contract_importer.py` | `sc_contract_registry.js` |
| 地盤 Payment Excel 匯入 | ✅ | `/api/import/excel`；`excel_importer_payment.py` | `main.js` importModal |
| 分判判項 / 付款 | ✅ | `/api/subcontractors`；`/api/payments` | `payments.js` |
| 中期糧款 PDF/XLSX/DOCX | ✅ | `interim_cert_report.py`；`payment_records.interim_cert_json` | `payments.js` |
| 分判 VO/扣款（p15–18） | ✅ | `/api/sc-vo-*`；`sc_vo_records` | `sc_vo_reg.js` |
| 地盤糧期 IP + SC 矩陣 | ✅ | `interim_payments`；`ip_period.js` | `ip_period.js` |
| 糧期核對（唯讀） | ✅ | `/api/projects/.../ip-reconciliation` | `ip_reconcile.js` |
| 分判 FAC PDF Phase A+B | ✅ | `sc_fac_pdf.py`；`PENDING.md` L179–186 ✓ | `sc_fac.js` |
| 主合約 FAC 表單（p19） | ✅ | `main_fac.py`；`/api/projects/.../main-con-fac` | `main_con_fac.js` |
| ISO 文件登記 | ✅ | `iso_document_files`；`iso_docs.js` | `iso_docs.js` |
| OCR 多引擎 | ✅ | `ocr_processor.py`；`/api/ocr` | `ocr.js` |
| QS 匯報 PDF | ✅ | `qs_report_pdf.py`；`/api/reports/boss-pdf` | `reports.js` |
| 工程分類 / 工作範疇 | ✅ | `engineering_categories`；`master_trade_categories` | `master_trade.js` |
| 主合約 FAC **PDF** | ⚠️ | `PENDING.md` L193「p19 仍 HOLD」 | — |
| 分判 FAC **Phase C** | ⚠️ | 物料/人工列、簽署 PDF 存檔 — `PENDING.md` L188–191 | — |
| Retention 連動 | ⚠️ | `retention_sum` 未接；`payments.js` L653 硬編 5% | — |
| Master List 財務 Phase 2 | ⚠️ | 子表 API 有；資料新鮮度待確認 | — |
| ISO 文件 Phase 2–3 | ⚠️ | 自動 folder、版本 — `PENDING.md` L12–25 | — |
| 角色權限 enforce | ⚠️ | `staff_members.access_role` 有；無 login/403 | `staff.js` |
| 成員登入 | ❌ | 無 login route、無 session — `app.py` | — |
| Audit log | ❌ | 無 audit 表 — `database.py` | — |
| 分判商主檔 | ❌ | 無 `subcontractor_companies` | — |
| BOQ 模組 | ❌ 待決 | 無 BOQ 表/API — `docs/BOQ Workflow.md` | — |
| C 行 Material On Site | ❌ | `interim_cert_report.py` L141 恒 0 | — |

**版本核對**：`startup.py` → `APP_VERSION = '20260813-eng-cat'`

**架構**：Flask 單體 ~136 routes（`app.py`）+ SQLite（`database.py`）+ 靜態 SPA（`frontend/index.html`, `main.js`）

---

## 二、已驗證（Verified — 有 code 證據）

### 2.1 技術與部署

| 項目 | 證據 |
|------|------|
| 本機 `DATA_DIR` = repo 根；Docker 用 `/data` | `config.py` → `_resolve_data_dir()` |
| API 統一回應 `{ success, data/error }` | `app.py` → `resp()` |
| 業務 API **無登入** | `app.py` 全檔無 login route |
| 還原端點有 Token 保護（不含 Token 值） | `app.py` → `restore_database()`；`system_status()` 僅回傳 `restore_token_configured: bool` |
| 啟動時空庫可背景 sync Ref Excel | `startup.py` → `_sync_*_background()` |

### 2.2 功能已實作

| 項目 | 證據 |
|------|------|
| VO 套用後鎖定 `applied_payment_id` | `database.py` → `sc_vo_records`；刪除已套用回 400 |
| 中期糧款 B 行來自勾選 VO | `interim_cert_report.build_interim_cert_model()` |
| 分判 FAC 自動帶判項價、VO、扣款、已付 | `sc_fac.py` / `sc_fac_pdf.py` |
| QS PDF 關注事項為**規則引擎**非 AI | `qs_report_pdf._attention_items()` |
| 無 BOQ 資料表 | `database.py` schema；`Feature Inventory.md` |

### 2.3 已知矛盾（需業務決策，非 bug 猜測）

| ID | 矛盾 | Code 位置 |
|----|------|-----------|
| **Q1.1** | A–E：`get_project_summary()` vs `compute_settlement()` B/C 定義不同 | `database.py` L4040+；`project_cover.py` L270+ |
| **Q1.2** | 判項 stats **不含** VO；中期糧款 **含** VO | `database.py` L4016+；`payments.js` L476+ |
| **Q1.3** | 保固金 5% 硬編；`retention_sum` 欄未讀 | `payments.js` L653 |
| **Q1.4** | C 行 MOS 恒 0；模板 `vo_material` 存在 | `interim_cert_report.py` L141 |
| **Q1.5** | 糧期核對唯讀，無寫回 | `ip_reconcile.js` |

---

## 三、推測（Inferred — 由文件/命名推論，待確認）

| 項目 | 推論 | 依據 |
|------|------|------|
| PPT 第一期刻意不含 BOQ | QS 假設 BOQ/SOR 在 Excel 或附件處理 | `PENDING.md` 無 BOQ；`BOQ Decision Brief` |
| 「BOQ」在口語中可能指判項報價描述文字 | 非 line-item 模組 | `subcontractors.description` + OCR |
| 建議優先序：公式 → Retention → 登入 → FAC PDF → 分判商主檔 | 分析推論，非管理層決議 | `Remaining Scope.md` |
| 生產若未設 RESTORE_TOKEN，空庫還原行為不同 | 維運風險 | `Open Questions.md` Q3.2 |
| Phase 1–6 路線圖多數尚未寫入 code | 規劃 vs 實作差距 | `匯報-20260814.md` §五 |

---

## 四、待確認（Unknown / 待 QS·管理層會議）

| ID | 問題 | 影響 | 參考 |
|----|------|------|------|
| **Q2.1** | `Q185` vs `Q0185` 是否同一宗？ | Master ↔ 項目自動配對 | `master_link.py` |
| **Q2.2** | 項目編號尾碼 `_kp` 是否必須一致？ | MS/C link | `sc_contract_ref.py` |
| **Q2.3** | 一項目多報價時負責人顯示以誰為準？ | Summary 列表 | `projects.js` |
| **Q3.1** | 上線前是否必須登入？誰可改 Master List / 糧期？ | 安全與流程 | `Role Permission Matrix.md` |
| **Q5.1** | 主合約 FAC PDF 是否仍需要（p19 HOLD）？ | 交付範圍 | `PENDING.md` L193 |
| **Q5.2** | **是否做 BOQ 模組？** | 大型 scope | `BOQ Decision - QS Meeting Brief.md` |
| **Q5.3** | 分判商主檔 vs FAC Phase C 優先序？ | Phase 2 排序 | `匯報-20260814.md` |
| **Q4.2** | Ref Excel 誰負責定期 sync？ | 資料新鮮度 | `匯報-20260814.md` §3.2 |

---

## 五、Workflows 現況摘要（給 QS 使用者）

### 5.1 分判 VO → 中期糧款（已驗證）

```
分判變更以及扣款登記 (sc-vo-reg)
  → sc_vo_records 新增 VO/扣款
  → 分判付款登記勾選套用
  → payment_records + interim_cert_json
  → PDF/XLSX/DOCX (interim_cert_report.py)
```

詳見：`docs/VO Workflow.md`

### 5.2 地盤糧期 IP（已驗證）

```
Payment Status Excel 匯入
  → interim_payments + interim_payment_sc_lines
  → 糧期狀況頁 (ip_period.js)
  → 糧期核對唯讀 (ip_reconcile.js)
```

詳見：`docs/Progress Payment Workflow.md`

### 5.3 BOQ（不存在 — 待決策）

- 系統以 **判項總額 + VO + Excel 糧期 + FAC 手填** 運作
- OCR 報價行 → 描述文字，**不入庫**
- 決策材料：`docs/BOQ Decision - QS Meeting Brief.md`

---

## 六、風險與阻礙

### 6.1 風險登記

| # | 風險 | 類型 | 等級 | 現況 |
|---|------|------|------|------|
| R1 | 無登入，任何知道 URL 者可改資料 | 安全 | **高** | Verified |
| R2 | Dashboard 與 Cover 利潤數不一致 | 報表 | **中** | Q1.1 Verified |
| R3 | 編號格式混用導致誤配項目 | 資料 | **中** | Q2.1 Unknown |
| R4 | Retention 硬編 5% 與判項欄脫節 | 計算 | **中** | Q1.3 Verified |
| R5 | BOQ scope creep 拖慢第一期 | 範圍 | **中** | 待 QS 會 |
| R6 | `PENDING.md` 版本字串過時 | 文件 | **低** | L226 vs `20260813-eng-cat` |
| R7 | Master List 財務子表資料可能過舊 | 資料 | **低** | Inferred |

### 6.2 阻礙

| 阻礙 | 說明 |
|------|------|
| 業務規則未定 | A–E、VO 計入口徑、Retention % 未書面定案 |
| QS 資源 | BOQ 決策會、公式確認需 QS 出席 |
| 登入 defer | Audit、上傳者紀錄依賴成員系統（`PENDING.md` L206） |
| 主合約 FAC PDF HOLD | p19 打印版需求未關閉 |

---

## 七、需本會議決定的事項

| # | 決策項 | 選項 | 建議 |
|---|--------|------|------|
| D1 | **A–E 公式 canonical** | A) Dashboard/PDF  B) Cover 註冊及更新  C) 指定 Excel 頁 | 會中指定一個，開發統一 |
| D2 | **判項 Dashboard 是否含 VO** | 是 / 否 | 與中期糧款對齊 |
| D3 | **BOQ 模組** | Out of scope / 輕量 / 完整 BOQ | 先開 QS 專場 30min |
| D4 | **上線前登入** | 必須 / 內網可緩 / defer | 管理層 + IT |
| D5 | **Retention %** | 固定 5% / 依判項 / 接 Excel J 欄 | QS 確認 |
| D6 | **主合約 FAC PDF** | 做 / HOLD / 取消 | 對齊 p19 需求 |
| D7 | **兩週 sprint 優先** | 編號配對 / Retention / FAC C / 其他 | 見 §八 |

---

## 八、未來兩週行動計劃（2026-08-14 → 2026-08-28）

### Week 1（8/14 – 8/21）

| ID | 行動 | 負責人 | 驗收條件 | 狀態 |
|----|------|--------|----------|------|
| W1-1 | 召開 **BOQ 範圍決策會**（30min） | QS 負責人 + 管理層 | [`BOQ Decision - Meeting Notes.md`](../BOQ%20Decision%20-%20Meeting%20Notes.md) 勾選一項決策 | 待做 |
| W1-2 | **書面確認 A–E 公式**來源（Excel 哪一頁） | QS 負責人 | 回覆寫入 `Open Questions.md` Q1.1「QS 確認」欄 | 待做 |
| W1-3 | **書面確認**判項 stats 是否含 VO | QS 負責人 | Q1.2 關閉 | 待做 |
| W1-4 | 編號正規化：`Q185`↔`Q0185` 比對規則實装或文件化 | 開發 | `master_link` 測試用例 ≥3 宗通過 | 待做 |
| W1-5 | 更新 `PENDING.md` 底部版本字串 | 開發 | 與 `APP_VERSION` 一致 | 待做 |

### Week 2（8/22 – 8/28）

| ID | 行動 | 負責人 | 驗收條件 | 狀態 |
|----|------|--------|----------|------|
| W2-1 | 依 D1/D2 **統一公式**（若 Week1 已決） | 開發 | Dashboard 與 Cover 同一項目數字一致（抽樣 2 項目） | 待做 |
| W2-2 | Retention：接 `retention_sum` **或** 文件定「固定 5%」 | QS + 開發 | 中期糧款 PDF 與 QS 確認規則一致 | 待做 |
| W2-3 | 若 BOQ=**輕量**：排 P1 C 行 MOS 接線 | 開發 | 套用 `vo_material` 後 C 行非 0 | 條件式 |
| W2-4 | 若 BOQ=**Out of scope**：更新 Q5.2 標記 | 開發 | `Open Questions.md` 填「不做 BOQ」 | 條件式 |
| W2-5 | **上線登入**決策記錄（D4） | 管理層 + IT | 書面：必須/defer + 目標日期 | 待做 |
| W2-6 | 部署後版本核對 | 運維 | 生產 `/api/system/status` = 預期版本 | 待做 |

### 負責人定義

| 角色 | 職責 |
|------|------|
| **QS 負責人** | 業務規則確認、BOQ 決策、Excel 對照 |
| **管理層** | 優先序、上線範圍、登入政策 |
| **開發** | Code 實作、公式統一、文件更新 |
| **運維** | Zeabur 部署、Token 設定狀態（不記錄 Token 值） |

---

## 九、附錄

### 9.1 文件索引（Obsidian / docs 對照）

| 資料夾（規劃） | 現有文件 |
|----------------|----------|
| Requirements | `Feature Inventory.md`, `Remaining Scope.md`, `PENDING.md` |
| Workflows | `VO Workflow.md`, `Progress Payment Workflow.md`, `BOQ Workflow.md`, `Calculation Rules.md` |
| Architecture | `System Overview.md`, `Data Model.md`, `Screen and Route Map.md`, `Role Permission Matrix.md` |
| Decisions | `BOQ Decision - QS Meeting Brief.md`, `Open Questions.md` |
| Meetings | 本文件 |

### 9.2 近期已完成（毋須重做）`[Verified]`

來源：`PENDING.md` L240–247

- ISO 文件登記頁、文件庫連結
- 分判付款 Tab、MS/C 合約登記、判項類型
- 糧期 IP Cert 上傳、主合約最終結算 A–K
- 分判 VO/扣款登記 Phase A–C（p15–18）
- 分判 FAC PDF Phase A+B（p20–21）

### 9.3 修訂紀錄

| 日期 | 修訂 |
|------|------|
| 2026-08-14 | 首版：管理層/QS 進度會議匯報 |

---

*本報告供內部會議使用；技術細節見 `docs/System Overview.md`、`docs/Remaining Scope.md`。*
