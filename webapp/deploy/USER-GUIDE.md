# Diagen — Operator Guide

## 1. Start everything (after machine reboot / first time)

Task Scheduler already auto-starts all 4 services on login (`diagen-backend`, `diagen-caddy`, `diagen-tunnel`, `diagen-backup`). Nothing to do manually — just log into Windows.

To force-start now without rebooting:

```bash
cd /c/Users/manav/Desktop/dungen/webapp/deploy
for name in backend caddy tunnel backup; do
  schtasks /run /tn "diagen-$name"
  sleep 2
done
```

## 2. Get the public URL

Quick tunnel URL **changes every time cloudflared restarts**. Always get the latest:

```bash
cd /c/Users/manav/Desktop/dungen/webapp/deploy
grep -n "trycloudflare.com" logs/tunnel.log | tail -3
```

Use the URL from the **most recent** `Requesting new quick Tunnel` block (last line block), not just any match — old URLs stay in the log.

## 3. Health check (do this after any restart)

```bash
cd /c/Users/manav/Desktop/dungen/webapp/deploy
tasklist | grep -iE "python|caddy|cloudflared"
```

All 3 must appear. If one's missing, restart just that one (see §5) — never restart via a broad taskkill across multiple services at once.

## 4. First-time sign up

Open the public URL in a browser → use the app's own signup screen → create your account. No admin bootstrap step. Password reset doesn't exist — losing it means a new account or manual DB edit.

## 5. Restart a single service (safe way)

**Important:** killing one process can accidentally kill others sharing the same console. Restart one at a time, verify with `tasklist` before touching the next.

```bash
cd /c/Users/manav/Desktop/dungen/webapp/deploy

# backend only
schtasks /end /tn "diagen-backend" 2>/dev/null
taskkill //F //IM python.exe //T 2>/dev/null
schtasks /run /tn "diagen-backend"
sleep 3
tasklist | grep -i python

# caddy only
schtasks /end /tn "diagen-caddy" 2>/dev/null
taskkill //F //IM caddy.exe //T 2>/dev/null
schtasks /run /tn "diagen-caddy"
sleep 3
tasklist | grep -i caddy

# tunnel only
schtasks /end /tn "diagen-tunnel" 2>/dev/null
taskkill //F //IM cloudflared.exe //T 2>/dev/null
schtasks /run /tn "diagen-tunnel"
sleep 5
tasklist | grep -i cloudflared
```

After any tunnel restart, re-fetch the URL (§2) — it will have changed.

## 6. Redeploy after a code change

```bash
cd /c/Users/manav/Desktop/dungen/webapp/deploy

# backend change
schtasks /end /tn "diagen-backend" 2>/dev/null
taskkill //F //IM python.exe //T 2>/dev/null
schtasks /run /tn "diagen-backend"

# frontend change
cd ../frontend && npm run build && cd ../deploy
schtasks /end /tn "diagen-caddy" 2>/dev/null
taskkill //F //IM caddy.exe //T 2>/dev/null
schtasks /run /tn "diagen-caddy"
```

## 7. Check logs

```bash
cd /c/Users/manav/Desktop/dungen/webapp/deploy
tail -n 40 logs/backend.log
tail -n 40 logs/caddy.log
tail -n 40 logs/tunnel.log
tail -n 40 logs/backup.log
```

## 8. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Error 1033 (Cloudflare Tunnel error) | cloudflared not running, or you're using a stale URL | Check §3 tasklist; if dead, restart per §5; re-fetch URL per §2 |
| Bad Gateway 502 | cloudflared up, but backend/caddy down | Check §3; restart missing service per §5 |
| `date`/`sleep: command not found` in logs | PATH missing Git bin in Task Scheduler context | Already patched in all 4 watchdog scripts — shouldn't recur |
| One restart kills unrelated services too | Shared console signal broadcast | Never batch multiple `taskkill /T` calls together — one at a time, verify between each |

## 9. Stop everything

```bash
cd /c/Users/manav/Desktop/dungen/webapp/deploy
for name in backend caddy tunnel backup; do
  schtasks /end /tn "diagen-$name" 2>/dev/null
done
taskkill //F //IM python.exe //T 2>/dev/null
taskkill //F //IM caddy.exe //T 2>/dev/null
taskkill //F //IM cloudflared.exe //T 2>/dev/null
```

## 10. Backups

Auto-backed up every 6h to `webapp/backend/data/backups/`, pruned after 14 days. To restore: stop backend (§9, backend only), copy a backup file over `webapp/backend/data/projects.db`, restart backend (§5).
