# Portfolio FAC UI 規格（N 項目結算總表 + 進度表）

> 對應 QS 參考檔：  
> - `Ref/From QS/N Project - Final Account Status List - r2.xlsx`  
> - `Ref/From QS/On Progress Projects - Apr 2026.xlsx`  
>
> 欄位對照見 [QS Reference Excel Field Mapping.md](./QS%20Reference%20Excel%20Field%20Mapping.md)  
> 總覽見 [QS Reference Excel Overview.md](./QS%20Reference%20Excel%20Overview.md)

**狀態：** 📋 規格草案（尚未實作）

---

## 1. 目標

1. 在系統內維護 **全公司 N 項目 FAC 狀態總表**（含分判矩陣）。
2. 提供 **進行中項目** 精簡 view（11 欄），與 FA 清單左欄共用資料。
3. 支援 **匯入／匯出** QS 現用 Excel 格式。
4. 可 **從既有 projects + Cover + 分判/Main FAC** 自動回填，減少重複輸入。

---

## 2. 導航結構

在側欄 **「管理」** 區新增兩個全公司頁（**不需先選項目**）：

```
── 全公司總表 ──
📋 N 項目結算總表    data-page="portfolio-fac"
🚧 進行中項目        data-page="portfolio-progress"
```

| 頁面 | Topbar 標題 | 副標題 |
|------|-------------|--------|
| portfolio-fac | N 項目結算總表 | 全公司主合約及分判 FAC 狀態 |
| portfolio-progress | 進行中項目 | On Progress Projects 快照 |

**沿用現有 UX：** Toast、`showContentLoading`、Modal Esc、sticky 表頭、`data-theme` light/dark。

---

## 3. 頁面 A：N 項目結算總表

### 3.1 布局

