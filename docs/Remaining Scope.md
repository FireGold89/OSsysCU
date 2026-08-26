# Remaining Scope

> 依 **code 缺失** + **`PENDING.md`** + **`docs/匯報-20260814.md`** 交叉整理。  
> 不含路線圖中尚未寫入 code 的規劃細節（標 `[Inferred]`）。

---

## 完成度圖例

| 符號 | 含義 |
|------|------|
| ✅ | Code 已實作且 PENDING 已勾或無待辦 |
| ⚠️ | 部分實作；PENDING 或匯報標待完善 |
| ❌ | Code 未見實作 |

---

## 模組完成度矩陣

| 模組 | 狀態 | 依據 |
|------|------|------|
| 地盤 Payment Excel 匯入 | ✅ | `excel_importer_payment.py`, `/api/import/excel` |
| 分判付款 + 中期糧款 PDF/XLSX/DOCX | ✅ | `interim_cert_report.py` |
| 分判 VO/扣款 sc-vo-reg | ✅ | `PENDING.md` Phase A–C ✓ |
| 地盤糧期 + IP 附件 + SC 矩陣 | ✅ | `ip_period.js`, `interim_payments` |
| 分判 FAC PDF Phase A+B | ✅ | `sc_fac_pdf.py`, `PENDING.md` L179–186 |
| Master List CRUD/同步/配對 | ✅ | `/api/master/*`, `master_link.py` |
| ISO 文件頁 | ✅ | `iso_docs.js`, `PENDING.md` L213 |
| OCR 多引擎 | ✅ | `ocr_processor.py` |
| QS 匯報 PDF | ✅ | `qs_report_pdf.py` |
| 工程分類 / 工作範疇 | ✅ | `engineering_categories`, `master_trade_categories` |
| MS/C 合約登記 | ✅ | `sc_contract_registry` |
| 主合約 FAC **表單** | ✅ | `main_con_fac.js`, `main_fac.py` |
| 主合約 FAC **PDF** | ⚠️ | `PENDING.md` L193「p19 仍 HOLD」 |
| 分判 FAC Phase C | ⚠️ | `PENDING.md` L188–191 物料列、簽署 PDF |
| Retention 連動 | ⚠️ | `PENDING.md` L42–43；`retention_sum` 未接 interim cert |
| Master List 財務 Phase 2 | ⚠️ | `匯報-20260814.md` L116「子表需重 sync」 |
| ISO 文件 Phase 2–3 | ⚠️ | `PENDING.md` L12–25 folder/版本 |
| 角色權限 enforce | ⚠️ | 欄位有；無 login/API 403 |
| 成員登入 | ❌ | `PENDING.md` L206 defer |
| Audit log | ❌ | `PENDING.md` L207 |
| BOQ 模組 | ❌ · **待 QS 決策** | 無表/API；見 `docs/BOQ Decision - QS Meeting Brief.md` |
| C 行 Material On Site | ❌ | 恒 0 — `interim_cert_report.py` |
| 分判商主檔 | ❌ | 無 `subcontractor_companies` 表 |
| Remeasurement 引擎 | ❌ | FAC B/E 手填 |

---

## PENDING.md 待辦（code 未做）

### 文件管理 Phase 2–3 `[Code]` 文件 / `[Code]` 未實作

- [ ] 新建地盤自動 `uploads/iso/{project_code}/`
- [ ] ISO 上傳改存項目子目錄
- [ ] 全局 path template → `doc_library_url`
- [ ] 換檔版本保留
- [ ] ISO 只填 SharePoint 連結
- [ ] 上傳者／審批（依成員系統）

**參考**：`PENDING.md` L12–28

### Retention `[Code]` 未接線

- [ ] `retention_sum` ↔ 中期糧款 5% 自動計算
- [ ] 分判合約類型 Retention = 判項金額 × %

**參考**：`PENDING.md` L42–43

### 分判 FAC Phase C `[Code]` 部分

- [ ] 物料/人工加減列可編輯覆寫
- [ ] 上傳已簽署 FAC PDF 存檔
- [ ] 版面微調 / logo
- [ ] 主合約 FAC PDF

**參考**：`PENDING.md` L188–193

### 系統基礎 defer `[Code]` 未實作

- [ ] 成員／登入系統
- [ ] Audit log

**參考**：`PENDING.md` L206–207

---

## 匯報路線圖（規劃，多數未在 code）`[Inferred]`

來源：`docs/匯報-20260814.md` §五

| Phase | 主題 | Code 現況 |
|-------|------|-----------|
| Phase 1 | 編號正規化、批量配對、staff 去重 | 部分已有 `master_link`；批量工具未齊 |
| Phase 2 | 分判商主檔 | ❌ 無表 |
| Phase 3 | 登入、Audit、通知 | ❌ |
| Phase 4 | Master List 深度優化 | ⚠️ 持續 |
| Phase 5 | 管理層報表擴展 | ⚠️ 僅 QS PDF 基礎 |
| Phase 6 | 文件庫基礎設施 | ⚠️ URL 有；folder 無 |

---

## 已知 Code 占位 / 簡化

| 項目 | 現況 | 證據 |
|------|------|------|
| 中期糧款 C 行 | 固定 0 | `interim_cert_report.py` |
| 保固金 % | 硬編 0.05 | `payments.js` L653 |
| 主合約 B/E/F/G | 手填 | `main_fac.py` |
| ip_reconcile | 唯讀 | 無寫回 API |
| `interim_cert_pdf.py` | 3 行 re-export | 非占位，薄封裝 |

---

## 近期已完成（供對照，毋須重做）`[Code]`

`PENDING.md` L211–218：

- ISO 文件登記頁
- 文件庫連結（全局 + 項目）
- 分判付款 Tab 整合
- 糧期 IP Cert 上傳
- 主合約最終結算頁 A–K

`docs/匯報-20260814.md` §2：Master List 表單 UX、負責 QS 下拉、MS/C 負責同事下拉等。

---

## 文件維護 `[Code]` 矛盾

| 文件 | 版本字串 | 現行 |
|------|----------|------|
| `PENDING.md` L226 | `20260807-doc-settings` | 過時 |
| `startup.APP_VERSION` | — | `20260813-eng-cat` |

---

## 建議優先序 `[Inferred]`

1. 釐清 A–E 公式 canonical（見 Calculation Rules.md）
2. Retention 接線或文档化為「固定 5%」
3. 登入 / 權限（生产 API 目前无 auth）
4. 主合約 FAC PDF
5. 分判商主檔（需新建 schema）

此優先序為分析推論，非 code 或管理層決議。

---

## BOQ 模組 — 條件式範圍 `[待 QS 會議]`

來源：`docs/BOQ Decision - QS Meeting Brief.md`

| QS 決策 | 納入 Remaining Scope | 文件 |
|---------|----------------------|------|
| Out of scope | 無新增 code task | `PENDING.md` BOQ 段 |
| 輕量加強 | P1 C 行 MOS · P2 SC FAC 物料列 · P3 FAC UX | `BOQ Decision - Lightweight Scope.md` |
| 報價明細子表 | + P4 `sc_quotation_lines` | 同上 §4 |
| 完整 BOQ | 獨立 Phase BOQ-0～5 | `BOQ Module Design (Draft).md` |

**會前不排入 sprint**，避免與 Retention／登入搶資源。
