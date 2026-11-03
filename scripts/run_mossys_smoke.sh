#!/bin/bash
# 在阿里云宿主机运行：把 smoke 脚本拷进 ossys 容器并执行
set -euo pipefail
REPO="${REPO:-/opt/ossys}"
SCRIPT="$REPO/scripts/mossys_load_smoke.py"
CONTAINER="${CONTAINER:-ossys}"
DEST="/tmp/mossys_load_smoke.py"

if [ ! -f "$SCRIPT" ]; then
  echo "找不到 $SCRIPT"
  echo "请 cd $REPO && sudo git fetch origin v2/portfolio && sudo git reset --hard origin/v2/portfolio"
  exit 1
fi

SUDO=
[ "$(id -u)" -ne 0 ] && SUDO=sudo

$SUDO docker cp "$SCRIPT" "$CONTAINER:$DEST"
exec $SUDO docker exec "$CONTAINER" python3 "$DEST" "${@:-https://mossys.xyz}"
