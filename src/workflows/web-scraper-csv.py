#!/usr/bin/env python3
"""
Web Scraper + CSV Exporter
Practice automation #2 for AI automation agency portfolio.
Scrapes a webpage and exports structured data to CSV.

Usage:
    python3 web-scraper-csv.py --url https://example.com --output results.csv
"""

import argparse
import csv
import sys
from datetime import datetime

import requests
from bs4 import BeautifulSoup


def scrape_website(url: str, timeout: int = 15) -> dict:
    """Scrape a webpage and extract structured data."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        print(f"❌ Error: Request timed out after {timeout}s")
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        print(f"❌ Error: Could not connect to {url}")
        sys.exit(1)
    except requests.exceptions.HTTPError as e:
        print(f"❌ Error: HTTP {e.response.status_code}")
        sys.exit(1)

    soup = BeautifulSoup(response.text, "html.parser")

    # Extract page title
    title = soup.title.string.strip() if soup.title and soup.title.string else "N/A"

    # Extract meta description
    meta_desc = "N/A"
    meta_tag = soup.find("meta", attrs={"name": "description"})
    if meta_tag and meta_tag.get("content"):
        meta_desc = meta_tag["content"].strip()

    # Extract headings
    headings = {}
    for level in ["h1", "h2", "h3"]:
        tags = soup.find_all(level)
        for i, tag in enumerate(tags, 1):
            text = tag.get_text(strip=True)
            if text:
                headings[f"{level}_{i}"] = text

    # Extract links
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = a.get_text(strip=True) or "[no text]"
        if href and not href.startswith(("#", "javascript:")):
            links.append({"href": href, "text": text[:100]})

    # Extract paragraph text (first 500 chars)
    paragraphs = soup.find_all("p")
    all_text = " ".join(p.get_text(strip=True) for p in paragraphs)
    first_500 = all_text[:500] if all_text else "N/A"

    return {
        "url": url,
        "scraped_at": datetime.utcnow().isoformat() + "Z",
        "title": title,
        "meta_description": meta_desc,
        "headings": headings,
        "links": links,
        "first_500_chars": first_500,
    }


def save_to_csv(data: dict, output_path: str):
    """Save scraped data to CSV file."""
    rows = []

    # Basic fields
    rows.append(["url", data["url"]])
    rows.append(["scraped_at", data["scraped_at"]])
    rows.append(["title", data["title"]])
    rows.append(["meta_description", data["meta_description"]])
    rows.append(["first_500_chars", data["first_500_chars"]])

    # Headings
    for key, value in data["headings"].items():
        rows.append([f"heading_{key}", value])

    # Links (first 50 to keep CSV manageable)
    for i, link in enumerate(data["links"][:50], 1):
        rows.append([f"link_{i}_href", link["href"]])
        rows.append([f"link_{i}_text", link["text"]])

    rows.append(["total_links", str(len(data["links"]))])
    rows.append(["total_headings", str(len(data["headings"]))])

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["field", "value"])
        writer.writerows(rows)

    print(f"✅ Saved {len(rows)} fields to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Scrape a webpage and export data to CSV"
    )
    parser.add_argument("--url", required=True, help="URL to scrape")
    parser.add_argument(
        "--output",
        default=None,
        help="Output CSV path (default: scraper_output.csv)",
    )
    parser.add_argument(
        "--timeout", type=int, default=15, help="Request timeout in seconds"
    )
    args = parser.parse_args()

    output = args.output or "scraper_output.csv"

    print(f"🔍 Scraping: {args.url}")
    data = scrape_website(args.url, timeout=args.timeout)

    print(f"📄 Title: {data['title']}")
    print(f"📝 Meta: {data['meta_description'][:80]}...")
    print(f"🔗 Links found: {len(data['links'])}")
    print(f"📌 Headings found: {len(data['headings'])}")

    save_to_csv(data, output)
    print(f"✅ Done! Output: {output}")


if __name__ == "__main__":
    main()
