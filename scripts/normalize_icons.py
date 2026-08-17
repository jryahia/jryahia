#!/usr/bin/env python3
"""Normalize all icon SVGs to a unified 256x256 tile+content format.

- skillicons.dev icons: already 256x256 (dark tile + brand paths + defs) -> extract inner content, rename defs ids per-icon (id collisions).
- simple-icons CDN icons: 24x24 monochrome -> dark tile + green glyph.
- OpenAI knot (ChatGPT logo, Wikimedia): square -> dark tile + green glyph.
- Playwright (playwright.dev): 400x400 brand colors -> dark tile + paths at 256 scale.

Output: overwrites scripts/icons/*.svg, each a <svg viewBox="0 0 256 256">...</svg>.
"""
import os
import re
import sys
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/125.0 Safari/537.36"}

GREEN = "#39d353"
TILE = "#242938"

here = os.path.dirname(os.path.abspath(__file__))
icon_dir = os.path.join(here, "icons")


def fetch(url, out=None):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    if out:
        with open(out, "wb") as f:
            f.write(data)
    return data


def fetch_chatgpt_knot():
    """OpenAI's official mark = the ChatGPT knot (square)."""
    url = "https://upload.wikimedia.org/wikipedia/commons/0/04/ChatGPT_logo.svg"
    raw = fetch(url)
    return raw.decode("utf-8", "replace")


def extract_paths(raw):
    """Return list of (attrs, inner) fragments from all path/rect elements."""
    frags = []
    for tag in ("path", "rect", "circle", "polygon", "line"):
        for m in re.finditer(r"<%s\b([^>]*)/>" % tag, raw):
            frags.append((tag, m.group(1)))
    return frags


def clean_prefixes(body):
    """Drop attributes with unknown namespace prefixes (serif:, inkscape:,
    sodipodi:...) but keep xlink:href (declared on the root svg)."""
    body = re.sub(r'\s+(?:serif|inkscape|sodipodi|cc|dc|rdf|rdfs|ns)\w*:[a-zA-Z_-]+="[^"]*"', "", body)
    return body


def normalize_skillicons(raw, name):
    """Extract children of the LAST (innermost) <svg> in the file."""
    start = raw.rfind("<svg")
    end = raw.rfind("</svg>")
    if start == -1 or end == -1 or end <= start:
        return None
    open_tag_end = raw.find(">", start)
    if open_tag_end == -1 or open_tag_end > end:
        return None
    children = raw[open_tag_end + 1:end]
    ids = set(re.findall(r'id="([^"]+)"', children))
    for iid in ids:
        children = (children.replace(f'id="{iid}"', f'id="{name}_{iid}"')
                            .replace(f'url(#{iid})', f'url(#{name}_{iid})'))
    children = clean_prefixes(children)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 256 256">'
            f'{children}</svg>')


def normalize_simple(raw, name, recolor=GREEN):
    m = re.search(r'<svg[^>]*viewBox="([^"]+)"[^>]*>(.*?)</svg>', raw, re.S)
    if not m:
        return None
    vb = m.group(1)
    try:
        W, H = [float(x) for x in re.split(r"[ ,]", vb)][2:4]
    except Exception:
        W, H = 24.0, 24.0
    body = m.group(2)
    # strip any fill attrs so we can apply theme green
    body = re.sub(r'\sfill="[^"]*"', "", body)
    body = clean_prefixes(body)
    scale = 200.0 / max(W, H)
    cx, cy = 128.0, 128.0
    inner = (f'<g transform="translate({cx:.2f},{cy:.2f}) scale({scale:.4f}) '
             f'translate({-W / 2:.2f},{-H / 2:.2f})">')
    inner += body.replace("<path", f'<path fill="{recolor}"').replace("<polygon", f'<polygon fill="{recolor}"')
    inner += "</g>"
    return (f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 256 256">'
            f'<rect x="8" y="8" width="240" height="240" rx="56" fill="{TILE}"/>'
            f'{inner}</svg>')


def main():
    os.makedirs(icon_dir, exist_ok=True)
    results = []

    # 1. skillicons icons (already downloaded)
    for fname in sorted(os.listdir(icon_dir)):
        if not fname.endswith(".svg"):
            continue
        name = fname[:-4]
        raw = open(os.path.join(icon_dir, fname), encoding="utf-8").read()
        if len(raw) < 500:  # empty/bad download
            results.append((name, "SKIP empty"))
            continue
        out = normalize_skillicons(raw, name)
        if out is None:
            results.append((name, "SKIP not-256"))
            continue
        with open(os.path.join(icon_dir, fname), "w", encoding="utf-8") as f:
            f.write(out)
        results.append((name, "skillicons"))

    # 2. simple-icons green glyphs (overwrite the 5 downloaded)
    si = {"anthropic": "anthropic", "langchain": "langchain",
          "huggingface": "huggingface", "n8n": "n8n", "vercel": "vercel"}
    for name, slug in si.items():
        raw = fetch(f"https://cdn.simpleicons.org/{slug}/ffffff").decode("utf-8", "replace")
        out = normalize_simple(raw, name)
        if out is None:
            results.append((name, "SKIP simple-icons parse"))
            continue
        with open(os.path.join(icon_dir, f"{name}.svg"), "w", encoding="utf-8") as f:
            f.write(out)
        results.append((name, "simple-icons"))

    # 3. OpenAI knot (ChatGPT logo)
    out = normalize_simple(fetch_chatgpt_knot(), "openai")
    if out is None:
        results.append(("openai", "SKIP knot parse"))
    else:
        with open(os.path.join(icon_dir, "openai.svg"), "w", encoding="utf-8") as f:
            f.write(out)
        results.append(("openai", "knot"))

    # 4. Playwright (site logo, brand colors)
    raw = fetch("https://playwright.dev/img/playwright-logo.svg").decode("utf-8", "replace")
    m = re.search(r'<svg[^>]*viewBox="([^"]+)"[^>]*>(.*?)</svg>', raw, re.S)
    if m:
        W, H = [float(x) for x in re.split(r"[ ,]", m.group(1))][2:4]
        body = m.group(2)
        scale = 200.0 / max(W, H)
        inner = (f'<g transform="translate(128,128) scale({scale:.4f}) '
                 f'translate({-W / 2:.2f},{-H / 2:.2f})">{body}</g>')
        out = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">'
               f'<rect x="8" y="8" width="240" height="240" rx="56" fill="{TILE}"/>'
               f'{inner}</svg>')
        with open(os.path.join(icon_dir, "playwright.svg"), "w", encoding="utf-8") as f:
            f.write(out)
        results.append(("playwright", "site-logo"))
    else:
        results.append(("playwright", "SKIP parse"))

    ok = sum(1 for _, s in results if not s.startswith("SKIP"))
    print(f"normalized: {ok}/35")
    for name, status in sorted(results):
        print(f"  {name:16} {status}")
    sys.exit(0 if ok == 35 else 1)


if __name__ == "__main__":
    main()
