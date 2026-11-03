#!/bin/bash
# 阿里云香港轻量 + Docker 镜像：在 Workbench 粘贴运行（需先准备 /opt/ossys.env）
set -euo pipefail

ENV_FILE="${ENV_FILE:-/opt/ossys.env}"
REPO_DIR="${REPO_DIR:-/opt/ossys}"
BRANCH="${BRANCH:-v2/portfolio}"
IMAGE_NAME="${IMAGE_NAME:-ossys-v2}"
CONTAINER_NAME="${CONTAINER_NAME:-ossys}"

if [ "$(id -u)" -ne 0 ]; then
  SUDO=sudo
else
  SUDO=
fi

$SUDO mkdir -p /data/uploads
chmod 755 /data 2>/dev/null || $SUDO chmod 755 /data

if [ ! -f "$ENV_FILE" ]; then
  echo "缺少 $ENV_FILE"
  echo "请先创建（勿把密码贴进聊天）："
  echo "  sudo nano $ENV_FILE"
  echo "内容参考仓库 v2.env.example，并加上 PORT=8080、DEPLOYMENT_TIER=v2"
  exit 1
fi

if ! command -v git >/dev/null 2>&1; then
  $SUDO apt-get update -qq
  $SUDO apt-get install -y git
fi

if [ ! -d "$REPO_DIR/.git" ]; then
  $SUDO mkdir -p "$(dirname "$REPO_DIR")"
  $SUDO git clone -b "$BRANCH" https://github.com/FireGold89/OSsysCU.git "$REPO_DIR"
else
  cd "$REPO_DIR"
  $SUDO git fetch origin "$BRANCH"
  $SUDO git checkout "$BRANCH"
  # 与 GitHub 完全一致，避免服务器本地改动导致 pull 显示已最新却未拉到新 commit
  $SUDO git reset --hard "origin/$BRANCH"
fi

cd "$REPO_DIR"
$SUDO docker build -t "$IMAGE_NAME" .

if $SUDO docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER_NAME"; then
  $SUDO docker rm -f "$CONTAINER_NAME"
fi

$SUDO docker run -d --name "$CONTAINER_NAME" --restart unless-stopped \
  -p 127.0.0.1:8080:8080 \
  -v /data:/data \
  --env-file "$ENV_FILE" \
  "$IMAGE_NAME"

sleep 2
echo "Git: $(git -C "$REPO_DIR" log -1 --oneline)"
curl -s "http://127.0.0.1:8080/api/system/status" || true
echo
code="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/ || true)"
echo "本机 HTTP 状态: ${code:-failed}（生产请用 https://mossys.xyz）"
$SUDO docker logs "$CONTAINER_NAME" --tail 20
