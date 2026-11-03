# mossys.xyz 运维速查

生产：https://mossys.xyz · 服务器：阿里云香港轻量 · IP：`43.103.44.4`

## 日常部署（代码更新）

本机 push `v2/portfolio` 后，SSH：

```bash
cd /opt/ossys
sudo git fetch origin v2/portfolio
sudo git checkout v2/portfolio
sudo git pull --ff-only origin v2/portfolio
sudo docker build -t ossys-v2 .
sudo docker rm -f ossys
sudo docker run -d --name ossys --restart unless-stopped \
  -p 127.0.0.1:8080:8080 \
  -v /data:/data \
  --env-file /opt/ossys.env \
  ossys-v2
```

验收：`curl -s https://mossys.xyz/api/system/status` → `app_version`、`auth_enabled: true`。

## 环境变量

- 路径：`/opt/ossys.env`（`chmod 600`，勿 commit）
- HTTPS 生产：`SESSION_COOKIE_SECURE=1`
- 改 env 后必须 `docker rm` + `docker run`（不要只 restart）

## 备份

```bash
# 本机 PowerShell
scp -i $env:USERPROFILE\.ssh\aliyun-ossys admin@43.103.44.4:/data/qs_system.db .\Backup\
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
