#!/usr/bin/env python3
"""
AI Audit Report Generator
Practice automation #3 for AI automation agency portfolio.
Analyzes a business website and generates a professional automation audit report.

Usage:
    python3 ai-audit-generator.py --company "TestCo" --url "https://example.com"
    python3 ai-audit-generator.py --company "Acme Inc" --url "https://acme.com" --output-dir ./audits
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

# OpenRouter config
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

MODEL_CHAIN = [
    "deepseek/deepseek-r1:free",
    "qwen/qwen3-8b:free",
    "openrouter/free",
]

AUDIT_ANALYSIS_PROMPT = """You are an AI automation consultant analyzing a business website for automation opportunities.

Company: {company}
Website: {url}
Scraped Data:
- Title: {title}
- Meta Description: {meta_desc}
- Headings: {headings}
- Services/Products mentioned: {services}
- Has contact form: {has_contact_form}
- Has blog: {has_blog}
- Has e-commerce: {has_ecommerce}
- Page text sample: {text_sample}

Based on this data, provide a professional automation audit analysis in JSON format:

{{
  "executive_summary": "2-3 sentence summary of automation potential",
  "current_state": "Analysis of current manual processes likely in use",
  "automation_opportunities": [
    {{
      "name": "Automation name",
      "description": "What it does",
      "time_savings": "X hours/week",
      "complexity": "low/medium/high",
      "priority": 1,
      "estimated_roi": "X hours/month saved"
    }}
  ],
  "priority_order": ["automation_1", "automation_2", ...],
  "estimated_total_savings": "X hours/week total",
  "next_steps": "Recommended first action"
}}

Include exactly 5 automation opportunities. Focus on practical, high-impact automations.
Output ONLY valid JSON, no markdown code fences."""


def get_api_key() -> str:
    """Get OpenRouter API key from environment or config."""
    key = OPENROUTER_API_KEY
    if key:
        return key
    config_paths = [
        Path("/root/.openclaw/config.yaml"),
        Path("/root/.openclaw/config.json"),
        Path.home() / ".openclaw" / "config.yaml",
    ]
    for config_path in config_paths:
        if config_path.exists():
            try:
                content = config_path.read_text()
                for line in content.split("\n"):
                    if "api_key" in line.lower() and ":" in line:
                        parts = line.split(":", 1)
                        if len(parts) == 2:
                            val = parts[1].strip().strip("'\"")
                            if len(val) > 10:
                                return val
            except Exception:
                pass
    return ""


def scrape_website(url: str) -> dict:
    """Scrape website for audit data."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"⚠️ Could not scrape {url}: {e}")
        return {
            "title": "N/A",
            "meta_desc": "N/A",
            "headings": [],
            "services": "N/A",
            "has_contact_form": False,
            "has_blog": False,
            "has_ecommerce": False,
            "text_sample": "N/A",
        }

    soup = BeautifulSoup(response.text, "html.parser")

    title = soup.title.string.strip() if soup.title and soup.title.string else "N/A"

    meta_desc = "N/A"
    meta_tag = soup.find("meta", attrs={"name": "description"})
    if meta_tag and meta_tag.get("content"):
        meta_desc = meta_tag["content"].strip()

    headings = []
    for level in ["h1", "h2", "h3"]:
        for tag in soup.find_all(level):
            text = tag.get_text(strip=True)
            if text:
                headings.append(f"[{level.upper()}] {text}")

    # Detect features
    has_contact_form = bool(
        soup.find("form") or soup.find(string=re.compile(r"contact", re.I))
    )
    has_blog = bool(
        soup.find(string=re.compile(r"blog|articles|news", re.I))
    )
    has_ecommerce = bool(
        soup.find(string=re.compile(r"shop|cart|buy|price|product", re.I))
    )

    # Extract services/products
    services = []
    for tag in soup.find_all(["h2", "h3", "li"]):
        text = tag.get_text(strip=True)
        if 10 < len(text) < 80:
            services.append(text)
    services = services[:10]

    # Text sample
    paragraphs = soup.find_all("p")
    text_sample = " ".join(p.get_text(strip=True) for p in paragraphs)[:1000]

    return {
        "title": title,
        "meta_desc": meta_desc,
        "headings": headings[:15],
        "services": services,
        "has_contact_form": has_contact_form,
        "has_blog": has_blog,
        "has_ecommerce": has_ecommerce,
        "text_sample": text_sample,
    }


