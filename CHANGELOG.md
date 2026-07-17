# Changelog

本專案變更記錄。格式參考 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.1.0/)。

## [未發布]

`APP_VERSION`: `2026-07-15-ip-phase234`

### 新增
- 分包糧期 Phase 2：Summary row 41 工種簡稱匯入 `trade_label`；矩陣表頭三行（SC／工種／公司）
- 分包糧期 Phase 3：點擊矩陣 cell drill-down 付款登記；糧期矩陣 vs Sub-IP 明細核對
- 分包糧期 Phase 4：按期／按分判視圖切換；超付分判警示（餘額 < 0）

`APP_VERSION`: `2026-07-15-sc-matrix-phase1`

### 新增
- 分包糧期矩陣 Phase 1：表頭顯示分判商公司名（join subcontractors）；表尾加判項金額／付款登記／餘額；糧期合計 vs 付款登記核對標籤

`APP_VERSION`: `2026-07-15-ip-sc-matrix`

### 新增
- 分包糧期矩陣：`interim_payment_sc_lines` 表；Excel Summary 匯入各 SC 欄（SC-004…）及總支出（M 欄）；糧期頁「分包糧期明細」矩陣表
- 主糧期「分包總支出」改讀 Summary 總計欄（修正先前誤取第一個 SC 欄）

`APP_VERSION`: `2026-07-06-ip-reconcile`

### 新增
- 糧期核對：地盤 QS（申請／批款）↔ 行政 Master（開票／收票）並排對照；狀態標籤（一致、金額差、僅行政、僅地盤）；只讀不覆寫；Master 編輯「糧期核對」分頁 + 糧期狀況頁面

`APP_VERSION`: `2026-07-04-qs-subcon-lines`

### 修正
- Master List 來源檔名正規化為 `YYYY Quotation & Contract number.xlsx`（含 DB 舊 `(新)…as 27.8.2024` 檔名遷移）

### 新增
- Master List QS 主分判：Excel 欄 X/Y 多行（例 MS/Q1241/24/kp 四家分判商）解析至 `master_qs_subcon_lines`；編輯畫面新增「主分判 QS」分頁；Admin 分判付款「主分判 ✓」對照全部 QS 主分判

`APP_VERSION`: `2026-07-03-finance-display`

### 修正
- Master List 財務明細：業主糧期、分判付款、支票統一結構化解析（A , B, C 格式）；日期顯示 dd/m/yyyy

### 修正
- Master List 支票明細：解析為支票號碼／銀行／日期三欄（例 `#828310 , 003, 22/3/2025`）

### 修正
- Master List Phase 2 財務：新增 `sync-finance` 重匯糧期／分判付款／支票；編輯畫面無明細時提示重新同步

### 修正
- 項目負責人管理：只顯示全名；停用縮寫（EC、KM 等）與同名重複；新增時禁止縮寫

### 修正
- Master List：負責人篩選改以主檔 `person_in_charge` 全名為準（下拉與列表一致）；縮寫主檔自動正規化為全名；不再以 staff id／尾碼區分

### 修正
- Master List 負責人篩選：統計與列表同一套 `person_in_charge` 比對；支援 staff id／舊縮寫參數；選負責人時不再重刷下拉

### 修正
- Master List 負責人篩選：下拉只顯示項目負責人管理全名，依 `person_in_charge` 比對（不用報價尾碼／縮寫分組）

### 修正
- 報價編號尾碼與項目負責人脫鉤：尾碼僅編號慣例；跟進人以 Master List 姓名為準，可由不同同事接手
- 項目負責人管理：移除報價尾碼欄；篩選／統計改依 `person_in_charge` 全名

### 修正
- 「負責人名單」改為「**項目負責人管理**」：以姓名為主、報價尾碼為輔；表格與說明文案同步調整

### 修正
- Master List：項目負責人以主檔全名為主，編輯／列表不顯示英文縮寫

### 修正
- 工程項目：變更項目代碼或從 Master List 帶入不同報價時須確認，避免誤改（例 Q1241→Q001）

### 修正
- 工程項目／Master List：項目負責人改為從負責人名單以**姓名**選擇，縮寫自動帶入

### 修正
- Master List 編輯：列表快取直接開啟表單；API 改 query `?id=`（避免 path 含 `/` 或 `id/` 被誤判）
- JS 加版本參數強制刷新快取

### 修正
- Master List 編輯／配對：改以數字 id 呼叫 API，避免報價編號含 `/` 在 Zeabur 上 404

### 新增（Master List Phase 2 試行）
- 財務明細子表：主分判合約、業主糧期／發票、分判付款、支票
- 匯入時拆開 Excel 多行儲存格（2022+）；主檔 `subcon_company` 僅保留 QS 主分判欄
- 編輯 Master List 可檢視糧期／分判付款／支票分頁

### 修正
- 分判欄位全年匯入：外判公司→`分判商`、外判金額/分判金額→`分判金額`（2019–2021 依表頭自動對應）
- Master List 編輯：標籤統一為「分判商／分判金額」

