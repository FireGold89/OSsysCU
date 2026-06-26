# Changelog

本專案變更記錄。格式參考 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.1.0/)。

## [未發布]

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
