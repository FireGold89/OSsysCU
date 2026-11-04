#!/bin/bash
# 修正 scp/tar 產生的 PaxHeaders.0（在 mossys 上 sudo 執行）
ISO_ROOT="${ISO_ROOT:-/data/uploads/iso}"
for proj in "$ISO_ROOT"/*/; do
  pax="${proj}PaxHeaders.0"
  if [ -d "$pax" ]; then
    for f in "$pax"/*; do
      [ -f "$f" ] || continue
      base="$(basename "$f")"
      dest="${proj}${base}"
      if [ ! -f "$dest" ]; then
        cp -a "$f" "$dest"
      fi
    done
    rm -rf "$pax"
    echo "flattened: $proj"
  fi
done
echo "done under $ISO_ROOT"
