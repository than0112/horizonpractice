import json
import os
import html
import re
from datetime import date

from scripts.utils.ollama_client import is_available, generate, generate_json

SKELETON_PROMPT = """You are a senior tech journalist writing for an AI-savvy audience.
Analyze this article and output ONLY valid JSON with no extra text:
{{
  "headline": "a compelling rewritten title (not the original)",
  "hook": "one sentence explaining why readers should care about this right now",
  "key_development": "what specifically happened — base ONLY on the title and summary provided, do not invent details",
  "impact": "concrete consequence based strictly on what is known from the title/summary",
  "trend": "how this connects to a larger pattern in AI or tech",
  "action": "what readers should watch for or do next",
  "insight": "the single sharpest observation about this story that most people will miss",
  "contrarian": "the counter-intuitive angle — why the obvious read of this story might be wrong",
  "so_what": "one concrete, actionable implication for a developer, founder, or knowledge worker"
}}

Article title: {title}
{summary_section}"""

EXPAND_PROMPT = """You are a senior tech journalist. Expand this article skeleton into a full 500-700 word article.

CRITICAL RULES:
- Write ONLY based on facts in the skeleton and original context — do NOT invent names, numbers, quotes, or events
- If you don't have enough detail, acknowledge that and focus on the broader trend and significance
- Write in engaging, intelligent prose — no bullet points in the body

REQUIRED STRUCTURE (each section must appear, in this order):
1. Hook paragraph — open with the "hook" from the skeleton
2. What Happened — state the key development clearly
3. Why It Matters — expand on impact and trend
4. The Contrarian Take — present the counter-intuitive angle from "contrarian" field
5. The Core Insight — deliver the sharpest observation from "insight" field
6. So What — close with the concrete actionable implication from "so_what" field

Skeleton:
{skeleton}

Original context — Title: {title}
{summary_section}

Write the full article now. Start directly with the content, no preamble."""


def _clean(text: str) -> str:
    if not text:
        return ""
    text = str(text)
    text = re.sub(r"<.*?>", "", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _truncate(text: str, max_chars: int = 800) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "..."


def _format_affiliate(items) -> str:
    if not items:
        return ""
    if isinstance(items, list):
        return "\n".join(f"- {i}" for i in items)
    return str(items)


def _summary_section(article: dict) -> str:
    summary = _truncate(_clean(article.get("summary", "")), 600)
    link = article.get("link", "")
    if summary:
        return f"Summary: {summary}"
    if link:
        return f"Source URL: {link}\n(No summary available — base your analysis strictly on the title and URL context)"
    return "(No summary available — base your analysis strictly on the title)"


def _build_skeleton(article: dict) -> dict:
    title = _truncate(_clean(article.get("title", "")), 200)
    prompt = SKELETON_PROMPT.format(title=title, summary_section=_summary_section(article))
    return generate_json(prompt, timeout=60)


def _expand_article(skeleton: dict, article: dict) -> str:
    title = _truncate(_clean(article.get("title", "")), 200)
    skeleton_str = json.dumps(skeleton, ensure_ascii=False, indent=2)
    prompt = EXPAND_PROMPT.format(skeleton=skeleton_str, title=title, summary_section=_summary_section(article))
    return generate(prompt, timeout=120)


def _fallback_article(article: dict) -> str:
    title = _clean(article.get("title", "No Title"))
    summary = _clean(article.get("summary", "No summary available."))
    affiliate = _format_affiliate(article.get("affiliate", []))
    resources_section = f"\n## Tools & Resources\n{affiliate}\n" if affiliate else ""
    return f"""## {title}

> [LLM Unavailable — showing original summary]

{summary}
{resources_section}"""


def _build_article_llm(article: dict) -> str:
    title = _clean(article.get("title", ""))
    score = article.get("score", 0)
    source = article.get("source", "")
    affiliate = _format_affiliate(article.get("affiliate", []))

    skeleton = _build_skeleton(article)
    if not skeleton:
        return _fallback_article(article)

    headline = skeleton.get("headline") or title
    full_text = _expand_article(skeleton, article)

    if not full_text or len(full_text) < 200:
        # Retry once with a simpler prompt
        summary = _truncate(_clean(article.get("summary", "")), 600)
        simple_prompt = (
            f"Write a 500-word tech analysis article about: {title}\n"
            f"Key points: {summary}\n"
            f"Structure: intro, what happened, why it matters, conclusion."
        )
        full_text = generate(simple_prompt, timeout=120)

    if not full_text:
        return _fallback_article(article)

    resources_section = f"\n## Tools & Resources\n{affiliate}\n" if affiliate else ""
    source_line = f"*Source: {source} | Score: {score}/10*" if source else f"*Score: {score}/10*"

    return f"""## {headline}

{full_text}
{resources_section}
---
{source_line}"""


def main(published: set[str] | None = None) -> list[str]:
    """Generate vocus.md. Returns list of article links that were published."""
    os.makedirs("output", exist_ok=True)
    published = published or set()

    try:
        with open("data/cache.json", "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        raw = {}

    # Support both new dict format and legacy {"articles": [...]} format
    if isinstance(raw, dict) and "articles" in raw:
        articles = raw["articles"]
    elif isinstance(raw, dict):
        articles = list(raw.values())
    else:
        articles = []

    # Exclude already-published, sort by composite score
    unpublished = [a for a in articles if a.get("link", a.get("title")) not in published]
    top = sorted(unpublished, key=lambda a: (
        a.get("score", 0) * 0.5 +
        a.get("audience_fit", 0) * 0.3 +
        a.get("trending_potential", 0) * 0.2
    ), reverse=True)[:5]

    if not top:
        top = [{"title": "No Data Available", "summary": "System fallback content", "affiliate": []}]

    llm_online = is_available()
    if not llm_online:
        print("WARNING: Ollama unavailable — using fallback templates")

    today = date.today().isoformat()
    sections = [f"# AI Daily Report — {today}\n"]

    used_links = []
    for i, article in enumerate(top, 1):
        print(f"  Generating article {i}/{len(top)}: {article.get('title', '')[:60]}...")
        sections.append(_build_article_llm(article) if llm_online else _fallback_article(article))
        link = article.get("link") or article.get("title", "")
        if link:
            used_links.append(link)

    output = "\n\n---\n\n".join(sections)
    with open("output/vocus.md", "w", encoding="utf-8") as f:
        f.write(output)

    print(f"VOCUS GENERATED OK ({len(top)} articles, ~{len(output.split())} words)")
    return used_links


if __name__ == "__main__":
    main()
