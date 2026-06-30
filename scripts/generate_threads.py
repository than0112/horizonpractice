import json
import os
import html
import re

from scripts.utils.ollama_client import is_available, generate

THREADS_PROMPT = """你是台灣最有影響力的 AI 科技評論員。根據以下新聞，照這個結構寫一則 Threads 貼文：

[開場句]
要求：≤15 個字。不能有「你知道嗎」「最近有篇文章」「根據報導」。
要直接、衝擊、讓人想繼續讀。
像這樣：「Meta 偷偷用 Gemini 跑了一整年。」
或這樣：「用 AI 寫程式碼，其實讓你變笨。」

[分析段落，3-5 句]
說出大多數人忽略的角度。表達你的立場，不是轉述。
指出為什麼大眾的第一反應可能是錯的。
嚴禁捏造事實，只根據提供的資訊分析。

[結尾問句]
一個具體的問題，針對這篇新聞，讓讀者想留言。
不能用「你覺得呢」「分享你的看法」「這對你有什麼影響」。
要像這樣：「如果你是 Meta 工程師，這週你會更新履歷嗎？」
或這樣：「你現在還敢把核心業務押在第三方 AI 上嗎？」

[hashtag]
2 個繁體中文 hashtag

---
總字數 150-220 字。不要輸出任何括號或格式說明，直接寫貼文內容。

新聞：{title}
{summary_section}"""


def _clean(text: str) -> str:
    if not text:
        return ""
    text = str(text)
    text = re.sub(r"<.*?>", "", text)
    text = html.unescape(text)
    noise = [r"submitted by.*", r"\[link\]", r"\[comments\]", r"comments", r"share", r"permalink"]
    for n in noise:
        text = re.sub(n, "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _truncate(text: str, max_chars: int = 500) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "..."


def _trim_to_limit(text: str, max_chars: int = 300) -> str:
    """Trim generated post to stay within platform character limit."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_period = max(truncated.rfind("。"), truncated.rfind("！"), truncated.rfind("？"))
    if last_period > 100:
        return text[:last_period + 1]
    return truncated.rstrip() + "…"


def _clean_post(text: str) -> str:
    """Strip format labels that LLM sometimes outputs literally."""
    # Remove lines that are just section labels like "Hook：" "CTA：" "[開場句]" etc.
    label_pattern = re.compile(
        r"^(hook|cta|開場句|分析|結尾|hashtag|洞察|觀點|反直覺)[：:）\]】]?\s*$",
        re.IGNORECASE | re.MULTILINE
    )
    text = label_pattern.sub("", text)
    # Remove markdown bold/italic markers
    text = re.sub(r"\*{1,2}(.+?)\*{1,2}", r"\1", text)
    # Collapse multiple blank lines into one
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _format_affiliate(items) -> str:
    if not items:
        return ""
    if isinstance(items, list):
        return "\n".join(f"• {i}" for i in items)
    return str(items)


def _summary_section(article: dict) -> str:
    summary = _truncate(_clean(article.get("summary", "")), 400)
    link = article.get("link", "")
    if summary:
        return f"重點：{summary}"
    if link:
        return f"來源：{link}\n（只有標題，請根據標題意涵評論，不要自行補充不存在的細節）"
    return "（只有標題，請根據標題意涵評論，不要自行補充不存在的細節）"


def _generate_post_llm(article: dict) -> str:
    title = _truncate(_clean(article.get("title", "")), 150)
    prompt = THREADS_PROMPT.format(title=title, summary_section=_summary_section(article))
    result = generate(prompt, timeout=90)
    if result and len(result) > 50:
        result = _clean_post(result)
        return _trim_to_limit(result, max_chars=300)
    return ""


def _fallback_post(article: dict) -> str:
    title = _clean(article.get("title", ""))
    summary = _clean(article.get("summary", ""))
    affiliate = _format_affiliate(article.get("affiliate"))

    return f"""🧠 值得關注的 AI 動態：

🔥 {title}

───
📌 重點：
{summary}

───
💡 延伸資源：
{affiliate if affiliate else "無"}

#AI #科技 #人工智慧"""


def main(published: set[str] | None = None) -> list[str]:
    """Generate threads.txt. Returns list of article links that were published."""
    os.makedirs("output", exist_ok=True)
    published = published or set()

    try:
        with open("data/cache.json", "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        raw = {}

    if isinstance(raw, dict) and "articles" in raw:
        articles = raw["articles"]
    elif isinstance(raw, dict):
        articles = list(raw.values())
    else:
        articles = []

    unpublished = [a for a in articles if a.get("link", a.get("title")) not in published]
    top = sorted(unpublished, key=lambda a: (
        a.get("score", 0) * 0.5 +
        a.get("audience_fit", 0) * 0.3 +
        a.get("trending_potential", 0) * 0.2
    ), reverse=True)[:3]

    if not top:
        top = [{"title": "No data available", "summary": "System fallback content", "score": 0, "affiliate": []}]

    llm_online = is_available()
    if not llm_online:
        print("WARNING: Ollama unavailable — using fallback templates")

    posts = []
    used_links = []
    for i, article in enumerate(top, 1):
        print(f"  Generating thread {i}/{len(top)}: {article.get('title', '')[:60]}...")
        if llm_online:
            post = _generate_post_llm(article)
            if not post:
                print("    -> LLM returned empty, using fallback")
                post = _fallback_post(article)
        else:
            post = _fallback_post(article)
        posts.append(post)
        link = article.get("link") or article.get("title", "")
        if link:
            used_links.append(link)

    with open("output/threads.txt", "w", encoding="utf-8") as f:
        f.write("\n\n---\n\n".join(posts))

    print(f"THREADS GENERATED OK ({len(posts)} posts)")
    return used_links


if __name__ == "__main__":
    main()
