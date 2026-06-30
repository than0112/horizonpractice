AFFILIATE_MAP = {
    "AI": ["ChatGPT Plus", "Prompt Engineering Book"],
    "coding": ["GitHub Copilot", "Udemy Python Course"]
}

def inject(article, topic):
    article["affiliate"] = AFFILIATE_MAP.get(topic, [])
    return article