```
┌─────────────────────────────────────────────────────────────┐
│ [篩選] 狀態▾  PM▾  Client▾  負責人▾  🔍搜尋 Project/N Code   │
│ [匯入 Excel] [匯出 Excel] [從系統同步]  上次更新：YYYY-MM-DD   │
├─────────────────────────────────────────────────────────────┤
│ KPI：進行中 N │ 已完成 N │ Client FA 待辦 N │ 分判待簽 N     │
├─────────────────────────────────────────────────────────────┤
│ ◀ 固定左欄 │ 可橫向捲動 — 分判 FAC 矩陣 ▶                      │
│ N│Code│描述│PM│…│Client│Client FA│判1│狀1│…│判15│狀15       │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 左側固定欄（19 欄，對齊 FA Excel）

| # | 欄位 | 可編輯 | 點擊／連結 |
|---|------|--------|------------|
| 1 | N Code | ✅ | — |
| 2 | Project Code | 唯讀 | → 該項目 Dashboard |
| 3 | 項目描述 | 唯讀 | 來自 project / Master |
| 4 | PM | ✅ | 同步 Cover `project_manager` |
| 5 | Commencement Date | ✅ | Cover / Master |
| 6 | Contract Completion Date | ✅ | Cover / Master |
| 7 | PC Date | ✅ | Cover `pc_cert_date` |
| 8 | PC Cert | ✅ checkbox | Main FAC PC 附件 |
| 9 | DLP Commencement Date | ✅ / 計算 | PC+1 或手動 |
| 10 | DLP (days) | ✅ | Cover 月數換算或手動 |
| 11 | DLP Expiry Date | ✅ / 計算 | — |
| 12 | Retention to be released | 唯讀 | Main FAC retention 列 |
| 13 | Defect Correction Certificate | ✅ checkbox | Cover / Main FAC MG |
| 14 | 預計完工日期 | ✅ | — |
| 15 | Remark | ✅ | — |
| 16 | Contract Sum | 唯讀 | `contract_amount` |
| 17 | 項目狀態 | ✅ select | Completed / On Progress |
| 18 | Client | 唯讀 | — |
| 19 | Client FA Status | ✅ select | Completed / On Progress / 待簽 |

### 3.3 右側分判矩陣（最多 15 組）

| 欄 | 可編輯 | 預填來源 |
|----|--------|----------|
| 分判商名稱 | ✅（可選系統分判下拉） | `subcontractors` |
| FAC Status | ✅ select | 手動 或 SC FAC 推導 |

**行內快捷：** 分判名稱旁 🔗 → 該項目「分判最終結算」頁（`sc-fac`）。

### 3.4 互動

| 動作 | 行為 |
|------|------|
| 列點擊 | 展開 drawer：Cover 日期摘要 + Main FAC 連結 + 分判列表 |
| 從系統同步 | 以 projects + Cover + subcontractors 覆寫可自動欄；**保留**手動狀態欄 |
| 匯入 Excel | 解析 `Final Account` sheet（r2 格式） |
| 匯出 Excel | 輸出與 QS 主管相同欄位順序（49 欄） |
| Sticky | 左 3 欄（N / Code / 描述）+ 表頭固定 |

### 3.5 篩選預設

- 預設：`project_progress_status = On Progress`
- 快捷篩選：`Client FA ≠ Completed`、`DLP 90 天內到期`

---

## 4. 頁面 B：進行中項目

可為獨立頁，或 FA 頁的 **「精簡模式」** Tab。

### 4.1 布局

```
┌──────────────────────────────────────────────────┐
│ [Tab: 全部 | 進行中 | 已完成]  PM▾  🔍  [匯出]    │
├──────────────────────────────────────────────────┤
│ Project Code │ 描述 │ Client │ PM │ 開工 │ 完工 │
│ PC │ 預計完工 │ Remark │ Contract Sum │ 狀態    │
└──────────────────────────────────────────────────┘
```

11 欄與 `On Progress Projects - Apr 2026.xlsx` 一一對應。

### 4.2 與 FA 頁關係

- 同一 `portfolio_projects` 表的 **subset view**
- 進度表 = `project_progress_status IN ('On Progress')` 或匯入標記
- 任一頁編輯，另一頁即時一致

---

## 5. 資料模型（規劃）

> 實作時加入 `database.py` migration；完成後更新 [Data Model.md](./Data%20Model.md)。

### 5.1 `portfolio_projects`

```sql
CREATE TABLE portfolio_projects (
  id INTEGER PRIMARY KEY,
  project_id INTEGER UNIQUE REFERENCES projects(id),
  n_code TEXT,
  expected_completion_date TEXT,
  project_progress_status TEXT,    -- Completed | On Progress
  client_fac_status TEXT,          -- Completed | On Progress | 待簽
  pc_cert_done INTEGER DEFAULT 0,
  defect_cert_done INTEGER DEFAULT 0,
  dlp_commencement_date TEXT,
  dlp_days INTEGER,
  dlp_expiry_date TEXT,
  retention_to_release REAL,
  portfolio_remark TEXT,
  source_file TEXT,
  last_import_at TEXT,
  updated_at TEXT
);
```

### 5.2 `portfolio_sc_fac_status`

```sql
CREATE TABLE portfolio_sc_fac_status (
  id INTEGER PRIMARY KEY,
  portfolio_project_id INTEGER REFERENCES portfolio_projects(id),
  slot_no INTEGER NOT NULL,        -- 1..15
  subcon_name TEXT,
  subcontractor_id INTEGER,        -- 可選 FK subcontractors
  fac_status TEXT,
  UNIQUE(portfolio_project_id, slot_no)
);
```

### 5.3 `portfolio_imports`

```sql
CREATE TABLE portfolio_imports (
  id INTEGER PRIMARY KEY,
  import_type TEXT NOT NULL,       -- fa_list | progress_list
  filename TEXT,
  rows_read INTEGER,
  rows_upserted INTEGER,
  imported_at TEXT
);
```

---

## 6. API 規格（規劃）

| 方法 | 路由 | 說明 |
|------|------|------|
| GET | `/api/portfolio/fac` | FA 總表（含分判矩陣 + stats） |
| GET | `/api/portfolio/progress` | 進度表 subset |
| PUT | `/api/portfolio/projects/<id>` | 更新左欄 + 狀態 |
| PUT | `/api/portfolio/projects/<id>/sc-status` | 更新分判矩陣（body: slots[]） |
| POST | `/api/portfolio/import/fa-list` | multipart 上傳 FA Excel |
| POST | `/api/portfolio/import/progress-list` | multipart 上傳進度表 |
| GET | `/api/portfolio/export/fa-list` | 下載 FA 格式 xlsx |
| GET | `/api/portfolio/export/progress-list` | 下載進度表 xlsx |
| POST | `/api/portfolio/sync-from-projects` | 從 Cover/分判/Main FAC 回填 |

### 6.1 GET `/api/portfolio/fac` 回傳範例

```json
{
  "items": [{
    "n_code": "N35",
    "project_id": 42,
    "project_code": "Q1059_25",
    "description": "友聯船廠A,B,C座宿舍內部區域改造裝修工程",
    "pm": "Dennis Chan",
    "commencement_date": "2025-08-01",
    "contract_completion_date": null,
    "pc_date": null,
    "pc_cert_done": false,
    "dlp_commencement_date": null,
    "dlp_days": 365,
    "dlp_expiry_date": null,
    "retention_to_release": null,
    "defect_cert_done": false,
    "expected_completion_date": "2026-06-30",
    "remark": "",
    "contract_sum": 43000000,
    "project_progress_status": "On Progress",
    "client": "友聯船廠有限公司",
    "client_fac_status": "On Progress",
    "subcontractors": [
      {"slot": 1, "name": "東寶工程公司", "fac_status": "On Progress", "subcontractor_id": 101},
      {"slot": 2, "name": "雅弘建築有限公司", "fac_status": "On Progress", "subcontractor_id": 102}
    ]
  }],
  "stats": {
    "on_progress": 28,
    "completed": 12,
    "client_fa_pending": 5,
    "sc_fac_pending": 8
  }
}
```

---

## 7. 前端檔案規劃

| 檔案 | 職責 |
|------|------|
| `frontend/js/portfolio_fac.js` | FA 總表 render、篩選、inline edit |
| `frontend/js/portfolio_progress.js` | 進度表（或與 fac 共用 module） |
| `frontend/index.html` | `#page-portfolio-fac`、`#page-portfolio-progress` |
| `frontend/css/style.css` | `.portfolio-table` sticky 左欄、橫向 scroll |
| `portfolio.py` | DB CRUD + sync 邏輯 |
| `portfolio_importer.py` | FA / 進度表 Excel 解析 |
| `app.py` | 掛上述 API |

