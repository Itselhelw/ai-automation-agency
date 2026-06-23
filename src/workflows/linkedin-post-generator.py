#!/usr/bin/env python3
"""
LinkedIn Post Generator
Practice automation #1 for AI automation agency portfolio.
Generates 5 ready-to-post LinkedIn posts from a topic using OpenRouter free models.

Usage:
    python3 linkedin-post-generator.py --topic "AI automation for small businesses"
    python3 linkedin-post-generator.py --topic "productivity tips" --model deepseek-r1:free
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests

# OpenRouter config
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")

# Model fallback chain (free models only)
MODEL_CHAIN = [
    "deepseek/deepseek-r1:free",
    "qwen/qwen3-8b:free",
    "openrouter/free",
]

POST_GENERATION_PROMPT = """You are an expert LinkedIn content creator. Generate 5 unique, engaging LinkedIn posts about the topic: "{topic}".

Each post must follow this structure:
1. HOOK — First line grabs attention (question, bold statement, or surprising stat)
2. VALUE — 2-3 paragraphs of actionable insight, story, or framework
3. CTA — End with a question or call-to-action to drive engagement

Rules:
- Each post: 150-300 words
- Use line breaks for readability (LinkedIn formatting)
- Include relevant emojis (sparingly)
- Vary the style: one story-based, one list-based, one question-based, one contrarian, one how-to
- Sound professional but conversational
- No hashtags in the body (we'll add them separately)

Output format (JSON):
[
  {"style": "story", "post": "..."},
  {"style": "list", "post": "..."},
  {"style": "question", "post": "..."},
  {"style": "contrarian", "post": "..."},
  {"style": "how-to", "post": "..."}
]

Output ONLY valid JSON, no markdown code fences."""


def get_api_key() -> str:
    """Get OpenRouter API key from environment, config file, or CLI arg."""
    key = OPENROUTER_API_KEY
    if key:
        return key

    # Try config file in repo
    config_file = Path(__file__).parent.parent.parent / ".env"
    if config_file.exists():
        for line in config_file.read_text().split("\n"):
            if line.startswith("OPENROUTER_API_KEY="):
                val = line.split("=", 1)[1].strip().strip("'\"")
                if len(val) > 10:
                    return val

    # Try common config locations
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


def generate_posts(topic: str, model: str = None) -> list:
    """Generate LinkedIn posts using OpenRouter API with model fallback."""
    api_key = get_api_key()
    if not api_key:
        print("❌ Error: OpenRouter API key not found.")
        print("   Set OPENROUTER_API_KEY environment variable or add to OpenClaw config.")
        sys.exit(1)

    models = [model] if model else MODEL_CHAIN

    for m in models:
        print(f"🤖 Trying model: {m}")
        try:
            response = requests.post(
                OPENROUTER_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": m,
                    "messages": [
                        {"role": "user", "content": POST_GENERATION_PROMPT.format(topic=topic)}
                    ],
                    "temperature": 0.8,
                    "max_tokens": 2000,
                },
                timeout=60,
            )

            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                # Parse JSON response
                try:
                    posts = json.loads(content)
                    print(f"✅ Generated {len(posts)} posts with {m}")
                    return posts
                except json.JSONDecodeError:
                    # Try to extract JSON from markdown fences
                    clean = content.strip()
                    if clean.startswith("```"):
                        clean = clean.split("\n", 1)[1]
                    if clean.endswith("```"):
                        clean = clean.rsplit("\n", 1)[0]
                    try:
                        posts = json.loads(clean)
                        print(f"✅ Generated {len(posts)} posts with {m}")
                        return posts
                    except json.JSONDecodeError:
                        print(f"⚠️ Could not parse response from {m}, trying next...")
                        continue
            else:
                print(f"⚠️ {m} returned {response.status_code}: {response.text[:100]}")
                continue

        except requests.exceptions.Timeout:
            print(f"⚠️ {m} timed out, trying next...")
            continue
        except requests.exceptions.RequestException as e:
            print(f"⚠️ {m} error: {e}, trying next...")
            continue

    print("❌ All models failed. Check your API key and internet connection.")
    sys.exit(1)


def save_posts(topic: str, posts: list, output_dir: str = None):
    """Save generated posts to a markdown file."""
    if output_dir is None:
        output_dir = "/root/.openclaw/workspace/outputs"
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_topic = topic.lower().replace(" ", "_")[:30]
    filename = f"{output_dir}/linkedin_posts_{safe_topic}_{timestamp}.md"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# LinkedIn Posts — {topic}\n\n")
        f.write(f"Generated: {datetime.utcnow().isoformat()}Z\n\n")
        f.write("---\n\n")

        for i, post_data in enumerate(posts, 1):
            style = post_data.get("style", "general")
            content = post_data.get("post", "")
            f.write(f"## Post {i} ({style})\n\n")
            f.write(f"{content}\n\n")
            f.write("---\n\n")

    print(f"✅ Saved to {filename}")
    return filename


def main():
    parser = argparse.ArgumentParser(
        description="Generate 5 LinkedIn posts from a topic"
    )
    parser.add_argument("--topic", required=True, help="Topic for the posts")
    parser.add_argument(
        "--model", default=None, help="Specific model to use (default: auto-fallback)"
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory (default: /root/.openclaw/workspace/outputs)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="OpenRouter API key (or set OPENROUTER_API_KEY env var)",
    )
    args = parser.parse_args()
    
    if args.api_key:
        global OPENROUTER_API_KEY
        OPENROUTER_API_KEY = args.api_key

    print(f"📝 Generating LinkedIn posts for: {args.topic}")
    posts = generate_posts(args.topic, model=args.model)
    filepath = save_posts(args.topic, posts, output_dir=args.output_dir)

    # Print preview
    print("\n📋 Preview:")
    for i, post_data in enumerate(posts, 1):
        style = post_data.get("style", "general")
        content = post_data.get("post", "")[:100]
        print(f"  Post {i} ({style}): {content}...")


if __name__ == "__main__":
    main()
