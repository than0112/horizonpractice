import json
import os
from scripts.ollama_score import score
from scripts.affiliate_engine import inject

def run():
    os.makedirs("data", exist_ok=True)

    if not os.path.exists("data/cache.json"):
        with open("data/cache.json", "w") as f:
            json.dump({"articles": []}, f)

    with open("data/cache.json", "r") as f:
        data = json.load(f)

    for a in data["articles"]:
        s = score(a["title"] + a.get("summary", ""))
        a["score"] = s.get("score", 0)

        topic = "AI" if "AI" in a["title"] else "coding"

        try:
            inject(a, topic)
        except Exception as e:
            print(f"inject failed: {e}")

    with open("data/cache.json", "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    run()