---

## 8. 匯入邏輯要點

### 8.1 FA List（r2）

- Sheet 名：`Final Account`
- 表頭列：含 `N Code` 的第 2 行（0-based row 1）
- Project Code 正規化：`Q1059_25` ↔ 配對 `projects.project_code`
- 分判矩陣：欄 20 起每 2 欄一組（Name, Status），最多 15 組
- 匯入策略：**upsert** by `project_code`；未知 code 可選「僅預覽」或建立 placeholder 項目

### 8.2 Progress List

- 表頭列：含 `Project Code` 的首行
- 11 欄直寫 `portfolio_projects`；不帶分判矩陣

### 8.3 從系統同步（不回寫手動狀態）

| 欄位 | 同步來源 | 覆寫手動？ |
|------|----------|------------|
| PM, 日期, Contract Sum, Client | projects + Cover + Master | 否（若 portfolio 已有值且 `manual_lock` 未實作則跳過） |
| PC Cert / Defect Cert | 附件存在 → checkbox | 是（衍生） |
| Retention | Main FAC | 是（衍生） |
| 分判名稱 | subcontractors 前 N 筆 | 僅空 slot |
| FAC Status | 推導規則 | **否**（保留 QS 手填） |

---

## 9. 實作 Phase

| Phase | 內容 | 優先 |
|-------|------|------|
| **P1** | DB 表 + 進度表 view（11 欄）+ 從 projects 自動生成 | 高 |
| **P2** | FA 左欄 19 欄 + 匯入／匯出 r2 Excel | 高 |
| **P3** | 分判 FAC 矩陣 15 槽 + inline 編輯 + SC 連結 | 中 |
| **P4** | 「從系統同步」+ Dashboard KPI 卡片 | 中 |
| **P5** | Payment 東寶 Budget／扣數（延伸） | 低 |

---

## 10. 驗收清單（實作後）

- [ ] 匯入 `N Project - Final Account Status List - r2.xlsx` 後 43 項可見
- [ ] 匯出 Excel 欄位順序與 QS 原版一致
- [ ] Q1059_25 四表資料在系統內可交叉跳轉
- [ ] 進度表 11 欄與 FA 左欄編輯同步
- [ ] dark / light 主題表格可讀
- [ ] 長表 sticky 表頭 + 左欄固定
