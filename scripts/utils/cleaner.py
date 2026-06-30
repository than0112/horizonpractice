import re
import html

def clean_content(text):
    if not text:
        return ""

    text = str(text)

    text = re.sub(r"<.*?>", "", text)
    text = html.unescape(text)

    noise = [
        r"submitted by.*",
        r"\[link\]",
        r"\[comments\]",
        r"comments",
        r"share",
        r"permalink"
    ]

    for n in noise:
        text = re.sub(n, "", text, flags=re.IGNORECASE)

    text = re.sub(r"\s+", " ", text)

    return text.strip()