# V2 並行環境（Staging / 試用）

> **V1 Production**：`main` → https://ossys.zeabur.app  
> **V2 Staging**：`v2/portfolio` → 本機 `:5001` 或 Zeabur 第二 Service（待建）

---

## 架構

| | V1 | V2 |
|--|----|----|
| Git 分支 | `main` | `v2/portfolio` |
| 本機目錄 | `OSsysCU` | `OSsysCU-v2`（git worktree） |
| 本機埠 | 5000（預設） | **5001** |
| 本機資料 | `qs_system.db` + `uploads/` | **`_data/`**（獨立 Volume） |
| APP_VERSION | `20260827-*` | `v2-*` |
| UI 標識 | 無 | Topbar **V2 試用環境** badge |
| 核對 API | `GET /api/system/status` | 同上 + `deployment_tier` |

**原則：** V2 改動不 merge 到 `main` 前，生產不受影響；兩邊 DB **不可共用**。

---

## 本機 V2 快速啟動

### 1. 目錄（已建立）

```text
Documents/Pro/
  OSsysCU/          ← V1，分支 main
  OSsysCU-v2/       ← V2，分支 v2/portfolio
```

查看 worktree：

```powershell
git -C OSsysCU worktree list
```

### 2. 環境變數

```powershell
cd OSsysCU-v2
copy v2.env.example v2.env
# 編輯 v2.env：SECRET_KEY、登入密碼
```

### 3. 啟動

```powershell
cd OSsysCU-v2
.\scripts\run_local_v2.ps1
```

首次若要比對 V1 真實資料：

```powershell
.\scripts\run_local_v2.ps1 -CopyDbFromV1
```

瀏覽：**http://localhost:5001**（V1 仍用 http://localhost:5000）

### 4. 核對版本

```http
GET http://localhost:5001/api/system/status
```

應見：`app_version` 以 `v2-` 開頭、`deployment_tier`: `v2`。

---

## Zeabur 第二套（Staging）

1. Zeabur 新建 **Service**（同一 GitHub repo `FireGold89/OSsysCU`）
2. **部署分支**：`v2/portfolio`（勿用 `main`）
3. **Volume**：新建獨立 Volume 掛載 `/data`
4. **Variables**（複製 V1，另確認）：
   - `DEPLOYMENT_TIER=v2`
   - `SECRET_KEY`（可與 V1 不同）
   - 登入帳密、可選 `RESTORE_TOKEN`
5. 自訂域名例：`ossys-v2.zeabur.app`
6. **資料初始化**：Settings 上傳 V1 備份之 `qs_system.db`，或空庫 + 匯入 Ref Excel

推送 V2 分支才會觸發 V2 重建；**push `main` 不影響 V2 Service**。

---

## 開發流程

```
1. 在 OSsysCU-v2 開發 Portfolio / 大功能
2. commit 到 v2/portfolio
3. push → V2 Zeabur 自動部署 → QS 試用
4. 試穩後 merge v2/portfolio → main → V1 上線
```

V1 緊急修復：只在 `OSsysCU`（main）改，cherry-pick 到 `v2/portfolio` 如需同步。

---

## Git 標籤（V1 基線）

```bash
git tag release/v1-baseline e123caa   # 20260827-main-con-fac-pdf2
git push origin release/v1-baseline
```

---

## 相關文件

- [QS Reference Excel Overview.md](./QS%20Reference%20Excel%20Overview.md) — V2 首要功能規格來源
- [Portfolio FAC UI Spec.md](./Portfolio%20FAC%20UI%20Spec.md)
- [RELEASE.md](../RELEASE.md) — V1 發行基線

---

## 常見問題

**Q：V2 改 DB schema 會否弄壞 V1？**  
A：不會，只要 V1 仍用各自 Volume／本機 `qs_system.db`。Merge 到 main 前要在 V1 資料上測 migration。

**Q：能否 V1/V2 共用 .env？**  
A：不建議。V2 用 `v2.env`；`run_local_v2.ps1` 會設 `DATA_DIR` 與 `PORT`。

**Q：如何移除 worktree？**  
A：`git worktree remove ../OSsysCU-v2`（先確保無未 commit 重要變更）
