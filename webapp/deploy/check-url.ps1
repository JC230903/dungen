# Prints the current public URL from the tunnel log (most recent one wins —
# quick tunnel URLs change on every restart).

$logFile = Join-Path $PSScriptRoot "logs\tunnel.log"

if (-not (Test-Path $logFile)) {
    Write-Host "No tunnel log yet — is the tunnel task running?"
    exit 1
}

$match = Select-String -Path $logFile -Pattern "https://[a-zA-Z0-9-]+\.trycloudflare\.com" |
    Select-Object -Last 1

if ($match) {
    Write-Host $match.Matches[0].Value
} else {
    Write-Host "No URL found yet — tunnel may still be starting. Check logs\tunnel.log."
}
