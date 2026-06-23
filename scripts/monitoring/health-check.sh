#!/bin/bash
# OpenClaw Agency Health Check
# Run via cron every 10 minutes

set -e

LOG_FILE="/root/.openclaw/workspace/logs/health-check.log"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Ensure log directory exists
mkdir -p "$(dirname "$LOG_FILE")"

echo "=== Health Check: $TIMESTAMP ===" >> "$LOG_FILE"

# 1. Gateway check
if systemctl is-active --quiet openclaw-gateway 2>/dev/null; then
    echo "✅ Gateway: running" >> "$LOG_FILE"
else
    echo "❌ Gateway: DOWN" >> "$LOG_FILE"
fi

# 2. n8n check
if pgrep -x "n8n" > /dev/null 2>&1; then
    echo "✅ n8n: running" >> "$LOG_FILE"
else
    echo "❌ n8n: DOWN" >> "$LOG_FILE"
fi

# 3. MongoDB check
if systemctl is-active --quiet mongod 2>/dev/null; then
    echo "✅ MongoDB: running" >> "$LOG_FILE"
else
    echo "❌ MongoDB: DOWN" >> "$LOG_FILE"
fi

# 4. Disk check
DISK_USAGE=$(df / | awk 'NR==2 {print $5}' | tr -d '%')
if [ "$DISK_USAGE" -lt 90 ]; then
    echo "✅ Disk: ${DISK_USAGE}% used" >> "$LOG_FILE"
else
    echo "❌ Disk: ${DISK_USAGE}% used (CRITICAL)" >> "$LOG_FILE"
fi

# 5. RAM check
RAM_USAGE=$(free | awk 'NR==2 {printf "%.0f", $3/$2*100}')
if [ "$RAM_USAGE" -lt 85 ]; then
    echo "✅ RAM: ${RAM_USAGE}% used" >> "$LOG_FILE"
else
    echo "❌ RAM: ${RAM_USAGE}% used (WARNING)" >> "$LOG_FILE"
fi

# 6. Cloudflare Tunnel check
if pgrep -x "cloudflared" > /dev/null 2>&1; then
    echo "✅ Cloudflare Tunnel: running" >> "$LOG_FILE"
else
    echo "❌ Cloudflare Tunnel: DOWN" >> "$LOG_FILE"
fi

# 7. fail2ban check
if systemctl is-active --quiet fail2ban 2>/dev/null; then
    echo "✅ fail2ban: running" >> "$LOG_FILE"
else
    echo "❌ fail2ban: DOWN" >> "$LOG_FILE"
fi

echo "---" >> "$LOG_FILE"

# Keep only last 1000 lines
tail -1000 "$LOG_FILE" > "${LOG_FILE}.tmp" && mv "${LOG_FILE}.tmp" "$LOG_FILE"
