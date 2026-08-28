# QS 參考 Excel 總覽

> QS 主管提供之四份參考檔案分析（2026-08-27）。  
> 參考檔位置：`Ref/From QS/`、`Ref/2025 Quotation & Contract number.xlsx`

---

## 四表在 QS 工作流程中的角色

| 檔案 | 路徑 | 層級 | 主要用途 |
|------|------|------|----------|
| **Payment Status** | `Ref/From QS/MS_Q1059_25 - Main contract Works Payment Status Table R6.xlsx` | 單項目 | 地盤代支付款明細（發票、分判、OA、IP） |
| **Master List** | `Ref/2025 Quotation & Contract number.xlsx` | 全公司 | 報價／合約主檔（所有項目從這裡編號） |
| **Final Account 清單** | `Ref/From QS/N Project - Final Account Status List - r2.xlsx` | 全公司 | N 項目結算狀態總表（主合約 + 各分判 FAC） |
| **進度表** | `Ref/From QS/On Progress Projects - Apr 2026.xlsx` | 全公司 | 進行中／已完成項目快照 |

---

## 編號對照規則（四表共通）

| 格式 | 範例 | 系統欄位 |
|------|------|----------|
| Master List 完整報價編號 | `MS/Q1059/25/dc` | `quotation_registry.quotation_no` |
| MP 合約代碼 | `Q1059_25` | `projects.project_code`；FA／進度表 Project Code |
| 地盤付款表檔名／首列 | `MS_Q1059_25` | 匯入 → `project_code` |
| N Code | `N35` | **尚未有 DB 欄位**（FA 清單專用） |

系統已有 `project_cover.derive_mp_contract_code()`：`MS/Q1059/25/dc` → `Q1059_25`。

---

## 規模摘要（實測 2026-08-27）

| 檔案 | Sheets | 資料量 |
|------|--------|--------|
| Payment Status (Q1059) | 5 | 代支 ~163 筆、30 分判編號 |
| Master List 2025 | 2 | 報價 ~3,086 行 × 37 欄 |
| FA 清單 r2 | 1 | ~43 N 項目 × 49 欄 |
| 進度表 Apr 2026 | 1 | ~38 項目 × 11 欄 |

---

## 四表重疊（FA vs 進度表）

|  | 數量 |
|--|------|
| FA 清單項目 | 43 |
| 進度表項目 | 38 |
| 兩邊都有 | **36** |
| 只在 FA | 7（含 Completed、格式異常列） |
| 只在進度表 | 1–2 |

> 進度表 ≈ FA 清單左側 19 欄的**精簡版**（去掉 N Code、DLP、Retention、Client FA、分判矩陣）。

---

## Q1059_25 四表串聯示例

| 表 | 對應資料 |
|----|----------|
| Master List | `MS/Q1059/25/dc`；HK$ 45,673,740；Dennis Chan；友聯船廠 |
| Payment Status | `MS_Q1059_25`；163 筆代支；30 分判 |
| FA 清單 | N35；主合約 + Client FA = `On Progress`；東寶、雅弘 = `On Progress` |
| 進度表 | `Q1059_25`；`On Progress` |

---

## 與 OSsysCU 覆蓋度

| Excel | 匯入 | 系統內維護 | 全公司總表 View |
|-------|------|------------|-----------------|
| Payment Status | ✅ `excel_importer_payment.py` | ✅ | —（單項目） |
| Master List | ✅ `master_list_importer.py` | ✅ | ✅ Master List 頁 |
| FA 清單 | ❌ | ⚠️ Cover／FAC 分散 | ❌ |
| 進度表 | ❌ | ⚠️ 資料散落各處 | ❌ |

---

## 相關文件

| 文件 | 內容 |
|------|------|
| [QS Reference Excel Field Mapping.md](./QS%20Reference%20Excel%20Field%20Mapping.md) | 四份 Excel **逐欄**對照 DB |
| [Portfolio FAC UI Spec.md](./Portfolio%20FAC%20UI%20Spec.md) | N 項目結算總表 + 進度表 **UI／API／Schema 規格** |
| [Remaining Scope.md](./Remaining%20Scope.md) | 待實作模組（含 Portfolio） |
| [Feature Inventory.md](./Feature%20Inventory.md) | 功能矩陣 |

---

## 建議實作 Phase

| Phase | 內容 |
|-------|------|
| **P1** | DB `portfolio_*` + 進度表 view（11 欄）+ 從 `projects` 自動生成 |
| **P2** | FA 左欄 19 欄 + 匯入／匯出 r2 Excel |
| **P3** | 分判 FAC 矩陣 15 槽 + inline 編輯 + SC 連結 |
| **P4** | 「從系統同步」推導規則 + Dashboard KPI |
| **P5** | Payment 東寶 Budget／扣數 sheet（可後做） |
