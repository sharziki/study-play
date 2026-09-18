#!/usr/bin/env python3
"""Import the STAT 350 course notes into Intellect.

Source: https://treese41528.github.io/STAT350/Website/chapter<N>/index.html
This is the official Purdue STAT 350 (Fall 2026) course website, which carries
the whole curriculum as 13 chapters. The user asked for the full curriculum, not
just the Quiz 3 chapter, so this imports all of it and lets the app's own exam
pressure decide what surfaces first.

Why a custom extractor rather than a generic HTML strip: these are Sphinx/Quarto
style pages where the real content lives in one main/article container, and the
nav sidebars repeat the entire table of contents on every page. Stripping tags
naively imports 13 copies of the site menu as "material", which then generates
garbage questions about navigation links. We target the content container, drop
nav/script/style, and keep math and tables as text.

Ordering matters: chapters are imported in reverse syllabus-proximity order so
the chapter being quizzed today (Ch 5) is imported FIRST and therefore generates
questions first, while the later chapters fill in behind it.
"""
import html
import json
import re
import sys
import urllib.request

SITE = "https://treese41528.github.io/STAT350/Website/"
BASE = SITE + "chapter{}/index.html"
API = "http://127.0.0.1:4173/api/materials"
COURSE = "STAT 350"

# Titles from the official schedule so each material is labeled the way the
# syllabus labels it, not by whatever the <title> tag happens to say.
CHAPTERS = {
    1: "Ch 1 — Introduction",
    2: "Ch 2 — Variables and Graphing",
    3: "Ch 3 — Numerical Summaries",
    4: "Ch 4 — Set Theory, Probability, Conditional Probability, Trees",
    5: "Ch 5 — Random Variables and Discrete Probability Distributions",
    6: "Ch 6 — Continuous Probability Distributions (Exponential, Normal)",
    7: "Ch 7 — Sampling Distributions and the Central Limit Theorem",
    8: "Ch 8 — Experimental Design and Sampling",
    9: "Ch 9 — Point Estimators and Confidence Intervals",
    10: "Ch 10 — Hypothesis Testing (Single Population Mean)",
    11: "Ch 11 — Inference for Two Independent Populations",
    12: "Ch 12 — One-Way ANOVA",
    13: "Ch 13 — Simple Linear Regression",
}

# Quiz 3 (today) covers Ch 5. Import it first, then the chapters already taught,
# then the rest, so the most exam-relevant material generates questions soonest.
ORDER = [5, 4, 3, 2, 1, 6, 7, 8, 9, 10, 11, 12, 13]


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (study-import)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


def extract(raw: str) -> str:
    """Pull the readable body text out of one chapter page."""
    # Kill non-content regions outright, including the repeated nav/TOC.
    for tag in ("script", "style", "nav", "header", "footer", "svg", "form"):
        raw = re.sub(rf"<{tag}\b.*?</{tag}>", " ", raw, flags=re.S | re.I)
    raw = re.sub(r"<aside\b.*?</aside>", " ", raw, flags=re.S | re.I)
    # Prefer the main content container when the theme provides one.
    for pat in (r"<main\b[^>]*>(.*?)</main>",
                r'<div[^>]*class="[^"]*bd-article[^"]*"[^>]*>(.*?)</div>\s*</div>',
                r"<article\b[^>]*>(.*?)</article>"):
        m = re.search(pat, raw, flags=re.S | re.I)
        if m and len(m.group(1)) > 1500:
            raw = m.group(1)
            break
    # Keep block structure as newlines so headings and list items stay separate.
    raw = re.sub(r"</(p|div|li|h[1-6]|tr|section|blockquote)>", "\n", raw, flags=re.I)
    raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
    raw = re.sub(r"</t[dh]>", " | ", raw, flags=re.I)
    raw = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(raw)
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    lines = [ln.strip() for ln in text.splitlines()]
    # Drop the "Copy to clipboard"/anchor noise these themes emit.
    drop = ("copy to clipboard", "toggle navigation", "previous", "next",
            "on this page", "show source", "binder", "colab")
    keep = [ln for ln in lines
            if ln and not (len(ln) < 40 and ln.lower().strip("· ") in drop)]
    return "\n".join(keep).strip()


def post(title: str, content: str) -> dict:
    body = json.dumps({"title": title, "content": content, "campaign": COURSE}).encode()
    req = urllib.request.Request(API, data=body, headers={"content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode())


def discover() -> list[str]:
    """Every lecture page on the site, from the nav that each page carries."""
    raw = fetch(BASE.format(5))
    hrefs = re.findall(r'href="([^"]*lectures/[^"]+\.html)"', raw)
    paths = set()
    for h in hrefs:
        h = h.lstrip("./")
        if h.startswith("lectures/"):          # same-chapter link (ch5)
            h = "chapter5/" + h
        paths.add(h)
    def key(p: str):
        m = re.search(r"(\d+)-(\d+)", p)
        return (int(m.group(1)), int(m.group(2))) if m else (99, 99)
    return sorted(paths, key=key)


def main() -> int:
    lectures = discover()
    print(f"discovered {len(lectures)} lecture pages\n")
    # Quiz 3 is today and covers Ch 5, so import Ch 5 first: generation runs in
    # the background and the most exam-relevant questions should exist soonest.
    ch = lambda p: int(re.search(r"chapter(\d+)", p).group(1))
    lectures.sort(key=lambda p: (0 if ch(p) == 5 else 1, ORDER.index(ch(p)) if ch(p) in ORDER else 99))

    results, failed = [], []
    for path in lectures:
        url = SITE + path
        try:
            text = extract(fetch(url))
        except Exception as e:  # noqa: BLE001
            print(f"  FETCH FAIL {path}: {e}"); failed.append(path); continue
        if len(text) < 800:
            print(f"  SKIP {path}: only {len(text)} chars"); failed.append(path); continue
        n = ch(path)
        slug = re.sub(r"^\d+-\d+-", "", path.rsplit("/", 1)[-1].replace(".html", "")).replace("-", " ")
        sec = re.search(r"(\d+-\d+)", path)
        title = f"STAT 350 · {sec.group(1).replace('-', '.') if sec else n} {slug.title()}"
        try:
            res = post(title, text)
        except Exception as e:  # noqa: BLE001
            print(f"  IMPORT FAIL {path}: {e}"); failed.append(path); continue
        results.append({"chapter": n, "path": path, "material_id": res.get("material_id"),
                        "created": res.get("created"), "chars": len(text)})
        print(f"  ch{n:<2} {'new' if res.get('created') else 'dup'}  id={res.get('material_id'):<4} "
              f"{len(text):>6}ch  {title[:62]}")

    print(f"\nimported {len(results)}/{len(lectures)} lectures, {len(failed)} failed")
    json.dump(results, open("/tmp/stat350-import.json", "w"), indent=1)
    return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main())
