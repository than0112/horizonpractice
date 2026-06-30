import json
from collections import defaultdict

clicks = defaultdict(int)

# 讀 click log
try:
    for line in open("output/clicks.jsonl"):
        item = json.loads(line)["item"]
        clicks[item] += 1
except:
    pass

# 假設 EPC（每次點擊收入）
EPC = {
    "chatgpt-course": 0.8,
    "copilot": 1.2,
    "ai-tools": 0.5
}

data = []

for item, count in clicks.items():
    revenue = count * EPC.get(item, 0.3)

    data.append({
        "item": item,
        "clicks": count,
        "revenue": round(revenue, 2)
    })

# Top 10 sorting
data = sorted(data, key=lambda x: x["revenue"], reverse=True)[:10]

json.dump(data, open("dashboard/data.json", "w"), indent=2)