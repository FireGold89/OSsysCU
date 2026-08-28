# OSsysCU V2 本機啟動（與 V1 並行：埠 5001 + 獨立 _data/）
# 用法:
#   .\scripts\run_local_v2.ps1
#   .\scripts\run_local_v2.ps1 -CopyDbFromV1
param(
    [switch]$CopyDbFromV1,
    [switch]$SkipDbCopy
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $Root

$DataDir = Join-Path $Root "_data"
$Uploads = Join-Path $DataDir "uploads"
New-Item -ItemType Directory -Force -Path $DataDir, $Uploads | Out-Null

$V1Root = Join-Path (Split-Path $Root -Parent) "OSsysCU"
$V1Db = Join-Path $V1Root "qs_system.db"
$V1Env = Join-Path $V1Root ".env"
$V2Db = Join-Path $DataDir "qs_system.db"
$V2Env = Join-Path $Root "v2.env"
$V2EnvExample = Join-Path $Root "v2.env.example"

# 首次：若無 v2.env，從 V1 .env 複製（本機試用較省事）
if (-not (Test-Path $V2Env)) {
    if (Test-Path $V1Env) {
        Copy-Item $V1Env $V2Env -Force
        Write-Host "[V2] 已從 V1 複製 .env → v2.env（登入帳密與 V1 相同）"
    } elseif (Test-Path $V2EnvExample) {
        Copy-Item $V2EnvExample $V2Env -Force
        Write-Host "[V2] 已建立 v2.env — 請編輯 SECRET_KEY 與登入密碼後再跑"
    } else {
        Write-Host "[V2] 警告: 找不到 v2.env，將以無登入模式啟動（僅本機）"
    }
}

# 首次：若 V2 空庫且 V1 有 DB，自動複製（可用 -SkipDbCopy 略過）
if (-not $SkipDbCopy) {
    if ($CopyDbFromV1 -or (-not (Test-Path $V2Db) -and (Test-Path $V1Db))) {
        if (-not (Test-Path $V1Db)) {
            Write-Error "找不到 V1 資料庫: $V1Db"
        }
        Copy-Item $V1Db $V2Db -Force
        Write-Host "[V2] 已從 V1 複製 qs_system.db → _data/"
        $V1Uploads = Join-Path $V1Root "uploads"
        if (Test-Path $V1Uploads) {
            Copy-Item (Join-Path $V1Uploads "*") $Uploads -Force -ErrorAction SilentlyContinue
            $n = (Get-ChildItem $Uploads -File -ErrorAction SilentlyContinue).Count
            Write-Host "[V2] 已同步 uploads/ ($n 個檔案)"
        }
    }
}

# 埠占用檢查
$inUse = Get-NetTCPConnection -LocalPort 5001 -State Listen -ErrorAction SilentlyContinue
if ($inUse) {
    Write-Host "[V2] 埠 5001 已被占用 (PID $($inUse[0].OwningProcess))。"
    Write-Host "     若已是 V2，直接開: http://localhost:5001"
    Write-Host "     否則關閉該程序後再執行本腳本。"
    exit 1
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "找不到 python。請確認已安裝 Python 3 並在 PATH 中。"
}

$env:DATA_DIR = $DataDir
$env:PORT = "5001"
$env:DEPLOYMENT_TIER = "v2"
$env:PYTHONIOENCODING = "utf-8"

Write-Host ""
Write-Host "========================================"
Write-Host "  OSsysCU V2 本機"
Write-Host "  http://localhost:5001"
Write-Host "  資料: $DataDir"
Write-Host "  請保持此視窗開啟；Ctrl+C 停止"
Write-Host "========================================"
Write-Host ""

python app.py