### 修正（2026-06-27）
- 2018 Master List 補齊欄位：業主、報業主/大判、外判與否、外判公司、外判金額（及利潤）
- 2017 同步補齊業主／外判等欄位（欄位位置與 2018 不同）

### 修正（2026-06-27）
- Master List 匯入**「中標項目」**工作表（2019–2021 中標清單；2022+ 仍用報價 F 欄「中」）
- 固定 sheet 處理順序（報價→合約→中標項目），避免中標標記被覆蓋

### 修正（2026-06-27）
- Master List 匯入改依**表頭**辨識版型（不再用資料行猜測）：
  - **modern**（2022–2026）：F=中標、G=報價/標書
  - **transitional_site**（2019–2020）：F=屋苑/地點、G=工作範疇
  - **transitional_2021**（2021）：F=報價/標書、G=屋苑/地點
  - **legacy_english**（2017–2018）
- 2019–2020 可正確讀取業主、金額；合約 sheet E 欄屋苑不再誤併入報價編號
- `sync-all` 預設路徑改為專案內 `Ref/`

### 新增
- **負責人名單**（`staff_members` 表）：縮寫、姓名、部門、電郵、權限角色（預留）
- 側欄「負責人名單」頁：新增／編輯／停用；Master List 與工程項目負責人下拉改讀名單
- `master_ref` 全名對照改為優先讀資料庫名單

### 新增（2026-06-27）
- Master List 每筆可編輯（`PUT /api/master/quotations/...`）
- 工程項目：`quotation_no`、負責人欄位；配對 Master List 時同步項目代碼與負責人
- 儀表板顯示項目負責人；工程項目可「從 Master List 選擇」

### 新增（Master List Phase 1）
- 公司級 `Quotation & Contract number.xlsx` 匯入（`master_list_importer.py`）
- 資料表 `quotation_registry`、`master_list_imports`；前端 Master List 頁
- 唯一鍵：完整報價編號（例 `MS/Q001/26/jy`）；財務 Admin 欄位留待 Phase 2
- 支援 2017–2018 英文欄位及「合約」工作表；負責人縮寫見 `master_ref.py`

### 變更
- 現有地盤 Payment Excel 匯入保留為 `excel_importer_payment.py`（可獨立執行、對照用）
- `excel_importer.py` 改為相容入口（轉呼叫 payment 模組）

---

## [2026-06-08] — 版本基線與備份機制

`APP_VERSION`: `2026-06-08-fix-project-payment-progress`  
`Git tag`: `release/2026-06-08`

### 新增
- `VERSION`、`RELEASE.md` 發行基線說明
- `scripts/backup_release.ps1` / `backup_release.sh` 一鍵完整備份（原始碼 zip + MANIFEST + 本機 DB）
- `.gitignore` 排除 `_backup/`、`_releases/`

---

`APP_VERSION`: `2026-06-08-fix-project-payment-progress`

### 修復
- 工程項目卡片「累計已付」因 JOIN 判項與付款而重複加總
- 付款進度不再硬上限 100%；超過承建金額時顯示提示及橙色進度條

---

## [2026-06-08] — Light / Dark 主題

`APP_VERSION`: `2026-06-08-light-dark-theme`

### 新增
- 頂部欄 ☀️ / 🌙 主題切換（淺色 / 深色）
- 主題偏好存入 `localStorage`（`qs_theme`）；首次造訪跟隨系統 `prefers-color-scheme`
- 儀表板 Chart.js 隨主題更新配色

### 變更
- `style.css` 重構為 `[data-theme="light"|"dark"]` CSS 變數

---

## [2026-06-13] — QS 匯報表 PDF 中文修復

`APP_VERSION`: `2026-06-13-pdf-chinese-font-v3`

### 修復
- PDF 中文亂碼：改為嵌入 TrueType（Windows `msjh.ttc`、Linux `fonts-wqy-zenhei`）
- Docker 安裝 `fonts-wqy-zenhei`；移除失效的 Noto 下載與 MSung CID 字型

### 新增
- 一鍵 **QS 匯報表** A4 PDF（重點摘要、關注事項、A–E 結算、糧期、分判明細）
- API：`GET /api/reports/boss-pdf/<project_id>`
- 關注事項：系統規則判斷（利潤率、墊支、未付比例、判項付款進度等）

---

## [2026-06] — UI 術語與雙語項目

### 新增
- 項目名稱中英分欄（`project_name_en` / `project_name_zh`）及 DB 遷移
- 發票 / 報價 OCR：文件類型判斷、判項建議、發票重複檢查、雙按鈕儲存（報價 / 發票）

### 變更
- 介面對齊香港 SME QS 用語（分判及支出、判項編號、付款登記、糧期狀況等）

---

## 部署核對清單

1. `git push origin main`
2. 等待 Zeabur 重建（約 1–3 分鐘）
3. `GET https://ossys.zeabur.app/api/system/status` → 確認 `app_version`
4. 瀏覽器 **Ctrl+F5** 強制重新整理靜態資源
