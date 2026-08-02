# Runs the FastAPI backend (uvicorn, single worker — required, see README)
# and restarts it if it ever exits. Meant to be launched by Task Scheduler
# at logon.

$ErrorActionPreference = "SilentlyContinue"

$backendDir = Join-Path $PSScriptRoot "..\backend"
$venvPy     = Join-Path $backendDir ".venv\Scripts\python.exe"
$logDir     = Join-Path $PSScriptRoot "logs"
$logFile    = Join-Path $logDir "backend.log"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

if (-not (Test-Path $venvPy)) {
    Add-Content $logFile "[watchdog] $(Get-Date) - venv not found at $venvPy. Run the one-time setup in README.md first."
    exit 1
}

Set-Location $backendDir

while ($true) {
    & $venvPy -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 *>> $logFile
    Add-Content $logFile "`n[watchdog] $(Get-Date) - backend exited, restarting in 3s`n"
    Start-Sleep -Seconds 3
}
