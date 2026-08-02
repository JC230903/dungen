# Runs a Cloudflare Quick Tunnel (no Cloudflare account/domain needed) and
# restarts it if it ever exits. Meant to be launched by Task Scheduler at
# logon.
#
# NOTE: a quick tunnel's public *.trycloudflare.com URL is random and
# changes every time it restarts. Check logs\tunnel.log (or run
# check-url.ps1) for the current one. If you later buy a domain and want a
# stable URL, see the "Upgrade to a named tunnel" section in README.md.

$ErrorActionPreference = "SilentlyContinue"

$logDir  = Join-Path $PSScriptRoot "logs"
$logFile = Join-Path $logDir "tunnel.log"
$cfExe   = Join-Path $PSScriptRoot "bin\cloudflared.exe"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

if (-not (Test-Path $cfExe)) {
    Add-Content $logFile "[watchdog] $(Get-Date) - cloudflared.exe not found at $cfExe. Run the one-time setup in README.md first."
    exit 1
}

Set-Location $PSScriptRoot

while ($true) {
    & $cfExe tunnel --url http://127.0.0.1:8080 --no-autoupdate *>> $logFile
    Add-Content $logFile "`n[watchdog] $(Get-Date) - tunnel exited, restarting in 3s (URL will change)`n"
    Start-Sleep -Seconds 3
}
