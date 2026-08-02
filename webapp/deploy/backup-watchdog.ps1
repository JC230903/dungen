# Periodically copies webapp/backend/data/projects.db (users + saved
# diagrams — the only durable state in this whole app) to a timestamped
# backup, and prunes backups older than $RetainDays. Meant to be launched
# by Task Scheduler at logon; runs forever, sleeping between backups.

$ErrorActionPreference = "SilentlyContinue"

$DbPath      = Join-Path $PSScriptRoot "..\backend\data\projects.db"
$BackupDir   = Join-Path $PSScriptRoot "..\backend\data\backups"
$IntervalSec = 6 * 60 * 60   # every 6 hours
$RetainDays  = 14

$logDir  = Join-Path $PSScriptRoot "logs"
$logFile = Join-Path $logDir "backup.log"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

while ($true) {
    if (Test-Path $DbPath) {
        $stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
        $dest = Join-Path $BackupDir "projects_$stamp.db"
        try {
            Copy-Item -Path $DbPath -Destination $dest -Force
            Add-Content $logFile "$(Get-Date) - backed up to $dest"
        } catch {
            Add-Content $logFile "$(Get-Date) - backup FAILED: $_"
        }

        $cutoff = (Get-Date).AddDays(-$RetainDays)
        Get-ChildItem $BackupDir -Filter "projects_*.db" |
            Where-Object { $_.LastWriteTime -lt $cutoff } |
            ForEach-Object {
                Remove-Item $_.FullName -Force
                Add-Content $logFile "$(Get-Date) - pruned old backup $($_.Name)"
            }
    } else {
        Add-Content $logFile "$(Get-Date) - no projects.db yet, nothing to back up"
    }

    Start-Sleep -Seconds $IntervalSec
}
