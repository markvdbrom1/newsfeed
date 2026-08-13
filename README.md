# Personalized News Feed

A single RSS feed, built from a list of keywords/phrases you control, refreshed
automatically on a schedule via GitHub Actions and served for free via GitHub
Pages.

How it works: `generate_feed.py` reads `config.yaml`, queries Google News'
public RSS search endpoint for each keyword, merges the results, drops
duplicates and anything older than `max_age_days`, sorts by recency, and
writes `docs/feed.xml`. A scheduled GitHub Action re-runs this and commits the
updated file, so the feed URL always reflects your keywords.

## 1. Create the repo

1. Create a new **public** GitHub repository (Pages on the free tier requires
   public, unless you have GitHub Pro/Team/Enterprise).
2. Push all the files in this folder to it (root of the `main` branch).

```bash
cd personalized-news-feed
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

## 2. Enable GitHub Pages

In the repo: **Settings → Pages → Build and deployment → Source**: select
"Deploy from a branch", branch `main`, folder `/docs`. Save.

Your feed will then be live at:
```
https://YOUR_USERNAME.github.io/YOUR_REPO/feed.xml
```

## 3. Allow the workflow to commit

In the repo: **Settings → Actions → General → Workflow permissions**, select
"Read and write permissions". This lets the scheduled job push the updated
`feed.xml` back to the repo.

## 4. Set your keywords

Edit `config.yaml`:

```yaml
keywords:
  - "generative AI"
  - "climate policy"
  - "Formula 1"
```

One keyword or phrase per line. These are passed straight through as Google
News search queries, so you can use quotes for exact phrases, `-word` to
exclude terms, `site:domain.com` to restrict to a source, etc.

Also update `feed.link` to your actual Pages URL from step 2, and adjust
`max_items`, `max_age_days`, or `items_per_keyword` if you want more/less
volume.

Commit and push — the workflow runs automatically on any push that changes
`config.yaml`, and also every 3 hours on its own.

## 5. Subscribe

Add `https://YOUR_USERNAME.github.io/YOUR_REPO/feed.xml` to any RSS reader
(Feedly, Inoreader, NetNewsWire, etc.).

## Running it locally (optional)

```bash
pip install -r requirements.txt
python generate_feed.py --config config.yaml --out docs/feed.xml
```

## Adjusting the schedule

Edit the `cron` line in `.github/workflows/update-feed.yml`. Cron is in UTC.
Examples:
- `"0 * * * *"` — every hour
- `"0 8,20 * * *"` — twice a day (8am/8pm UTC)

## Notes / limitations

- Google News RSS search has no official rate limits published, but avoid
  cranking the schedule to run every few minutes — every-3-hours is plenty
  for "interesting news," and being a good citizen keeps this reliable.
- If a keyword returns nothing (typo, too narrow), the script logs a warning
  and continues with the rest rather than failing the whole run.
- Swap in other RSS sources by editing `fetch_keyword_items()` in
  `generate_feed.py` if you'd rather pull from specific publications instead
  of/alongside Google News.
