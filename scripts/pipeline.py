import json
from ollama_score import score
from affiliate_engine import inject

def run():
    data = json.load(open("data/cache.json"))

    for a in data["articles"]:
        s = score(a["title"] + a.get("summary",""))
        a["score"] = s["score"]

        topic = "AI" if "AI" in a["title"] else "coding"
        inject(a, topic)

    json.dump(data, open("data/cache.json","w"))

if __name__ == "__main__":
    run()