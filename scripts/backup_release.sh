#!/usr/bin/env bash
# OSsysCU 完整版本備份腳本（Linux / macOS / Git Bash）
# 用法: ./scripts/backup_release.sh [輸出目錄]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

get_version() {
  if [[ -f VERSION ]]; then
    tr -d '\r\n' < VERSION
  else
    grep -oP "APP_VERSION\s*=\s*'\K[^']+" startup.py | head -1
  fi
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

DB_COPIED=false
for db in "$REPO_ROOT/qs_system.db" "$REPO_ROOT/data/qs_system.db" "${DATA_DIR:-}/qs_system.db"; do
  if [[ -f "$db" ]]; then
    cp "$db" "$DEST_DIR/qs_system.db"
    DB_COPIED=true
    break
  fi
done

if [[ -d "$REPO_ROOT/uploads" ]]; then
  UPLOAD_SIZE=$(du -sk "$REPO_ROOT/uploads" 2>/dev/null | cut -f1 || echo 999999)
  if [[ "$UPLOAD_SIZE" -lt 204800 ]]; then
    cp -r "$REPO_ROOT/uploads" "$DEST_DIR/uploads"
  fi
fi

cat > "$DEST_DIR/MANIFEST.json" <<EOF
{
  "app_name": "OSsysCU",
  "version": "$VERSION",
  "git_commit": "$COMMIT",
  "git_branch": "$BRANCH",
  "backup_time": "$(date -Iseconds)",
  "db_included": $DB_COPIED,
  "production": "https://ossys.zeabur.app"
}
EOF

FINAL_ZIP="$OUT_DIR/${FOLDER_NAME}.zip"
rm -f "$FINAL_ZIP"
(cd "$DEST_DIR" && zip -rq "$FINAL_ZIP" .)

echo ""
echo "=== OSsysCU 備份完成 ==="
echo "版本:    $VERSION"
echo "Commit:  $COMMIT_SHORT ($BRANCH)"
echo "資料夾:  $DEST_DIR"
echo "壓縮檔:  $FINAL_ZIP"
echo "含 DB:   $DB_COPIED"
echo ""
