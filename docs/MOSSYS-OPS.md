# mossys.xyz 运维速查

生产：**https://mossys.xyz**（阿里云香港轻量 · `43.103.44.4`）。V2 发版以本环境为准，勿与其他环境共用同一 SQLite。

## 推荐流程（本机 → GitHub → 阿里云）

1. 本机：在 `v2/portfolio` 改代码 → 更新 `startup.py` / `VERSION` / `CHANGELOG.md`（有发版时）→ **commit + push**。
2. 阿里云：拉齐 GitHub 并重建容器（见下）。**不要**覆盖 `/opt/ossys.env` 或 `/data`。
3. 验收：`curl -s https://mossys.xyz/api/system/status` → `app_version`、`auth_enabled: true`。

## 日常部署（代码更新）

**一键（服务器 Workbench / SSH）：**

```bash
sudo bash /opt/ossys/scripts/deploy_aliyun_hk.sh
```

**本机 PowerShell（push 后）：**

```powershell
ssh -i $env:USERPROFILE\.ssh\aliyun-ossys admin@43.103.44.4 "sudo bash /opt/ossys/scripts/deploy_aliyun_hk.sh"
```

**手动等价命令**（须 `fetch` + `reset --hard`，勿只 `pull` 而不 fetch，否则可能仍停在旧 commit）：

```bash
cd /opt/ossys
sudo git fetch origin v2/portfolio
sudo git checkout v2/portfolio
sudo git reset --hard origin/v2/portfolio
sudo docker build -t ossys-v2 .
sudo docker rm -f ossys
sudo docker run -d --name ossys --restart unless-stopped \
  -p 127.0.0.1:8080:8080 \
  -v /data:/data \
  --env-file /opt/ossys.env \
  ossys-v2
```

## 环境变量

- 路径：`/opt/ossys.env`（`chmod 600`，勿 commit）
- HTTPS 生产：`SESSION_COOKIE_SECURE=1`
- 改 env 后必须 `docker rm` + `docker run`（不要只 restart）

## 备份

```bash
# 本机 PowerShell
scp -i $env:USERPROFILE\.ssh\aliyun-ossys admin@43.103.44.4:/data/qs_system.db .\Backup\
```

## uploads 目錄說明

**路徑規則（v2-20261104 起）**：`{功能}/{項目或_general}/{前綴_原檔名_YYYYMMDD}.ext`

| 第一層 `功能/` | 對應畫面／API | 第二層 |
|----------------|---------------|--------|
| `iso/` | ISO 文件登記 | `{MS_Q1161_25_jc}/` |
| `ocr/` | OCR、付款掃描 | `{項目}/` 或 `_general/` |
| `quotations/` | 分判 · 上傳報價 PDF | `{項目}/` |
| `main-fac/` | 主包 FAC 附件 | `{項目}/` |
| `sc-vo/` | 分判 VO 附件 | `{項目}/` |
| `ip/` | 糧期支票／IP 附件 | `{項目}/` |
| `imports/` | Excel 匯入暫存 | `_general/`（檔名前綴 portfolio、master-list 等） |
| `misc/` | `/api/files/upload` | `_general/` |

**根目錄 32 位 hex `.pdf`**：歸類為 **legacy-root**（舊 OCR 等）；DB 仍可能引用，**勿批量刪**。

**不寫 uploads 的「製作」**：QS 匯報、會簽表、Main/SC FAC 預覽 PDF、糧期計算書匯出等 → 僅 HTTP 下載／瀏覽器 blob；完整清單見 `upload_naming.GENERATED_EXPORTS` 或 **/admin**「uploads 分類」頁尾。

**本機／SSH 統計**：

```bash
python scripts/uploads_inventory.py
# 或指定目錄：python scripts/uploads_inventory.py /data/uploads
```

## ISO / 附件遷移（預覽 404「文件不在伺服器」）

資料庫只記 **路徑**；實體檔在 **`/data/uploads/`**，ISO 在 **`/data/uploads/iso/{項目編號}/`**。只還原 `qs_system.db`、未拷貝 `iso/` 子目錄時，畫面仍顯示檔名但預覽會 404。

**新上傳命名（v2-20261104 起）**：`{原檔主檔名}_{YYYYMMDD}.pdf`（同日同名再加 `_8位hex`）。舊資料多為 `{槽位中文}_{日期}_{hex}` 或遷移備份缺中文前綴；預覽 API 會依 `_xxxxxxxx` 尾碼對齊。

**刪除附件（v2-20261104-iso-delete-disk 起）**：畫面按刪除會一併移除磁碟檔。若先前已刪 DB 但檔仍在（舊版行為），可 SSH 手動刪，或對照 DB：

```bash
# 列出某項目 iso 目錄內檔案（例 MS/Q1970/24 → MS_Q1970_24_jc）
sudo ls -la /data/uploads/iso/MS_Q1970_24_jc/
```

**伺服器自查（Workbench / SSH）：**

```bash
sudo ls /data/uploads/iso
# 某項目例：MS/Q1161/25 → 目錄名多為底線版，如 MS_Q1161_25
sudo find /data/uploads/iso -type f | head
```

**做法 A — 本機有完整 `uploads`（含 `iso/`）**

1. 部署含新版 `restore-uploads` 的程式（保留 zip 內子目錄）。
2. PowerShell（`.env` 設 `RESTORE_TOKEN`，與 mossys 相同）：