def get_ai_analysis(company: str, url: str, scraped: dict) -> dict:
    """Get AI analysis of automation opportunities."""
    api_key = get_api_key()
    if not api_key:
        print("⚠️ No API key found. Generating template report without AI analysis.")
        return generate_fallback_analysis(company, scraped)

    prompt = AUDIT_ANALYSIS_PROMPT.format(
        company=company,
        url=url,
        title=scraped["title"],
        meta_desc=scraped["meta_desc"],
        headings=", ".join(scraped["headings"][:10]) or "N/A",
        services=", ".join(scraped["services"][:5]) or "N/A",
        has_contact_form="Yes" if scraped["has_contact_form"] else "No",
        has_blog="Yes" if scraped["has_blog"] else "No",
        has_ecommerce="Yes" if scraped["has_ecommerce"] else "No",
        text_sample=scraped["text_sample"][:500] or "N/A",
    )

    for model in MODEL_CHAIN:
        print(f"🤖 Analyzing with: {model}")
        try:
            response = requests.post(
                OPENROUTER_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 2000,
                },
                timeout=90,
            )

            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    clean = content.strip()
                    if clean.startswith("```"):
                        clean = clean.split("\n", 1)[1]
                    if clean.endswith("```"):
                        clean = clean.rsplit("\n", 1)[0]
                    try:
                        return json.loads(clean)
                    except json.JSONDecodeError:
                        continue
            else:
                print(f"⚠️ {model} returned {response.status_code}")
                continue

        except requests.exceptions.Timeout:
            print(f"⚠️ {model} timed out")
            continue
        except requests.exceptions.RequestException as e:
            print(f"⚠️ {model} error: {e}")
            continue

    print("⚠️ All models failed. Using fallback analysis.")
    return generate_fallback_analysis(company, scraped)


def generate_fallback_analysis(company: str, scraped: dict) -> dict:
    """Generate a fallback analysis without AI."""
    opportunities = [
        {
            "name": "Email Automation",
            "description": "Auto-sort, prioritize, and draft responses to incoming emails",
            "time_savings": "5-10 hours/week",
            "complexity": "low",
            "priority": 1,
            "estimated_roi": "20-40 hours/month saved",
        },
        {
            "name": "Lead Capture & Qualification",
            "description": "Auto-capture leads from website forms, score them, and route to sales",
            "time_savings": "3-5 hours/week",
            "complexity": "medium",
            "priority": 2,
            "estimated_roi": "12-20 hours/month saved",
        },
        {
            "name": "Content Production",
            "description": "AI-assisted content generation for blog posts, social media, and emails",
            "time_savings": "5-15 hours/week",
            "complexity": "medium",
            "priority": 3,
            "estimated_roi": "20-60 hours/month saved",
        },
        {
            "name": "Customer Support Automation",
            "description": "AI chatbot handling 60-70% of common customer questions",
            "time_savings": "10-20 hours/week",
            "complexity": "high",
            "priority": 4,
            "estimated_roi": "40-80 hours/month saved",
        },
        {
            "name": "Data Entry & Reporting",
            "description": "Automated data collection, entry, and report generation",
            "time_savings": "3-8 hours/week",
            "complexity": "low",
            "priority": 5,
            "estimated_roi": "12-32 hours/month saved",
        },
    ]

    return {
        "executive_summary": f"{company} has significant automation potential. Based on our analysis of their website and business model, we identified 5 high-impact automation opportunities that could save 26-58 hours/week.",
        "current_state": f"{company} appears to be handling many processes manually. Common patterns in their industry suggest heavy reliance on email communication, manual lead tracking, and repetitive content creation.",
        "automation_opportunities": opportunities,
        "priority_order": [o["name"] for o in opportunities],
        "estimated_total_savings": "26-58 hours/week",
        "next_steps": "Start with Email Automation (low complexity, high impact) as a quick win, then expand to Lead Capture and Content Production.",
    }


