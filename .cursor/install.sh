#!/usr/bin/env bash
# Idempotent Cloud Agent setup for OSsysCU (Flask + SQLite QS payment system).
set -euo pipefail

cd "$(dirname "$0")/.."

# System libraries: OCR (opencv-python / onnxruntime), image handling (Pillow),
# and the Chinese font ReportLab embeds into generated PDFs.
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  python3-venv \
  libgomp1 \
  libglib2.0-0 \
  libsm6 \
  libxext6 \
  libxrender1 \
  fonts-wqy-zenhei

# Python virtualenv + pinned dependencies.
python3 -m venv .venv
# shellcheck disable=SC1091
. .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
