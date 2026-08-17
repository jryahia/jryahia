#!/usr/bin/env python3
"""Download skillicons.dev single-icon SVGs into scripts/icons/."""
import os
import sys
import urllib.request

ICONS = ["python", "javascript", "typescript", "react", "nextjs", "nodejs",
         "express", "fastapi", "mongodb", "postgres", "mysql", "redis", "docker",
         "git", "openai", "anthropic", "langchain", "huggingface", "n8n",
         "playwright", "selenium", "postman", "vercel", "linux", "github",
         "html", "css", "threejs", "vite", "tailwind", "figma", "webflow",
         "wordpress", "ps", "xd"]

here = os.path.dirname(os.path.abspath(__file__))
out_dir = os.path.join(here, "icons")
os.makedirs(out_dir, exist_ok=True)

ok, bad = 0, []
for name in ICONS:
    url = f"https://skillicons.dev/icons?i={name}"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/125.0 Safari/537.36"
        })
        with urllib.request.urlopen(req, timeout=20) as r:
            data = r.read()
        if len(data) < 500:
            bad.append((name, len(data)))
            continue
        with open(os.path.join(out_dir, f"{name}.svg"), "wb") as f:
            f.write(data)
        ok += 1
    except Exception as e:
        bad.append((name, str(e)))

print(f"downloaded: {ok}/{len(ICONS)}")
for name, err in bad:
    print(f"  BAD {name}: {err}")
sys.exit(1 if bad else 0)
