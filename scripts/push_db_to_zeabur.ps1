# 上傳本機 qs_system.db 至 Zeabur（admin 登入 + RESTORE_TOKEN）
param(
    [Parameter(Mandatory = $true)]
    [string]$AdminPassword,
    [string]$AdminUser = 'admin',
    [string]$RestoreToken = 'Restore8899',
    [string]$DbPath = (Join-Path (Split-Path $PSScriptRoot -Parent) 'qs_system.db'),
    [string]$BaseUrl = 'https://ossys.zeabur.app'
)

if (-not (Test-Path $DbPath)) {
    Write-Error "找不到資料庫: $DbPath"
    exit 1
}

$sizeMb = [math]::Round((Get-Item $DbPath).Length / 1MB, 2)
Write-Host "目標: $BaseUrl"
Write-Host "本機 DB: $DbPath ($sizeMb MB)"

$before = curl.exe -s "$BaseUrl/api/system/status" | ConvertFrom-Json
Write-Host ("還原前: projects={0} payments={1} version={2}" -f $before.data.project_count, $before.data.payment_count, $before.data.app_version)

$cookieJar = Join-Path $env:TEMP 'ossys_restore_cookies.txt'
Remove-Item $cookieJar -ErrorAction SilentlyContinue

$loginBody = "{`"username`":`"$AdminUser`",`"password`":`"$AdminPassword`"}"
$loginResp = curl.exe -s -c $cookieJar -X POST "$BaseUrl/api/auth/login" -H "Content-Type: application/json" -d $loginBody
$login = $loginResp | ConvertFrom-Json
if (-not $login.success) {
    Write-Error "admin 登入失敗: $($login.error)"
    exit 1
}
Write-Host "admin 登入成功: $($login.data.username)"

$result = curl.exe -s -b $cookieJar -X POST "$BaseUrl/api/system/restore-db" -H "X-Restore-Token: $RestoreToken" -F "file=@$DbPath"
Write-Host $result
$parsed = $result | ConvertFrom-Json
if (-not $parsed.success) {
    Write-Error "還原失敗: $($parsed.error)"
    exit 1
}

$after = curl.exe -s "$BaseUrl/api/system/status" | ConvertFrom-Json
Write-Host ("還原後: projects={0} payments={1}" -f $after.data.project_count, $after.data.payment_count)

Remove-Item $cookieJar -ErrorAction SilentlyContinue
