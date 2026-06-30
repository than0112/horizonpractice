import re
from scripts.utils.ollama_client import generate_json, is_available

_SCORE_PROMPT = """You are an AI content curator for a tech-savvy audience in Taiwan.
Score this article on three dimensions and classify it. Output ONLY valid JSON:
{{
  "score": <0-10 overall importance>,
  "reason": "<one sentence why>",
  "audience_fit": <0-10 relevance to Taiwan AI/tech readers>,
  "trending_potential": <0-10 likelihood to trend in next 48h>,
  "content_type": "<one of: breakthrough|product|research|opinion|business|other>"
}}

Article: {text}"""

_FALLBACK_PATTERNS = [
    (r'"score"\s*:\s*(\d+)', "score"),
    (r'score[:\s]+(\d+)', "score"),
    (r'(\d+)\s*/\s*10', "score"),
]


def _fallback(raw: str) -> dict:
    result = {"score": 0, "reason": raw[:200], "audience_fit": 0,
              "trending_potential": 0, "content_type": "unknown"}
    for pattern, _ in _FALLBACK_PATTERNS:
        m = re.search(pattern, raw, re.IGNORECASE)
        if m:
            result["score"] = min(int(m.group(1)), 10)
            break
    return result


def score(text: str) -> dict:
    if not is_available():
        return {"score": 0, "reason": "Ollama unavailable", "audience_fit": 0,
                "trending_potential": 0, "content_type": "unknown"}

    prompt = _SCORE_PROMPT.format(text=text[:600])
    result = generate_json(prompt, timeout=30)

    if result and "score" in result:
        result["score"] = min(int(result.get("score", 0)), 10)
        result["audience_fit"] = min(int(result.get("audience_fit", 0)), 10)
        result["trending_potential"] = min(int(result.get("trending_potential", 0)), 10)
        valid_types = {"breakthrough", "product", "research", "opinion", "business", "other"}
        if result.get("content_type") not in valid_types:
            result["content_type"] = "other"
        return result

    # generate_json failed to parse — try raw text fallback
    from scripts.utils.ollama_client import generate
    raw = generate(prompt, timeout=30)
    return _fallback(raw) if raw else _fallback("")