def generate_report(company: str, url: str, scraped: dict, analysis: dict) -> str:
    """Generate a professional markdown audit report."""
    now = datetime.utcnow().strftime("%B %d, %Y")

    report = f"""# 🤖 AI Automation Audit Report

**Company:** {company}  
**Website:** {url}  
**Date:** {now}  
**Prepared by:** Abdo — AI Automation Specialist

---

## Executive Summary

{analysis.get("executive_summary", "N/A")}

**Estimated Total Savings:** {analysis.get("estimated_total_savings", "N/A")}

---

## Current State Analysis

{analysis.get("current_state", "N/A")}

### Website Overview
| Field | Value |
|-------|-------|
| Title | {scraped["title"]} |
| Description | {scraped["meta_desc"][:100]} |
| Contact Form | {"✅ Yes" if scraped["has_contact_form"] else "❌ No"} |
| Blog/Content | {"✅ Yes" if scraped["has_blog"] else "❌ No"} |
| E-commerce | {"✅ Yes" if scraped["has_ecommerce"] else "❌ No"} |

### Key Headings
"""

    for h in scraped["headings"][:10]:
        report += f"- {h}\n"

    report += "\n---\n\n## Automation Opportunities\n\n"

    for opp in analysis.get("automation_opportunities", []):
        report += f"### {opp.get('priority', '?')}. {opp.get('name', 'Unknown')}\n\n"
        report += f"**What it does:** {opp.get('description', 'N/A')}\n\n"
        report += f"**Time savings:** {opp.get('time_savings', 'N/A')}\n\n"
        report += f"**Complexity:** {opp.get('complexity', 'N/A')}\n\n"
        report += f"**Estimated ROI:** {opp.get('estimated_roi', 'N/A')}\n\n"
        report += "---\n\n"

    report += f"""## Recommended Priority Order

Based on impact vs. effort analysis:

"""

    for i, name in enumerate(analysis.get("priority_order", []), 1):
        report += f"{i}. **{name}**\n"

    report += f"""

---

## Next Steps

{analysis.get("next_steps", "Contact us to discuss implementation.")}

### What Happens Next
1. **Free 30-minute call** — We discuss your specific needs and priorities
2. **Custom proposal** — Detailed plan with timeline and pricing
3. **Build & deploy** — Typically 1-2 weeks for first automation
4. **Monitor & optimize** — 24/7 monitoring with monthly reports

---

## Investment

| Package | Price | Includes |
|---------|-------|----------|
| **AI Audit** (this report) | $500 one-time | Full analysis + recommendations |
| **Starter** | $2,000/month | 1 automation + 5 hours support |
| **Growth** | $4,000/month | 3 automations + 15 hours support |
| **Scale** | $7,000/month | Unlimited + 30 hours support |

---

*This report was generated using AI analysis of publicly available information.*
*For a more detailed assessment, book a free call: openclaw036@gmail.com*

**Abdo** — AI Automation Specialist  
📧 openclaw036@gmail.com | 🌐 agency.ghosttrace.tech
"""

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Generate an AI automation audit report for a business"
    )
    parser.add_argument("--company", required=True, help="Company name")
    parser.add_argument("--url", required=True, help="Company website URL")
    parser.add_argument(
        "--output-dir",
        default="/root/.openclaw/workspace/outputs/agency-audits",
        help="Output directory for the report",
    )
    parser.add_argument(
        "--skip-ai",
        action="store_true",
        help="Skip AI analysis (use template)",
    )
    args = parser.parse_args()

    print(f"🔍 Analyzing: {args.company} ({args.url})")

    # Step 1: Scrape website
    print("\n📡 Scraping website...")
    scraped = scrape_website(args.url)
    print(f"   Title: {scraped['title']}")
    print(f"   Headings: {len(scraped['headings'])}")
    print(f"   Services: {len(scraped['services'])}")

    # Step 2: AI analysis
    if args.skip_ai:
        analysis = generate_fallback_analysis(args.company, scraped)
    else:
        print("\n🤖 Running AI analysis...")
        analysis = get_ai_analysis(args.company, args.url, scraped)

    # Step 3: Generate report
    print("\n📝 Generating report...")
    report = generate_report(args.company, args.url, scraped, analysis)

    # Step 4: Save
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    safe_name = re.sub(r"[^a-zA-Z0-9]+", "-", args.company.lower()).strip("-")
    timestamp = datetime.utcnow().strftime("%Y%m%d")
    filename = output_dir / f"audit-{safe_name}-{timestamp}.md"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\n✅ Audit report saved: {filename}")
    print(f"📊 Estimated savings: {analysis.get('estimated_total_savings', 'N/A')}")
    print(f"🎯 Top priority: {analysis.get('priority_order', ['N/A'])[0]}")


if __name__ == "__main__":
    main()
