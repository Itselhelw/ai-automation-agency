#!/usr/bin/env python3
"""
Token Usage Tracker — Tracks per-model token consumption
Runs via cron every 10 minutes
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

LOGS_DIR = Path("/root/.openclaw/workspace/logs")
USAGE_FILE = LOGS_DIR / "token_usage.json"
OPTIMIZER_LOG = LOGS_DIR / "token_optimizer.log"

# Free model daily quotas (requests per day)
MODEL_QUOTAS = {
    "openrouter/owl-alpha": 20,
    "openrouter/deepseek/deepseek-r1:free": 20,
    "openrouter/qwen/qwen3-8b:free": 20,
    "openrouter/free": 200,
    "openrouter/auto": 100,
    "google/gemma-4-31b-it:free": 20,
    "openrouter/qwen/qwen3-coder:free": 20,
}

def log(msg):
    timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = f"[{timestamp}] {msg}"
    print(entry)
    with open(OPTIMIZER_LOG, "a") as f:
        f.write(entry + "\n")

def load_usage():
    if USAGE_FILE.exists():
        try:
            with open(USAGE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}

def save_usage(data):
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(USAGE_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_session_status():
    """Get token usage from OpenClaw session_status"""
    try:
        result = subprocess.run(
            ["openclaw", "status", "--json"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        pass
    return None

def check_limits(usage_data):
    """Check if any model is approaching its limit"""
    alerts = []
    for model, quota in MODEL_QUOTAS.items():
        if model in usage_data:
            used = usage_data[model].get("today_used", 0)
            pct = (used / quota) * 100 if quota > 0 else 0
            if pct >= 95:
                alerts.append(f"🔴 {model}: {used}/{quota} ({pct:.0f}%) — CRITICAL")
            elif pct >= 85:
                alerts.append(f"🟡 {model}: {used}/{quota} ({pct:.0f}%) — WARNING")
    return alerts

def main():
    log("Token optimizer cycle started")

    # Load existing usage
    usage = load_usage()

    # Get current session status
    status = get_session_status()
    if status:
        model = status.get("model", "unknown")
        usage_stats = status.get("usage", {})
        tokens_used = usage_stats.get("total_tokens", 0)

        if model not in usage:
            usage[model] = {
                "today_used": 0,
                "today_limit": MODEL_QUOTAS.get(model, 100),
                "last_reset": datetime.now().isoformat(),
            }

        usage[model]["today_used"] = usage[model].get("today_used", 0) + tokens_used
        log(f"Recorded {tokens_used} tokens for {model}")

    # Check limits
    alerts = check_limits(usage)
    for alert in alerts:
        log(alert)

    # Save
    save_usage(usage)

    # Summary
    for model in MODEL_QUOTAS:
        if model in usage:
            used = usage[model].get("today_used", 0)
            limit = MODEL_QUOTAS[model]
            log(f"  {model}: {used}/{limit}")

    log("Token optimizer cycle complete")

if __name__ == "__main__":
    main()
