import json
import urllib.request

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.1"

def score(text):
    prompt = f"""
Score 0-10 importance.

Return JSON:
{{
  "score": number,
  "reason": string
}}

Text:
{text}
"""

    res = requests.post(OLLAMA_URL, json={
        "model": MODEL,
        "prompt": prompt,
        "stream": False
    })

    return json.loads(res.json()["response"])