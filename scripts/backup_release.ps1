# OSsysCU 完整版本備份腳本（Windows）
# 用法:
#   .\scripts\backup_release.ps1
#   .\scripts\backup_release.ps1 -OutDir "D:\Backups\OSsysCU"
#   .\scripts\backup_release.ps1 -IncludeProduction   # 另拉 mossys.xyz DB + uploads（需 SSH 金鑰）
param(
    [string]$OutDir = "",
    [string]$DataDir = "",
    [switch]$IncludeProduction,
    [int]$MaxUploadsMB = 500
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

function Resolve-LocalDataDir {
    param([string]$Explicit)
    if ($Explicit) { return (Resolve-Path $Explicit).Path }
    if ($env:DATA_DIR -and (Test-Path $env:DATA_DIR)) {
        return (Resolve-Path $env:DATA_DIR).Path
    }
    $data = Join-Path $RepoRoot "_data"
    if (Test-Path $data) { return (Resolve-Path $data).Path }
    return $RepoRoot.Path
}

function Get-BestLocalDbPath {
    param([string]$DataRoot)
    $candidates = @(
        (Join-Path $DataRoot "qs_system.db"),
        (Join-Path $RepoRoot "_data\qs_system.db"),
        (Join-Path $RepoRoot "data\qs_system.db"),
        (Join-Path $RepoRoot "qs_system.db")
    ) | Select-Object -Unique

    $best = $null
    foreach ($db in $candidates) {
        if (-not (Test-Path $db)) { continue }
        $len = (Get-Item $db).Length
        if (-not $best -or $len -gt $best.Length) {
            $best = [PSCustomObject]@{ Path = $db; Length = $len }
        }
    }
    if ($best) { return $best.Path }
    return $null
}

function Copy-UploadsIfSmall {
    param(
        [string]$Src,
        [string]$DestName,
        [string]$DestDir,
        [int]$MaxMb
    )
    if (-not (Test-Path $Src)) { return $false }
    $sum = (Get-ChildItem $Src -Recurse -File -ErrorAction SilentlyContinue |
        Measure-Object -Property Length -Sum).Sum
    if (-not $sum) { return $false }
    if ($sum -gt ($MaxMb * 1MB)) {
        Write-Host "略過 $DestName：大小 $([math]::Round($sum / 1MB, 1)) MB > $MaxMb MB" -ForegroundColor Yellow
        return $false
    }
    Copy-Item $Src (Join-Path $DestDir $DestName) -Recurse -Force
    return $true
}

function Write-FinalBackupZip {
    param(
        [Parameter(Mandatory = $true)][string]$SourceDir,
        [Parameter(Mandatory = $true)][string]$ZipPath
    )
    if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }

    $parent = Split-Path $SourceDir -Parent
    $name = Split-Path $SourceDir -Leaf

    if (Get-Command tar -ErrorAction SilentlyContinue) {
        & tar -a -cf $ZipPath -C $parent $name
        if ($LASTEXITCODE -eq 0 -and (Test-Path $ZipPath)) { return }
        if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
    }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory($SourceDir, $ZipPath)
}

function Fetch-ProductionSnapshot {
    param(
        [string]$DestDir,
        [int]$MaxMb
    )
    $key = Join-Path $env:USERPROFILE ".ssh\aliyun-ossys"
    $host = "admin@43.103.44.4"
    if (-not (Test-Path $key)) {
        Write-Host "找不到 SSH 金鑰 $key，略過生產備份" -ForegroundColor Yellow
        return @{ ok = $false; reason = 'no_ssh_key' }
    }
    $dbDest = Join-Path $DestDir "qs_system_mossys.db"
    & scp -i $key "${host}:/data/qs_system.db" $dbDest
    if ($LASTEXITCODE -ne 0) {
        return @{ ok = $false; reason = 'scp_db_failed' }
    }
    $tmp = Join-Path $env:TEMP "ossys_uploads_mossys_$([Guid]::NewGuid().ToString('N'))"
    New-Item -ItemType Directory -Force -Path $tmp | Out-Null
    try {
        & scp -r -i $key "${host}:/data/uploads" $tmp
        if ($LASTEXITCODE -ne 0) {
            return @{ ok = $false; reason = 'scp_uploads_failed'; db = $true }
        }
        $upSrc = Join-Path $tmp "uploads"
        if (-not (Test-Path $upSrc)) { $upSrc = Get-ChildItem $tmp -Directory | Select-Object -First 1 -ExpandProperty FullName }
        $upOk = Copy-UploadsIfSmall -Src $upSrc -DestName "uploads_mossys" -DestDir $DestDir -MaxMb $MaxMb
        return @{ ok = $true; db = $true; uploads = $upOk }
    }
    finally {
        Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
    }
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
[System.GC]::Collect()
[System.GC]::WaitForPendingFinalizers()
Start-Sleep -Milliseconds 200

$localData = Resolve-LocalDataDir $DataDir
$dbPath = Get-BestLocalDbPath $localData
$DbCopied = $false
$dbSourceNote = ""
if ($dbPath) {
    Copy-Item $dbPath (Join-Path $DestDir "qs_system_local.db")
    $DbCopied = $true
    $dbSourceNote = $dbPath
}

$uploadsLocal = $false
$uploadsFrom = Join-Path $localData "uploads"
if (-not (Test-Path $uploadsFrom)) {
    $uploadsFrom = Join-Path $RepoRoot "uploads"
}
$uploadsLocal = Copy-UploadsIfSmall -Src $uploadsFrom -DestName "uploads_local" -DestDir $DestDir -MaxMb $MaxUploadsMB

$prod = $null
if ($IncludeProduction) {
    $prod = Fetch-ProductionSnapshot -DestDir $DestDir -MaxMb $MaxUploadsMB
}

$Manifest = @{
    app_name          = "OSsysCU"
    version           = $Version
    git_commit        = $Commit
    git_branch        = $Branch
    backup_time       = (Get-Date).ToString("o")
    db_local          = if ($DbCopied) { "qs_system_local.db" } else { $null }
    db_local_source   = $dbSourceNote
    uploads_local     = $uploadsLocal
    production        = "https://mossys.xyz"
    production_fetch  = if ($IncludeProduction) { $prod } else { $null }
} | ConvertTo-Json -Depth 5

$Manifest | Set-Content (Join-Path $DestDir "MANIFEST.json") -Encoding UTF8

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
Write-Host "本機 DB: $(if ($DbCopied) { $dbSourceNote } else { '（無）' })"
Write-Host "本機上傳: $(if ($uploadsLocal) { 'uploads_local' } else { '略過或無' })"
if ($IncludeProduction) {
    Write-Host "生產 DB:   $(if ($prod.db) { 'qs_system_mossys.db' } else { '失敗' })"
    Write-Host "生產上傳: $(if ($prod.uploads) { 'uploads_mossys' } else { '略過或失敗' })"
}
Write-Host ""