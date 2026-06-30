import json

def main():
    data = json.load(open("data/cache.json"))

    md = ["# AI Daily Report\n"]

    for a in data["articles"][:5]:
        md.append(f"## {a['title']}")
        md.append(a.get("summary",""))

        if "affiliate" in a:
            md.append("### tools")
            md += a["affiliate"]

    open("output/vocus.md","w").write("\n".join(md))

if __name__ == "__main__":
    main()