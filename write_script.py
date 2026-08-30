#!/usr/bin/env python3
"""
write_script.py

Turns today's stories (from ingest_feed.py) into a spoken-word podcast
script. Since the source feed is already scoped to your interests via its
own config, no separate curation/relevance step is needed here — this
just organizes and narrates what's already in content_<date>.json.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 write_script.py

Input:
    podcast_data/content_<date>.json   (from ingest_feed.py)

Output:
    podcast_data/script_<date>.txt     (plain spoken-word script, ready for TTS)

Note: uses "podcast_data/" by default, matching ingest_feed.py — kept
separate from any "output/" folder your feed repo publishes via GitHub
Pages, so pipeline working files don't end up public.
"""

import os
import glob
import json

import requests

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
MODEL = os.environ.get("PODCAST_SCRIPT_MODEL", "claude-sonnet-5")
OUTPUT_DIR = os.environ.get("PODCAST_OUTPUT_DIR", "podcast_data")
PODCAST_NAME = os.environ.get("PODCAST_NAME", "Your Daily Briefing")
MAX_STORIES = int(os.environ.get("PODCAST_MAX_STORIES", "8"))
HOST_STYLE = os.environ.get(
    "PODCAST_HOST_STYLE",
    "warm, direct, and a little conversational — like a smart friend catching "
    "you up, not a news anchor. Contractions are fine. No forced enthusiasm."
)

API_URL = "https://api.anthropic.com/v1/messages"


def latest_content_file() -> str:
    files = sorted(glob.glob(os.path.join(OUTPUT_DIR, "content_*.json")))
    if not files:
        raise FileNotFoundError(
            f"No content_*.json found in {OUTPUT_DIR}/. Run ingest_feed.py first."
        )
    return files[-1]


def build_prompt(stories: list, date_str: str) -> str:
    story_block = "\n\n".join(
        f"Story {i+1} (category: {s['topic']}):\n"
        f"Headline: {s['title']}\n"
        f"Summary: {s['summary']}"
        for i, s in enumerate(stories)
    )

    return f"""Write a spoken-word podcast script for a daily personal news
briefing called "{PODCAST_NAME}", for the date {date_str}.

Host style: {HOST_STYLE}

Structure:
- A short, natural intro (mention it's today's briefing, don't over-explain
  the format)
- Cover each story below in the order given, with a smooth spoken
  transition into each one. Group related stories together if a few share
  a theme, rather than treating every headline as a hard cut.
- A brief, natural sign-off

Stories to cover:

{story_block}

CRITICAL formatting rules — this text will go straight into a
text-to-speech engine:
- Plain spoken prose only. No markdown, no headers, no bullet points, no
  asterisks, no stage directions like "[pause]" or "(laughs)".
- No sound effect or music cues.
- Spell out anything that wouldn't read naturally aloud (odd acronyms,
  symbols) — otherwise normal text is fine.
- Do not include a title line — start directly with the spoken intro.
- Aim for roughly {max(150, len(stories) * 100)} words total — concise, not padded."""


def call_claude(prompt: str) -> str:
    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Export it, or add it as a GitHub Actions secret."
        )

    response = requests.post(
        API_URL,
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": MODEL,
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    return "".join(
        block["text"] for block in data["content"] if block.get("type") == "text"
    ).strip()


def main():
    content_path = latest_content_file()
    with open(content_path, "r", encoding="utf-8") as f:
        content = json.load(f)

    stories = content["stories"][:MAX_STORIES]
    date_str = content["date"]

    if not stories:
        print(f"No stories found in {content_path} — nothing to write.")
        return

    print(f"Writing script for {len(stories)} stories from {content_path}...")
    prompt = build_prompt(stories, date_str)
    script_text = call_claude(prompt)

    out_path = os.path.join(OUTPUT_DIR, f"script_{date_str}.txt")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(script_text)

    word_count = len(script_text.split())
    est_minutes = word_count / 150

    print(f"\nWrote script to {out_path}")
    print(f"({word_count} words, ~{est_minutes:.1f} min at a natural speaking pace)")
    print(f"\n--- Preview ---\n{script_text[:400]}...\n")


if __name__ == "__main__":
    main()