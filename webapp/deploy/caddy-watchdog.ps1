# Runs Caddy (static frontend + /api reverse proxy) and restarts it if it
# ever exits. Meant to be launched by Task Scheduler at logon.

$ErrorActionPreference = "SilentlyContinue"

$logDir   = Join-Path $PSScriptRoot "logs"
$logFile  = Join-Path $logDir "caddy.log"
$caddyExe = Join-Path $PSScriptRoot "bin\caddy.exe"
$config   = Join-Path $PSScriptRoot "Caddyfile"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

if (-not (Test-Path $caddyExe)) {
    Add-Content $logFile "[watchdog] $(Get-Date) - caddy.exe not found at $caddyExe. Run the one-time setup in README.md first."
    exit 1
}

Set-Location $PSScriptRoot

while ($true) {
    & $caddyExe run --config $config *>> $logFile
    Add-Content $logFile "`n[watchdog] $(Get-Date) - caddy exited, restarting in 3s`n"
    Start-Sleep -Seconds 3
}
