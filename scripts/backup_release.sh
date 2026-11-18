#!/usr/bin/env bash
# OSsysCU 完整版本備份腳本（Linux / macOS / Git Bash）
# 用法:
#   ./scripts/backup_release.sh [輸出目錄]
#   INCLUDE_PRODUCTION=1 ./scripts/backup_release.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
MAX_UPLOAD_MB="${MAX_UPLOAD_MB:-500}"

get_version() {
  if [[ -f VERSION ]]; then
    tr -d '\r\n' < VERSION
  else
    grep -oP "APP_VERSION\s*=\s*'\K[^']+" startup.py | head -1
  fi
}

resolve_local_data_dir() {
  if [[ -n "${DATA_DIR:-}" && -d "$DATA_DIR" ]]; then
    echo "$DATA_DIR"
    return
  fi
  if [[ -d "$REPO_ROOT/_data" ]]; then
    echo "$REPO_ROOT/_data"
    return
  fi
  echo "$REPO_ROOT"
}

best_db_path() {
  local best="" best_size=0
  local data_root
  data_root="$(resolve_local_data_dir)"
  local candidates=(
    "$data_root/qs_system.db"
    "$REPO_ROOT/_data/qs_system.db"
    "$REPO_ROOT/data/qs_system.db"
    "$REPO_ROOT/qs_system.db"
  )
  local db
  for db in "${candidates[@]}"; do
    [[ -f "$db" ]] || continue
    local sz
    sz="$(stat -c%s "$db" 2>/dev/null || stat -f%z "$db")"
    if [[ "$sz" -gt "$best_size" ]]; then
      best="$db"
      best_size="$sz"
    fi
  done
  echo "$best"
}

copy_uploads_if_small() {
  local src="$1" dest_name="$2" dest_dir="$3"
  [[ -d "$src" ]] || return 1
  local kb
  kb="$(du -sk "$src" 2>/dev/null | cut -f1 || echo 9999999)"
  if [[ "$kb" -gt $((MAX_UPLOAD_MB * 1024)) ]]; then
    echo "略過 $dest_name：超過 ${MAX_UPLOAD_MB}MB" >&2
    return 1
  fi
  cp -r "$src" "$dest_dir/$dest_name"
  return 0
}

VERSION="$(get_version)"
COMMIT="$(git rev-parse HEAD)"
COMMIT_SHORT="$(git rev-parse --short HEAD)"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUT_DIR="${1:-$(dirname "$REPO_ROOT")/OSsysCU_releases}"
mkdir -p "$OUT_DIR"

FOLDER_NAME="OSsysCU_${VERSION}_${TIMESTAMP}_${COMMIT_SHORT}"
DEST_DIR="$OUT_DIR/$FOLDER_NAME"
mkdir -p "$DEST_DIR"

git archive --format=zip -o "$DEST_DIR/source.zip" HEAD

DB_SOURCE=""
DB_COPIED=false
if db="$(best_db_path)"; [[ -n "$db" ]]; then
  cp "$db" "$DEST_DIR/qs_system_local.db"
  DB_COPIED=true
  DB_SOURCE="$db"
fi

LOCAL_DATA="$(resolve_local_data_dir)"
UPLOADS_LOCAL=false
if copy_uploads_if_small "${LOCAL_DATA}/uploads" "uploads_local" "$DEST_DIR"; then
  UPLOADS_LOCAL=true
elif [[ -d "$REPO_ROOT/uploads" ]] && copy_uploads_if_small "$REPO_ROOT/uploads" "uploads_local" "$DEST_DIR"; then
  UPLOADS_LOCAL=true
fi

PROD_DB=false
PROD_UP=false
if [[ "${INCLUDE_PRODUCTION:-}" == "1" ]]; then
  KEY="${HOME}/.ssh/aliyun-ossys"
  if [[ -f "$KEY" ]]; then
    if scp -i "$KEY" "admin@43.103.44.4:/data/qs_system.db" "$DEST_DIR/qs_system_mossys.db"; then
      PROD_DB=true
    fi
    TMP="$(mktemp -d)"
    if scp -r -i "$KEY" "admin@43.103.44.4:/data/uploads" "$TMP/"; then
      if copy_uploads_if_small "$TMP/uploads" "uploads_mossys" "$DEST_DIR"; then
        PROD_UP=true
      fi
    fi
    rm -rf "$TMP"
  else
    echo "找不到 ${KEY}，略過生產備份" >&2
  fi
fi

cat > "$DEST_DIR/MANIFEST.json" <<EOF
{
  "app_name": "OSsysCU",
  "version": "$VERSION",
  "git_commit": "$COMMIT",
  "git_branch": "$BRANCH",
  "backup_time": "$(date -Iseconds)",
  "db_local": $( [[ "$DB_COPIED" == true ]] && echo '"qs_system_local.db"' || echo null ),
  "db_local_source": "$DB_SOURCE",
  "uploads_local": $UPLOADS_LOCAL,
  "production": "https://mossys.xyz",
  "production_db": $PROD_DB,
  "production_uploads": $PROD_UP
}
EOF

FINAL_ZIP="$OUT_DIR/${FOLDER_NAME}.zip"
rm -f "$FINAL_ZIP"
if command -v tar >/dev/null 2>&1; then
  tar -a -cf "$FINAL_ZIP" -C "$OUT_DIR" "$FOLDER_NAME"
else
  (cd "$DEST_DIR" && zip -rq "$FINAL_ZIP" .)
fi

echo ""
echo "=== OSsysCU 備份完成 ==="
echo "版本:    $VERSION"
echo "Commit:  $COMMIT_SHORT ($BRANCH)"
echo "資料夾:  $DEST_DIR"
echo "壓縮檔:  $FINAL_ZIP"
echo "本機 DB: ${DB_SOURCE:-（無）}"
echo ""