```powershell
cd C:\Users\hiufung_lau\Documents\Pro\OSsysCU-v2
python scripts\push_uploads_to_prod.py
```

3. 看輸出 `synced` 應 > 0；再開 ISO 預覽。

**做法 B — 直接 scp 目錄（大檔、略過 zip）**

PowerShell **勿用變數名 `$host`**（系統保留），請用 `$remote` 等：

```powershell
$key = "$env:USERPROFILE\.ssh\aliyun-ossys"
$remote = "admin@43.103.44.4"
# 例：Zeabur 備份解壓後的 iso 路徑
$ISO = "$env:USERPROFILE\Downloads\backup-6ae94ee684ee3b8379e9ee23\data\datav2\uploads\iso"

scp -r -i $key $ISO "${remote}:/tmp/iso-restore"
ssh -i $key $remote "sudo mkdir -p /data/uploads/iso && sudo cp -a /tmp/iso-restore/iso/. /data/uploads/iso/ 2>/dev/null; sudo cp -a /tmp/iso-restore/MS_Q*. /data/uploads/iso/ 2>/dev/null; sudo cp -a /tmp/iso-restore/. /data/uploads/iso/"
ssh -i $key $remote "sudo find /data/uploads/iso/MS_Q1161_25_jc -type f | head"
```

若 `scp` 上傳後 `/tmp/iso-restore` 底下直接是 `MS_Q1161_25_jc` 等資料夾，第三行可簡化為：

```bash
sudo cp -a /tmp/iso-restore/. /data/uploads/iso/
```

舊環境備份若只有 zip，解壓後須保留 **`iso/項目編號/*.pdf`** 結構，不要只拷貝 uploads 根目錄的散檔。

**仍 404 時**：對照 DB 內 `file_path`（例 `iso/MS_Q1161_25/xxx.pdf`）與磁碟檔名是否一致；缺檔只能自舊站再拷或於 ISO 頁重新上傳。

## API 压测（可重复）

脚本在 Git 仓库 **`scripts/mossys_load_smoke.py`**（宿主机 `/opt/ossys/scripts/…`）。**容器里没有 `/opt/ossys`**（镜像只有 `/app`，未打包 scripts），须先 **`docker cp` 进容器** 再 `docker exec` 执行。脚本在容器内用 env 登入，模拟首屏／切项目／并行 GET；单请求 **≥22s** 会标 `slow`。**不能代替浏览器点 UI**。

**方法二 — 阿里云 Workbench / SSH（推荐）**

```bash
# 一键（需仓库已 pull 到含 mossys_load_smoke.py 的 commit）
sudo bash /opt/ossys/scripts/run_mossys_smoke.sh
```

或手动：

```bash
sudo docker cp /opt/ossys/scripts/mossys_load_smoke.py ossys:/tmp/mossys_load_smoke.py
sudo docker exec ossys python3 /tmp/mossys_load_smoke.py https://mossys.xyz
```

若 `No such file`：在宿主机执行 `ls /opt/ossys/scripts/mossys_load_smoke.py`；没有则 `cd /opt/ossys && sudo git fetch origin v2/portfolio && sudo git reset --hard origin/v2/portfolio`。

可同时测本机 8080 与 HTTPS：

```bash
sudo docker exec ossys python3 /tmp/mossys_load_smoke.py http://127.0.0.1:8080 https://mossys.xyz
```

期望终端输出含 **`all OK under 22s`**。

**方法一 — 本机 PowerShell**

```powershell
scp -i $env:USERPROFILE\.ssh\aliyun-ossys .\scripts\mossys_load_smoke.py admin@43.103.44.4:/tmp/
ssh -i $env:USERPROFILE\.ssh\aliyun-ossys admin@43.103.44.4 `
  "sudo docker cp /tmp/mossys_load_smoke.py ossys:/tmp/mossys_load_smoke.py && sudo docker exec ossys python3 /tmp/mossys_load_smoke.py https://mossys.xyz"
```

## 故障排查

### 网站打不开 / 502

```bash
sudo docker ps -a
sudo docker logs ossys --tail 40
sudo docker logs caddy --tail 40
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/
```

- `ossys` 不在跑 → 看 logs，常见 `/opt/ossys.env` 缺失或语法错误
- 本机 8080 正常、外网不行 → 查 Caddy、防火墙 80/443

### 登录后又回登录页

- HTTP 用 `:8080` 且 env 无 `SESSION_COOKIE_SECURE=0`（旧镜像）→ 用 **https://mossys.xyz**
- env 只有一行 → 恢复完整 `ossys.env` 并重建容器
- 浏览器清 Cookie 或无痕重试

### HTTPS 证书失败

```bash
dig +short mossys.xyz A
dig +short www.mossys.xyz A
sudo docker restart caddy
sudo docker logs caddy --tail 30
```

- 必须解析到 `43.103.44.4`；NS 须为阿里云 `*.alidns.com`
- 防火墙须放行 **80**（Let's Encrypt HTTP-01）

### Caddy

- 配置：`/opt/caddy/Caddyfile`
- 改完：`sudo docker restart caddy`

### 数据库

- 仅 `/data/qs_system.db` + `/data/uploads`；勿 NAS、勿第二台 app 共用同一 db

## 防火墙（阿里云）

建议：22、80、443；生产可关公网 8080（app 只监听 127.0.0.1:8080）。
