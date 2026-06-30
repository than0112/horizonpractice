"""Output quality validator — run after pipeline to check generated files."""
import os
import re
import sys


def _count_words(text: str) -> int:
    return len(text.split())


def validate_vocus(path: str = "output/vocus.md") -> list[str]:
    issues = []

    if not os.path.exists(path):
        return [f"MISSING: {path}"]

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    if not content.strip():
        return [f"EMPTY: {path}"]

    # Count articles (## headings)
    articles = re.findall(r"^## .+", content, re.MULTILINE)
    if len(articles) < 3:
        issues.append(f"vocus: only {len(articles)} articles (expected ≥ 3)")

    # Check total word count
    word_count = _count_words(content)
    if word_count < 500:
        issues.append(f"vocus: only {word_count} words total (expected ≥ 500)")

    # Check for fallback markers
    fallback_count = content.count("[LLM Unavailable")
    if fallback_count > 0:
        issues.append(f"vocus: {fallback_count} article(s) used LLM fallback")

    # Check for hardcoded boilerplate (sign of old template)
    if "This reflects a broader shift in AI + developer tooling ecosystem." in content:
        issues.append("vocus: contains old hardcoded boilerplate — template not replaced")

    return issues


def validate_threads(path: str = "output/threads.txt") -> list[str]:
    issues = []

    if not os.path.exists(path):
        return [f"MISSING: {path}"]

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    if not content.strip():
        return [f"EMPTY: {path}"]

    posts = [p.strip() for p in content.split("---") if p.strip()]

    if len(posts) < 3:
        issues.append(f"threads: only {len(posts)} posts (expected 3)")

    for i, post in enumerate(posts, 1):
        char_count = len(post)
        if char_count < 80:
            issues.append(f"threads: post {i} too short ({char_count} chars)")
        if char_count > 350:
            issues.append(f"threads: post {i} too long ({char_count} chars, limit ~300)")

    # Check if all posts are identical (sign of stuck generation)
    if len(posts) >= 2 and len(set(posts)) == 1:
        issues.append("threads: all posts are identical")

    return issues


def main():
    vocus_issues = validate_vocus()
    thread_issues = validate_threads()
    all_issues = vocus_issues + thread_issues

    if all_issues:
        print("WARNING: Output validation issues:")
        for issue in all_issues:
            print(f"   - {issue}")
        sys.exit(0)
    else:
        print("OK: Output validation passed")
        sys.exit(0)


if __name__ == "__main__":
    main()
