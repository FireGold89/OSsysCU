# Role Permission Matrix

> 現況：**角色欄位已建模，權限 enforce 未實作**。  
> 不含任何 Token 值或密碼欄位說明。

---

## 角色定義 `[Code]`

| 角色 ID | API label | API hint | 證據 |
|---------|-----------|----------|------|
| `qs` | QS | 報價／判項／付款（預設） | `app.py` → `staff_roles()` |
| `finance` | 財務 | 發票／支票欄位（預留） | 同上 |
| `admin` | 管理員 | 全系統設定（預留） | 同上 |
| `viewer` | 唯讀 | 僅查閱（預留） | 同上 |

常數：`STAFF_ACCESS_ROLES = ('admin', 'qs', 'finance', 'viewer')` — `database.py` L5042

預設值：新建／無效 role 降為 `'qs'` — `create_staff_member()`, `update_staff_member()`

---

## 資料模型 `[Code]`

### `staff_members` 表

| 欄 | 用途 |
|----|------|
| `code` UNIQUE | 縮寫（報價編號尾碼、MS/C person_code） |
| `name_en`, `name_zh` | 姓名 |
| `email`, `phone`, `department` | 聯絡 |
| `access_role` | 角色（上表四種） |
| `is_active` | 啟用 / 停用 |
| `notes` | 備註 |

定義：`database.py` → `_migrate_db()` staff_members CREATE

---

## API `[Code]`

| 端點 | 方法 | 行為 | 權限檢查 |
|------|------|------|----------|
| `/api/staff/roles` | GET | 回傳角色定義列表 | 無 |
| `/api/staff` | GET | 列表；可篩 `active=1`, `role=` | 無 |
| `/api/staff/<id>` | GET/PUT/DELETE | CRUD / 停用 | 無 |
| `/api/staff` | POST | 新增 | 無 |

篩選實作：`list_staff_by_access_role(active_only, access_role)` — `database.py`

**所有其他 `/api/*` 路由**：code 中無 `@require_role`、無 `before_request` 角色檢查。

---

## 前端 `[Code]`

| 行為 | 證據 |
|------|------|
| 側欄全部 nav 固定可見 | `frontend/index.html` L48–94 |
| 角色 badge 顯示「預留權限」 | `staff.js` L137–138 |
| 無 `currentUser` / `isAdmin` 判斷 | `main.js` 全檔 |
| 負責人下拉供 Projects / Master List / MS/C 共用 | `staff.js` → `StaffRoster.fillPersonSelect()`, `fillQsSelect()` |

---

## 權限矩陣（code 現況 vs 設計意圖）

| 能力 | qs | finance | admin | viewer | Code enforce |
|------|:--:|:-------:|:-----:|:------:|:------------:|
| 瀏覽全部頁面 | ✓ | ✓ | ✓ | ✓ | 無限制 [Code] |
| 改 Master List | ✓ | ✓ | ✓ | ✓ | 無限制 [Code] |
| 改付款 / 糧期 | ✓ | ✓ | ✓ | ✓ | 無限制 [Code] |
| 系統設定 / 還原 DB | ✓ | ✓ | ✓ | ✓ | 僅 restore token [Code] |
| 依角色隱藏 UI | — | — | — | — | **未實作** [Code] |
| 登入驗證 | — | — | — | — | **未實作** [Code] |

> **Inferred**（非 code enforce）：hint 文案暗示 finance 将来限財務欄、viewer 唯讀、admin 管設定；目前僅為 UI 標籤，不影響 API。

---

## 系統級保護（非角色）`[Code]`

| 端點 | 保護機制 | 證據 |
|------|----------|------|
| `POST /api/system/restore-db` | 環境變數 Token；非空庫必填 | `restore_database()` |
| `POST /api/system/restore-uploads` | Token 必填 | `restore_uploads()` |
| `POST /api/system/sync-excel` | `SYNC_TOKEN` 或 fallback `RESTORE_TOKEN` | `sync_excel_api()` |

`/api/system/status` 僅回傳 `restore_token_configured: boolean`，**不含** Token 值。

---

## person_code 跨表用法 `[Code]`

| 位置 | 用途 |
|------|------|
| `staff_members.code` | 主檔縮寫 |
| `quotation_registry.person_code` | 報價負責人 |
| `projects.person_code` | 項目負責人 |
| `sc_contract_registry.person_code` | MS/C 負責同事 |
| 報價編號尾碼 `/jy` | `master_ref.py` 解析 |

合併邏輯：`list_master_person_roster()` — 優先 `is_active=1` 的 staff 記錄。

---

## 明確未實作 `[Code]`

- Flask session / cookie 登入
- `password_hash` 或 OAuth 欄位
- `@login_required` / `@require_role` decorator
- Audit log（誰改了什麼）
- 依 `access_role` 的 API 403 回應

**文件化 defer**：`PENDING.md` L206–207「成員／登入系統」「Audit log」
