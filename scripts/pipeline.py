import json
import os
import re
import html
import shutil
from datetime import datetime, timezone, timedelta

import feedparser

from scripts.ollama_score import score
from scripts.affiliate_engine import inject
import scripts.generate_threads as generate_threads
import scripts.vocus as vocus

# -------------------------
# CONFIG
# -------------------------
RSS_SOURCES = [
    "https://news.ycombinator.com/rss",
    "https://www.reddit.com/r/artificial/.rss",
    "https://www.reddit.com/r/MachineLearning/.rss",
    "https://feeds.feedburner.com/TechCrunch",
    "https://feeds.bbci.co.uk/news/business/rss.xml",
]

FRESHNESS_DAYS = 14   # articles older than this are dropped
CACHE_RETAIN_DAYS = 30  # max age to keep in cumulative cache
MAX_PER_SOURCE = 5


# -------------------------
# HELPERS
# -------------------------
def _clean(text: str) -> str:
    if not text:
        return ""
    text = str(text)
    text = re.sub(r"<.*?>", "", text)
    text = html.unescape(text)
    for pattern in [r"submitted by.*", r"\[link\]", r"\[comments\]",
                    r"comments", r"share", r"permalink"]:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()


def _entry_date(entry) -> datetime | None:
    for field in ("published_parsed", "updated_parsed"):
        t = entry.get(field)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# -------------------------
# FETCH RSS
# -------------------------
def fetch_rss() -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=FRESHNESS_DAYS)
    articles = []

    for url in RSS_SOURCES:
        try:
            feed = feedparser.parse(url)
            count = 0
            for entry in feed.entries:
                if count >= MAX_PER_SOURCE:
                    break
                dt = _entry_date(entry)
                if dt and dt < cutoff:
                    continue
                title = _clean(entry.get("title", ""))
                if not title:
                    continue
                articles.append({
                    "title": title,
                    "summary": _clean(entry.get("summary") or entry.get("description") or ""),
                    "link": entry.get("link", ""),
                    "source": url,
                    "fetched_at": dt.strftime("%Y-%m-%d") if dt else _today(),
                })
                count += 1
        except Exception as e:
            print(f"[RSS ERROR] {url} -> {e}")

    print(f"  Fetched {len(articles)} fresh articles")
    return articles


# -------------------------
# CACHE  (cumulative, URL-keyed)
# -------------------------
CACHE_PATH = "data/cache.json"
PUBLISHED_PATH = "data/published.json"


def load_cache() -> dict[str, dict]:
    """Return {url: article} dict from cache, dropping articles older than CACHE_RETAIN_DAYS."""
    os.makedirs("data", exist_ok=True)
    try:
        with open(CACHE_PATH, encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return {}

    # Normalise to {url: article} dict
    if isinstance(raw, list):
        # bare list
        by_url = {a.get("link") or a.get("title", ""): a for a in raw if isinstance(a, dict)}
    elif isinstance(raw, dict) and "articles" in raw:
        # legacy {"articles": [...]} format
        by_url = {a.get("link") or a.get("title", ""): a for a in raw["articles"] if isinstance(a, dict)}
    else:
        # already {url: article} dict
        by_url = {k: v for k, v in raw.items() if isinstance(v, dict)}

    cutoff = (datetime.now(timezone.utc) - timedelta(days=CACHE_RETAIN_DAYS)).strftime("%Y-%m-%d")
    return {url: a for url, a in by_url.items() if a.get("fetched_at", "9999") >= cutoff}


def save_cache(cache: dict[str, dict]) -> None:
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    # Also write legacy list format for dashboard / report consumers
    article_list = sorted(cache.values(), key=lambda a: a.get("score", 0), reverse=True)
    legacy = {"articles": article_list}
    os.makedirs("output", exist_ok=True)
    os.makedirs("dashboard", exist_ok=True)
    for path in ["output/report.json", "dashboard/latest.json"]:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(legacy, f, ensure_ascii=False, indent=2)


def merge_into_cache(cache: dict[str, dict], fresh: list[dict]) -> tuple[dict[str, dict], int]:
    """Add new articles; skip if URL already exists. Returns (updated_cache, new_count)."""
    new_count = 0
    for a in fresh:
        key = a.get("link") or a["title"]  # fallback to title if no link
        if key not in cache:
            cache[key] = a
            new_count += 1
    return cache, new_count


# -------------------------
# PUBLISHED TRACKING  (Task 2.3)
# -------------------------
def load_published() -> set[str]:
    try:
        with open(PUBLISHED_PATH, encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()


def save_published(published: set[str]) -> None:
    with open(PUBLISHED_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(published), f, ensure_ascii=False, indent=2)


def mark_published(urls: list[str]) -> None:
    published = load_published()
    published.update(urls)
    save_published(published)


# -------------------------
# ARCHIVE  (Task 2.1)
# -------------------------
def archive_outputs() -> None:
    today = _today()
    archive_dir = "output/archive"
    os.makedirs(archive_dir, exist_ok=True)
    for src, dst in [
        ("output/vocus.md",    f"{archive_dir}/vocus_{today}.md"),
        ("output/threads.txt", f"{archive_dir}/threads_{today}.txt"),
    ]:
        if os.path.exists(src):
            shutil.copy2(src, dst)


# -------------------------
# MAIN PIPELINE
# -------------------------
def run():
    print("STEP 1: fetching RSS...")
    fresh = fetch_rss()

    print("STEP 2: merging into cumulative cache...")
    cache = load_cache()
    cache, new_count = merge_into_cache(cache, fresh)
    published = load_published()
    print(f"  Cache: {len(cache)} total | {new_count} new | {len(published)} published")

    if not cache:
        cache["__fallback__"] = {
            "title": "Fallback AI News", "summary": "No data available",
            "link": "", "source": "system", "fetched_at": _today()
        }

    print("STEP 3: scoring new articles...")
    for a in cache.values():
        if "score" in a:
            continue  # already scored in a previous run
        try:
            result = score(a["title"] + " " + a.get("summary", ""))
            a.update({
                "score":              result.get("score", 0),
                "score_reason":       result.get("reason", ""),
                "audience_fit":       result.get("audience_fit", 0),
                "trending_potential": result.get("trending_potential", 0),
                "content_type":       result.get("content_type", "unknown"),
            })
            topic = "AI" if "AI" in a["title"] else "coding"
            inject(a, topic)
        except Exception as e:
            print(f"  [SCORE ERROR] {e}")
            a["score"] = 0

    print("STEP 4: saving cache...")
    save_cache(cache)

    print("STEP 5: generating content...")
    thread_links = generate_threads.main(published=published)
    vocus_links  = vocus.main(published=published)
    mark_published(thread_links + vocus_links)
    print(f"  Marked {len(thread_links) + len(vocus_links)} articles as published")

    print("STEP 6: archiving outputs...")
    archive_outputs()

    print("PIPELINE DONE OK")


if __name__ == "__main__":
    run()
