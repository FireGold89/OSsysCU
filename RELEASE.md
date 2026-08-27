# OSsysCU 發行基線

## 目前穩定版

| 項目 | 值 |
|------|-----|
| **APP_VERSION** | `20260827-ux-desktop` |
| **Git commit** | （見 `main` 最新） |
| **Git 標籤** | `release/2026-08-27` |
| **記錄日期** | 2026-08-27 |
| **生產環境** | https://ossys.zeabur.app |
| **核對** | `GET /api/system/status` → `app_version` |
| **完整備份** | `_releases/OSsysCU_20260827-staff-roster_20260827_120030_7080c81.zip` |

## 本基線功能摘要

- **QS管理系統**（原 QS付款管理）品牌更名
- Session 登入（admin / qs）+ 閒置自動登出（qs 60 分鐘 / admin 30 分鐘）
- 登入前不閃主介面（server redirect + auth-pending）
- 夾萬登入動畫（90° 转轮 → 微开 → 停 2 秒 → 震動 → 慢速全开）
- Settings DB 還原 UI + Zeabur push 腳本
- 項目負責人：部門／權限角色下拉（物業工程部、美博工程部、QS部、行政部、會計部）
- **桌面 UX Phase 1**：登入動畫可跳過、切項目局部 loading、報價編號顯示、Dashboard 付款鑽取、sticky 表頭、Modal Esc、閒置預警
- 既有：判項、付款登記、糧期、OCR、財務報表、QS 匯報 PDF、Light/Dark 主題

## 備份方式

### 1. 完整系統備份（含 DB + uploads）

```powershell
.\scripts\backup_release.ps1 -OutDir ".\_releases"
```

### 2. Git 標籤

```bash
git tag -l "release/*"
git show release/2026-08-27
```

### 3. 生產資料庫

Zeabur Volume `/data/qs_system.db`，或 Settings 頁上傳還原。

## 版本號規則

1. 單一來源：`startup.py` → `APP_VERSION`
2. 同步更新：`VERSION`、`CHANGELOG.md`、`RELEASE.md`（大版本時）
3. 發行後打 git tag：`release/YYYY-MM-DD`

## 還原本基線

```bash
git checkout release/2026-08-27
```

或解壓 `_releases/` 內對應 zip。

## 歷史基線

| 標籤 | APP_VERSION（約） | 日期 |
|------|-------------------|------|
| `release/2026-08-27` | `20260827-staff-roster` | 2026-08-27 |
| `release/2026-06-08` | `2026-06-08-fix-project-payment-progress` | 2026-06-08 |
