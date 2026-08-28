# OSsysCU V2 本機啟動（與 V1 並行：不同埠 + 獨立資料目錄）
# 用法: .\scripts\run_local_v2.ps1
#       .\scripts\run_local_v2.ps1 -CopyDbFromV1   # 首次從 V1 複製 qs_system.db
param(
    [switch]$CopyDbFromV1
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

$DataDir = Join-Path $Root "_data"
$Uploads = Join-Path $DataDir "uploads"
New-Item -ItemType Directory -Force -Path $DataDir, $Uploads | Out-Null

$V1Root = Join-Path (Split-Path $Root -Parent) "OSsysCU"
$V1Db = Join-Path $V1Root "qs_system.db"
$V2Db = Join-Path $DataDir "qs_system.db"

if ($CopyDbFromV1) {
    if (-not (Test-Path $V1Db)) {
        Write-Error "找不到 V1 資料庫: $V1Db"
    }
    Copy-Item $V1Db $V2Db -Force
    Write-Host "[V2] 已從 V1 複製 qs_system.db"
} elseif (-not (Test-Path $V2Db)) {
    Write-Host "[V2] _data/qs_system.db 不存在 — 將以空庫啟動（可選 -CopyDbFromV1 複製 V1）"
}

$env:DATA_DIR = $DataDir
$env:PORT = "5001"
$env:DEPLOYMENT_TIER = "v2"

if (Test-Path (Join-Path $Root "v2.env")) {
    Write-Host "[V2] 已設 DATA_DIR=$DataDir PORT=5001 — 登入帳密見 v2.env（若已建立）"
} else {
    Write-Host "[V2] 提示: 複製 v2.env.example → v2.env 並設定 SECRET_KEY / 登入密碼"
}

Write-Host "[V2] http://localhost:5001  ·  tier=v2  ·  APP_VERSION 見 startup.py"
python app.py
