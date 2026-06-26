# OSsysCU 發行基線

## 目前穩定版

| 項目 | 值 |
|------|-----|
| **版本** | `2026-06-08-fix-project-payment-progress` |
| **Git 標籤** | `release/2026-06-08` |
| **生產環境** | https://ossys.zeabur.app |
| **核對** | `GET /api/system/status` → `app_version` |

## 本基線功能摘要

- QS 付款管理：判項、付款登記、糧期、OCR、財務報表
- QS 匯報表 PDF（A4、繁中嵌入字型）
- Light / Dark 主題
- 雙語項目名稱、香港 SME QS 術語
- Excel 匯入／同步（Payment Status Table）
- 工程項目付款進度修復（正確累計已付）

## 備份方式

### 1. 程式碼快照（建議每次大改前）

```powershell
.\scripts\backup_release.ps1
```

輸出目錄預設：`..\OSsysCU_releases\`（專案上一層，不進 git）

內容：`source.zip`（git 追蹤檔案）+ `MANIFEST.json` + 本機 `qs_system.db`（若存在）

### 2. Git 標籤

```bash
git tag -l "release/*"
git show release/2026-06-08
```

### 3. 生產資料庫

Zeabur：下載 Volume 內 `/data/qs_system.db`，或透過 `/api/system/restore-db` 流程備份。

## 版本號規則

1. 單一來源：`startup.py` → `APP_VERSION`
2. 同步更新：`VERSION`（純文字）、`CHANGELOG.md`、`RELEASE.md`（大版本時）
3. 發行後打 git tag：`release/YYYY-MM-DD` 或 `release/YYYY-MM-DD-簡述`

## 還原本基線程式碼

```bash
git checkout release/2026-06-08
```

或從 `OSsysCU_releases` 資料夾解壓對應時間戳的 zip。
