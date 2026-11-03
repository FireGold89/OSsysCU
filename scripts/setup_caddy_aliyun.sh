#!/bin/bash
# 阿里云香港轻量：Caddy 自动 HTTPS，反代本机 ossys 容器
# 用法: sudo DOMAIN=qs.example.com bash setup_caddy_aliyun.sh
# 前提: 域名 A 记录已指向本机公网 IP；防火墙已放行 80、443
set -euo pipefail

DOMAIN="${DOMAIN:-}"
EMAIL="${EMAIL:-}"  # 可选，Let's Encrypt 到期提醒
ENV_FILE="${ENV_FILE:-/opt/ossys.env}"
CADDY_DIR="${CADDY_DIR:-/opt/caddy}"
IMAGE="${CADDY_IMAGE:-caddy:2-alpine}"
CONTAINER_APP="${CONTAINER_APP:-ossys}"
CONTAINER_CADDY="${CONTAINER_CADDY:-caddy}"

if [ "$(id -u)" -ne 0 ]; then
  echo "请用 sudo 运行" >&2
  exit 1
fi
if [ -z "$DOMAIN" ]; then
  echo "请设置 DOMAIN，例如: sudo DOMAIN=qs.yourcompany.com bash $0" >&2
  exit 1
fi

mkdir -p "$CADDY_DIR/data" "$CADDY_DIR/config"

if [ -n "$EMAIL" ]; then
  GLOBAL="{ email {$EMAIL} }"
else
  GLOBAL=""
fi

cat > "$CADDY_DIR/Caddyfile" <<EOF
${GLOBAL}
{$DOMAIN} {
    encode gzip
    reverse_proxy 127.0.0.1:8080
}
EOF

if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  docker pull "$IMAGE"
fi

if docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER_APP"; then
  docker rm -f "$CONTAINER_APP"
fi
if [ ! -f "$ENV_FILE" ]; then
  echo "找不到 $ENV_FILE" >&2
  exit 1
fi
grep -q '^SESSION_COOKIE_SECURE=' "$ENV_FILE" \
  && sed -i 's/^SESSION_COOKIE_SECURE=.*/SESSION_COOKIE_SECURE=1/' "$ENV_FILE" \
  || echo 'SESSION_COOKIE_SECURE=1' >> "$ENV_FILE"

docker run -d --name "$CONTAINER_APP" --restart unless-stopped \
  -p 127.0.0.1:8080:8080 \
  -v /data:/data \
  --env-file "$ENV_FILE" \
  ossys-v2

docker rm -f "$CONTAINER_CADDY" 2>/dev/null || true
docker run -d --name "$CONTAINER_CADDY" --restart unless-stopped \
  --network host \
  -v "$CADDY_DIR/Caddyfile:/etc/caddy/Caddyfile:ro" \
  -v "$CADDY_DIR/data:/data" \
  -v "$CADDY_DIR/config:/config" \
  "$IMAGE"

sleep 3
echo "--- Caddy 日志（最近）---"
docker logs "$CONTAINER_CADDY" --tail 15 2>&1 || true
echo ""
echo "完成。请用浏览器打开: https://${DOMAIN}/"
echo "（DNS 未生效时证书申请会失败，请确认 A 记录指向本机公网 IP）"
echo "可关闭防火墙公网 8080，仅保留 22/80/443。"
