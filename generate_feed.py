#!/usr/bin/env python3
"""
Generate a single personalized RSS feed from a list of keywords/phrases.

For each keyword in config.yaml, this queries Google News' RSS search
endpoint (which requires no API key), merges the results, removes
duplicates, drops anything older than max_age_days, sorts by recency,
and writes a combined RSS file to docs/feed.xml (served via GitHub Pages).

Usage:
    python generate_feed.py [--config config.yaml] [--out docs/feed.xml]
"""

import argparse
import hashlib
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from urllib.parse import quote_plus

import feedparser
import yaml
from feedgen.feed import FeedGenerator

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl={lang}&gl={country}&ceid={country}:{lang_short}"


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not cfg or "keywords" not in cfg or not cfg["keywords"]:
        raise ValueError("config.yaml must define a non-empty 'keywords' list")
    cfg.setdefault("feed", {})
    cfg["feed"].setdefault("title", "My Personalized News")
    cfg["feed"].setdefault("description", "Curated news based on my interests")
    cfg["feed"].setdefault("link", "https://example.com/feed.xml")
    cfg["feed"].setdefault("max_items", 60)
    cfg["feed"].setdefault("max_age_days", 3)
    cfg["feed"].setdefault("items_per_keyword", 10)
    cfg["feed"].setdefault("language", "en-US")
    cfg["feed"].setdefault("country", "US")
    return cfg


def build_query_url(keyword, language, country):
    lang_short = language.split("-")[0]
    return GOOGLE_NEWS_RSS.format(
        query=quote_plus(keyword),
        lang=language,
        country=country,
        lang_short=lang_short,
    )


def normalize_title(title):
    """Lowercase, strip punctuation/source suffix, collapse whitespace — used for dedup."""
    title = re.sub(r"\s*-\s*[^-]+$", "", title)  # Google News appends " - Source Name"
    title = re.sub(r"[^\w\s]", "", title.lower())
    return re.sub(r"\s+", " ", title).strip()


def entry_id(entry):
    link = getattr(entry, "link", "") or ""
    title = normalize_title(getattr(entry, "title", "") or "")
    return hashlib.sha256(f"{link}|{title}".encode("utf-8")).hexdigest()


def parse_published(entry):
    if getattr(entry, "published_parsed", None):
        return datetime.fromtimestamp(time.mktime(entry.published_parsed), tz=timezone.utc)
    return datetime.now(tz=timezone.utc)


def fetch_keyword_items(keyword, cfg):
    url = build_query_url(keyword, cfg["feed"]["language"], cfg["feed"]["country"])
    try:
        parsed = feedparser.parse(url)
    except Exception as e:
        print(f"  [warn] failed to fetch '{keyword}': {e}", file=sys.stderr)
        return []

    if getattr(parsed, "bozo", False) and not parsed.entries:
        print(f"  [warn] no results / parse issue for '{keyword}'", file=sys.stderr)
        return []

    items = []
    for entry in parsed.entries[: cfg["feed"]["items_per_keyword"]]:
        items.append(
            {
                "id": entry_id(entry),
                "title": getattr(entry, "title", "(untitled)"),
                "link": getattr(entry, "link", ""),
                "summary": getattr(entry, "summary", ""),
                "published": parse_published(entry),
                "source_keyword": keyword,
            }
        )
    return items


def collect_all_items(cfg):
    all_items = {}
    for keyword in cfg["keywords"]:
        print(f"Fetching: {keyword}")
        for item in fetch_keyword_items(keyword, cfg):
            # First occurrence wins; later duplicate keywords just get skipped
            all_items.setdefault(item["id"], item)

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=cfg["feed"]["max_age_days"])
    fresh = [it for it in all_items.values() if it["published"] >= cutoff]
    fresh.sort(key=lambda it: it["published"], reverse=True)
    return fresh[: cfg["feed"]["max_items"]]


def build_feed_xml(items, cfg, out_path):
    fg = FeedGenerator()
    fg.title(cfg["feed"]["title"])
    fg.link(href=cfg["feed"]["link"], rel="self")
    fg.description(cfg["feed"]["description"])
    fg.language(cfg["feed"]["language"].split("-")[0])
    fg.lastBuildDate(datetime.now(tz=timezone.utc))

    for item in items:
        fe = fg.add_entry()
        fe.id(item["link"] or item["id"])
        fe.title(item["title"])
        if item["link"]:
            fe.link(href=item["link"])
        if item["summary"]:
            fe.description(item["summary"])
        fe.pubDate(item["published"])
        fe.category(term=item["source_keyword"])

    fg.rss_file(out_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--out", default="docs/feed.xml")
    args = parser.parse_args()

    cfg = load_config(args.config)
    items = collect_all_items(cfg)
    print(f"\nCollected {len(items)} items after dedup/filter/sort.")
    build_feed_xml(items, cfg, args.out)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
