# OSsysCU 完整版本備份腳本（Windows）
# 用法: .\scripts\backup_release.ps1 [-OutDir "D:\Backups\OSsysCU"]
param(
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $RepoRoot

function Get-AppVersion {
    $versionFile = Join-Path $RepoRoot "VERSION"
    if (Test-Path $versionFile) {
        return (Get-Content $versionFile -Raw).Trim()
    }
    $line = Select-String -Path (Join-Path $RepoRoot "startup.py") -Pattern "APP_VERSION\s*=\s*'([^']+)'" |
        Select-Object -First 1
    if ($line) { return $line.Matches.Groups[1].Value }
    return "unknown"
}

function Write-FinalBackupZip {
    param(
        [Parameter(Mandatory = $true)][string]$SourceDir,
        [Parameter(Mandatory = $true)][string]$ZipPath
    )
    if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }

    $parent = Split-Path $SourceDir -Parent
    $name = Split-Path $SourceDir -Leaf

    # Prefer tar: avoids Compress-Archive file-lock on nested source.zip (Win10+)
    if (Get-Command tar -ErrorAction SilentlyContinue) {
        & tar -a -cf $ZipPath -C $parent $name
        if ($LASTEXITCODE -eq 0 -and (Test-Path $ZipPath)) { return }
        if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
    }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory($SourceDir, $ZipPath)
}

$Version = Get-AppVersion
$Commit = (git rev-parse HEAD).Trim()
$CommitShort = (git rev-parse --short HEAD).Trim()
$Branch = (git rev-parse --abbrev-ref HEAD).Trim()
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"

if (-not $OutDir) {
    $OutDir = Join-Path (Split-Path $RepoRoot -Parent) "OSsysCU_releases"
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$FolderName = "OSsysCU_${Version}_${Timestamp}_${CommitShort}"
$DestDir = Join-Path $OutDir $FolderName
New-Item -ItemType Directory -Force -Path $DestDir | Out-Null

$SourceZip = Join-Path $DestDir "source.zip"
git archive --format=zip -o $SourceZip HEAD
if (-not (Test-Path $SourceZip)) {
    throw "git archive 失敗"
}
# 釋放 git 對 source.zip 的 handle，避免後續壓縮失敗
[System.GC]::Collect()
[System.GC]::WaitForPendingFinalizers()
Start-Sleep -Milliseconds 200

# 本機資料庫（若存在）
$DbCopied = $false
$dbCandidates = @(
    (Join-Path $RepoRoot "qs_system.db"),
    (Join-Path $RepoRoot "data\qs_system.db")
)
$envData = $env:DATA_DIR
if ($envData) { $dbCandidates += (Join-Path $envData "qs_system.db") }

foreach ($db in $dbCandidates) {
    if (Test-Path $db) {
        Copy-Item $db (Join-Path $DestDir "qs_system.db")
        $DbCopied = $true
        break
    }
}

# 上傳檔（若存在且不太大）
$uploadsSrc = Join-Path $RepoRoot "uploads"
if (Test-Path $uploadsSrc) {
    $files = Get-ChildItem $uploadsSrc -File -ErrorAction SilentlyContinue
    if ($files -and ($files | Measure-Object -Property Length -Sum).Sum -lt 200MB) {
        Copy-Item $uploadsSrc (Join-Path $DestDir "uploads") -Recurse
    }
}

$Manifest = @{
    app_name    = "OSsysCU"
    version     = $Version
    git_commit  = $Commit
    git_branch  = $Branch
    backup_time = (Get-Date).ToString("o")
    db_included = $DbCopied
    production  = "https://ossys.zeabur.app"
} | ConvertTo-Json -Depth 3

$Manifest | Set-Content (Join-Path $DestDir "MANIFEST.json") -Encoding UTF8

# Final zip: tar first; Compress-Archive can fail on nested source.zip locks
$FinalZip = Join-Path $OutDir "$FolderName.zip"
Write-FinalBackupZip -SourceDir $DestDir -ZipPath $FinalZip
if (-not (Test-Path $FinalZip)) {
    throw "建立最終壓縮檔失敗"
}

Write-Host ""
Write-Host "=== OSsysCU 備份完成 ===" -ForegroundColor Green
Write-Host "版本:    $Version"
Write-Host "Commit:  $CommitShort ($Branch)"
Write-Host "資料夾:  $DestDir"
Write-Host "壓縮檔:  $FinalZip"
Write-Host "含 DB:   $DbCopied"
Write-Host ""
