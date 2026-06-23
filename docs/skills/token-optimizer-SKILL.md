---
name: "token-optimizer"
description: "Tracks per-model token usage, enforces rate limits, and applies caveman-style compression."
---

# Token Optimizer Skill — Smart Token Management

## What It Does
Tracks token consumption across all models, prevents rate-limit breaches, and applies caveman-style compression to reduce token usage by 20-30%.

## Components

### 1. Usage Tracker (`token_tracker.py`)
- Runs via `cron` every 10 minutes
- Reads `session_status` to get per-model token consumption
- Maintains `logs/token_usage.json` with daily tallies
- Resets counters daily at midnight UTC

### 2. Rate-Limit Guard
- Before any model call, check remaining quota
- If >85% consumed: switch to next available :free model
- If >95% consumed: block non-critical requests, alert Abdo
- Model priority: `openrouter/free` → `deepseek-r1:free` → `qwen3-8b:free`

### 3. Caveman Compression
Inspired by [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) — reduces output tokens while preserving technical accuracy.

**Compression rules:**
- Remove filler: "please", "kindly", "just", "basically", "actually"
- Contract phrases: "in order to" → "to", "I think" → ""
- Preserve: code blocks, URLs, file paths, error messages, CVE IDs
- Target: 20-30% reduction on non-technical content

**API:**
- `compress_prompt(text)` — compress before sending to model
- `compress_response(text)` — compress before delivering to user
- `smart_compression(text, context)` — auto-detect technical vs. conversational

### 4. Alert System
- Telegram alert when any model exceeds 85% daily quota
- Includes: model name, tokens used, remaining, recommendation
- Logged to `logs/token_optimizer.log`

## Free Model Quotas (per day)
| Model | Requests | Notes |
|-------|----------|-------|
| openrouter/free | 200 | Auto-rotates |
| deepseek-r1:free | 20 | High reasoning |
| qwen3-8b:free | 20 | Fast, good for coding |
| openrouter/owl-alpha | 20 | 1M context, best quality |

## Safety Rules
- Never exceed known quotas — always switch models first
- Never compress error traces or debug output
- Never compress code blocks or technical identifiers
- All compression is logged for audit

## Integration
- Cron job every 10 minutes: `python3 token_tracker.py`
- Sub-agent spawns use `compress_prompt()` before model calls
- `session_status` checked before heavy operations
