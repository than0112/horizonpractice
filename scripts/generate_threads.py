import json

def main():
    data = json.load(open("data/cache.json"))

    top = sorted(data["articles"], key=lambda x: x["score"], reverse=True)[:3]

    out = []

    for a in top:
        out.append(f"""
我發現一個現象：

{a['title']}

→ {a.get('summary','')}

延伸資源：
{a.get('affiliate', [])}
""")

    open("output/threads.txt","w").write("\n---\n".join(out))

if __name__ == "__main__":
    main()