import json
import re
import requests
from requests.exceptions import RequestException

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3.1"


def is_available() -> bool:
    try:
        requests.get("http://localhost:11434", timeout=3)
        return True
    except Exception:
        return False


def generate(prompt: str, model: str = DEFAULT_MODEL, timeout: int = 90) -> str:
    """Call Ollama and return the response text. Returns empty string on failure."""
    try:
        resp = requests.post(OLLAMA_URL, json={
            "model": model,
            "prompt": prompt,
            "stream": False
        }, timeout=timeout)
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except RequestException:
        return ""


def generate_json(prompt: str, model: str = DEFAULT_MODEL, timeout: int = 90) -> dict:
    """Call Ollama and parse JSON from the response. Returns empty dict on failure."""
    raw = generate(prompt, model=model, timeout=timeout)
    if not raw:
        return {}

    # Try direct parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Extract first JSON object from text
    start = raw.find("{")
    if start == -1:
        return {}

    depth = 0
    in_string = False
    escaped = False

    for i, ch in enumerate(raw[start:], start=start):
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(raw[start:i + 1])
                except json.JSONDecodeError:
                    break

    # Last resort: try to extract key values with regex
    result = {}
    for key in ["headline", "hook", "key_development", "impact", "trend", "action"]:
        m = re.search(rf'"{key}"\s*:\s*"([^"]+)"', raw)
        if m:
            result[key] = m.group(1)

    return result
