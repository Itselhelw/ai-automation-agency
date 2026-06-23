---
name: "auto-fix-skill"
description: "Self-healing system that detects failures like \"Apply Patch failed\" and auto-applies fixes."
---

# Auto-Fix Skill — Self-Healing System

## What It Does
Monitors logs for known error patterns and applies minimal-risk fixes automatically. Escalates to Abdo when fixes fail.

## Error Detection Patterns
- `⚠️ 🩹 Apply Patch failed` — patch/diff application failures
- `Permission denied` — file permission issues
- `Command not found` — missing dependencies
- `Network timeout` — connectivity issues
- `Rate limit.*exceed` — API rate limiting
- `Disk full` — storage exhaustion
- `Out of memory` — RAM exhaustion
- `Connection refused` — service unavailable

## Fix Strategy (Risk-Tiered)
| Risk | Action | Examples |
|------|--------|----------|
| Low | Auto-execute | `chmod`, `touch`, `mkdir`, `df`, `ls` |
| Medium | Log + notify Abdo | `apt install`, `sed`, `git pull` |
| High | Block + alert Abdo | `rm`, `systemctl`, config changes |

## Workflow
1. **Scan** → Read last 200 lines of `logs/exec.log`, `logs/automation-engine.log`
2. **Match** → Regex against known error patterns
3. **Diagnose** → Identify root cause using abductive reasoning
4. **Fix** → Apply simplest effective fix for risk tier
5. **Verify** → Confirm error no longer appears in logs
6. **Log** → Write to `logs/auto_fixer.log` with: timestamp, error, fix, success

## Safety Rules
- Never execute destructive commands without Abdo approval
- Never modify SSH config, UFW rules, or crontab without approval
- Always verify fix worked before declaring success
- If same error recurs 3+ times, escalate even if fixable

## Integration
- Runs via `cron` every 10 minutes as `systemEvent` to main session
- Logs to `logs/auto_fixer.log`
- Critical failures send Telegram alert via `wake`
