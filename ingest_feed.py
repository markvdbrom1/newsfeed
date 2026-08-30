#!/usr/bin/env python3
"""
ingest_feed.py

Adapter for when you already have a combined RSS feed (e.g. hosted on
GitHub Pages, built with feedgen or similar) instead of running
gather_content.py locally. Converts that feed into the same
content_<date>.json shape that curate_content.py expects, so the rest
of the pipeline doesn't need to change.

Two ways to point this at your feed:
  - PODCAST_FEED_PATH: a local file path, e.g. "output/feed.xml" — use
    this in GitHub Actions when the feed-generating step runs in the same
    repo/checkout. Faster and more reliable than fetching your own public
    URL over the network. Takes priority if both are set.
  - PODCAST_FEED_URL: a remote URL, e.g.
    "https://markvdbrom1.github.io/newsfeed/feed.xml" — use this if the
    feed lives in a different repo/host than this pipeline runs in.

Usage:
    export PODCAST_FEED_PATH=output/feed.xml
    python3 ingest_feed.py

Output:
    podcast_data/content_<date>.json

Note: this writes to "podcast_data/" by default, NOT "output/" — that's
deliberate. If your feed-generating repo publishes "output/" via GitHub
Pages, we don't want to dump pipeline working files into a folder that's
being served publicly. Override with PODCAST_OUTPUT_DIR if you want
something else.
"""

import os
import re
import json
import urllib.request
from datetime import datetime, timedelta, timezone

import feedparser

FEED_PATH = os.environ.get("PODCAST_FEED_PATH")
FEED_URL = os.environ.get("PODCAST_FEED_URL")
MAX_AGE_HOURS = int(os.environ.get("PODCAST_MAX_AGE_HOURS", "48"))
OUTPUT_DIR = os.environ.get("PODCAST_OUTPUT_DIR", "podcast_data")


def clean_summary(raw_summary: str) -> str:
    text = re.sub(r"<[^>]+>", "", raw_summary or "")
    text = text.replace("&nbsp;", " ")
    return re.sub(r"\s+", " ", text).strip()


def normalize_title(title: str) -> str:
    title = re.sub(r"\s*-\s*[^-]+$", "", title)
    title = re.sub(r"[^a-z0-9\s]", "", title.lower())
    return re.sub(r"\s+", " ", title).strip()


def parse_published(entry) -> datetime:
    if getattr(entry, "published_parsed", None):
        return datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def entry_topic(entry) -> str:
    tags = getattr(entry, "tags", None)
    if tags:
        return tags[0].get("term", "general")
    return "general"


def main():
    if not FEED_PATH and not FEED_URL:
        raise RuntimeError(
            "Neither PODCAST_FEED_PATH nor PODCAST_FEED_URL is set. "
            "Set one, e.g. export PODCAST_FEED_PATH=output/feed.xml "
            "(local, same repo) or "
            "export PODCAST_FEED_URL=https://your-feed-url/feed.xml (remote)."
        )

    if FEED_PATH:
        print(f"Reading feed from local path: {FEED_PATH}")
        with open(FEED_PATH, "rb") as f:
            raw_bytes = f.read()
        source_label = FEED_PATH
    else:
        # Fetch with a normal User-Agent — some hosts (incl. GitHub Pages
        # CDNs) are picky about the default urllib/feedparser UA.
        req = urllib.request.Request(FEED_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw_bytes = resp.read()
        source_label = FEED_URL

    feed = feedparser.parse(raw_bytes)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)

    seen_titles = set()
    stories = []

    print(f"Fetched {len(feed.entries)} raw entries from {source_label}")
    print(f"Cutoff: stories published after {cutoff.isoformat()}\n")

    for entry in feed.entries:
        published = parse_published(entry)
        if published < cutoff:
            continue

        norm = normalize_title(entry.title)
        if norm in seen_titles:
            continue
        seen_titles.add(norm)

        stories.append({
            "topic": entry_topic(entry),
            "title": entry.title,
            "source": getattr(entry, "source", {}).get("title", "Unknown")
                      if hasattr(entry, "source") else "Unknown",
            "link": entry.link,
            "published": published.isoformat(),
            "summary": clean_summary(getattr(entry, "summary", "")),
        })

    topics_seen = sorted(set(s["topic"] for s in stories))
    print(f"Kept {len(stories)} stories after dedupe/age filtering")
    print(f"Topics/categories present: {topics_seen}\n")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = os.path.join(OUTPUT_DIR, f"content_{date_str}.json")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "date": date_str,
            "topics": topics_seen,
            "story_count": len(stories),
            "stories": stories,
        }, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(stories)} stories to {out_path}")


if __name__ == "__main__":
    main()