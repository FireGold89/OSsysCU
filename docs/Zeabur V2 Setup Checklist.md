# Zeabur V2 設定清單（Staging）

> 分支 **`v2/portfolio`** 已 push：`https://github.com/FireGold89/OSsysCU/tree/v2/portfolio`  
> V1 不受影響：`main` → https://ossys.zeabur.app

**預估時間：** 約 10–15 分鐘（需在 Zeabur Dashboard 操作；CLI 目前無法改分支）

---

## Step 1 — 在同一 Project 新增 Service

1. 登入 [Zeabur Dashboard](https://zeabur.com/dashboard)
2. 打開 **OSsysCU 現有 Project**（與 V1 同一 project 即可，方便共用網路／管理）
3. **Add Service** → **GitHub** → 選 **`FireGold89/OSsysCU`**
4. Service 名稱建議：`ossys-v2` 或 `ossys-staging`

---

## Step 2 — 綁定分支（關鍵）

1. 進入新 Service → **Settings**（或 Source / Git 設定）
2. **Branch** 改為：`v2/portfolio`（**不要**用 `main`）
3. 確認 Build 方式：根目錄 **Dockerfile**（與 V1 相同）
4. 儲存後點 **Redeploy**

> 之後只有 push `v2/portfolio` 會重建此 Service；push `main` 只動 V1。

---

## Step 3 — 新建 Volume（必須獨立）

1. Service → **Volumes** → **Add Volume**
2. 掛載路徑：`/data`
3. **勿**掛載 V1 正在用的 Volume

空庫啟動後，可從 V1 Settings 下載 DB 或本機 `push_db_to_zeabur.ps1` 改 URL 上傳至 V2。

---

## Step 4 — Environment Variables

在 **Configuration → Variables** 新增（可從 V1 Service **複製** 再改）：

| 變數 | V2 建議值 | 說明 |
|------|-----------|------|
| `DEPLOYMENT_TIER` | `v2` | Topbar 顯示「V2 試用環境」 |
| `SECRET_KEY` | 新隨機字串 | 可與 V1 不同 |
| `APP_ADMIN_USER` | 同 V1 | |
| `APP_ADMIN_PASSWORD` | 同 V1 或另設 | |
| `APP_LOGIN_USER` | `qs` | |
| `APP_LOGIN_PASSWORD` | 同 V1 或另設 | |
| `RESTORE_TOKEN` | 同 V1 或另設 | Settings 還原 DB 用 |
| `AUTH_SESSION_DAYS` | 同 V1 | 可選 |
| `AUTH_IDLE_MINUTES` | 同 V1 | 可選 |

**不要**設 `DATA_DIR`（容器內 Dockerfile 已固定 `/data`）。

---

## Step 5 — 域名

1. Service → **Networking** → **Generate Domain** 或綁自訂域
2. 建議：`ossys-v2.zeabur.app`（或 Zeabur 自動子域）
3. 記下 URL 供 QS 試用

---

## Step 6 — 驗收

部署完成後（約 1–3 分鐘）：

```http
GET https://<你的-v2-域名>/api/system/status
```

預期：

```json
{
  "app_version": "v2-20260828-baseline",
  "deployment_tier": "v2",
  "deployment_label": "V2 試用環境",
  "volume_mounted": true
}
```

瀏覽器登入後，Topbar 右側應見 **V2 試用環境** 橙色 badge。

---

## Step 7 — 初始化資料（擇一）

| 方式 | 做法 |
|------|------|
| 複製 V1 資料 | V1 備份 `qs_system.db` → V2 Settings 上傳還原（需 RESTORE_TOKEN） |
| 本機腳本 | 改 `OSSYS_URL=https://<v2域名>` 執行 `scripts/push_db_to_zeabur.ps1` |
| 空庫 | 匯入 Payment / Master List Excel 測試 |

---

## 常見錯誤

| 現象 | 原因 | 修正 |
|------|------|------|
| V2 顯示 V1 版本號 | 分支仍為 `main` | Settings 改 `v2/portfolio` 並 Redeploy |
| 與 V1 資料混在一起 | 共用 Volume | 新建 Volume 掛 `/data` |
| 無 V2 badge | 未設 `DEPLOYMENT_TIER=v2` | 加 Variable 後 Redeploy |
| 404 / 建置失敗 | Dockerfile 路徑 | 確認 Root Directory 為 repo 根目錄 |

---

## 完成後請記錄

| 項目 | 值 |
|------|-----|
| V2 URL | **https://ossys-v2.zeabur.app** |
| Zeabur Service 名 | ossys-v2（請與 Dashboard 核對） |
| Volume 名 | 獨立 Volume → `/data` |
| 首次部署 | 2026-08-28 |
| 資料初始化 | 2026-08-28 — 自 V1 本機 DB 還原（34 項目、199 付款、32 uploads） |

### 一鍵同步（本機 → V2）

在 **V1 目錄** `OSsysCU`（需 `.env` 含 `APP_ADMIN_PASSWORD`）：

```powershell
python scripts/push_db_to_v2.py
python scripts/push_uploads_to_v2.py
```
