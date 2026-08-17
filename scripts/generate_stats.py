#!/usr/bin/env python3
"""Generate output/stats.svg for the jryahia profile README.

Pulls REAL data from the GitHub REST + GraphQL APIs and renders a
branded dark/orange SVG (H2S DNA: #0a0a0b bg, #f97316 accent).
Runs daily via .github/workflows/profile-stats.yml.
"""
import json
import os
import sys
import urllib.request

API = "https://api.github.com"
USER = "jryahia"
TOKEN = os.environ.get("STATS_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
PRIVATE_FALLBACK = int(os.environ.get("PRIVATE_REPOS", "0") or 0)

# H2S Computer DNA palette
OUTER_BG = "#0a0a0b"
TILE_BG = "#161b22"
BORDER = "#21262d"
ORANGE = "#f97316"
TEXT = "#e6edf3"
MUTED = "#8b949e"
FONT = "'Segoe UI', -apple-system, 'Helvetica Neue', Arial, sans-serif"


def req(path):
    r = urllib.request.Request(API + path)
    if TOKEN:
        r.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.load(resp)


def graphql(query):
    body = json.dumps({"query": query}).encode()
    r = urllib.request.Request(API + "/graphql", data=body, method="POST")
    r.add_header("Authorization", f"Bearer {TOKEN}")
    r.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.load(resp)


def main():
    user = req("/user") if TOKEN else req(f"/users/{USER}")
    repos = []
    page = 1
    while True:
        if TOKEN:
            # authenticated: real total incl. private repos
            endpoint = f"/user/repos?per_page=100&page={page}&affiliation=owner&visibility=all"
        else:
            endpoint = f"/users/{USER}/repos?per_page=100&page={page}&type=public"
        batch = req(endpoint)
        if not batch:
            break
        repos.extend(batch)
        page += 1

    stars = sum(r["stargazers_count"] for r in repos)
    forks = sum(r["forks_count"] for r in repos)

    # private repos the token can't list (fallback when running with GITHUB_TOKEN only)
    repo_total = len(repos) + (PRIVATE_FALLBACK if not TOKEN else 0)

    langs = {}
    for r in repos:
        if r.get("language"):
            langs[r["language"]] = langs.get(r["language"], 0) + 1
    total_lang = sum(langs.values()) or 1
    top_langs = sorted(langs.items(), key=lambda kv: -kv[1])[:5]

    commits = "n/a"
    if TOKEN:
        try:
            data = graphql(
                "{ user(login: \"%s\") { contributionsCollection {"
                " totalCommitContributions } } }" % USER
            )
            commits = data["data"]["user"]["contributionsCollection"][
                "totalCommitContributions"
            ]
        except Exception:
            commits = "n/a"

    followers = user["followers"]

    svg = render_svg(repo_total, commits, forks, followers, top_langs, total_lang)
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "output")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "stats.svg"), "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"OK stats.svg: repos={repo_total} (incl. private) commits={commits} "
          f"forks={forks} followers={followers} langs={dict(top_langs)}")


def render_svg(repos, commits, forks, followers, top_langs, total_lang):
    W, H = 900, 340
    tiles = [("REPOS", str(repos)), ("COMMITS / YEAR", str(commits)),
             ("FORKS", str(forks)), ("FOLLOWERS", str(followers))]
    tile_x = [30, 245, 460, 675]
    tw, th, ty = 195, 92, 64

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" fill="none">',
        f'<rect width="{W}" height="{H}" rx="16" fill="{OUTER_BG}"/>',
        f'<text x="30" y="46" fill="{ORANGE}" font-family="{FONT}" '
        f'font-size="22" font-weight="800" letter-spacing="4">GITHUB STATS</text>',
        f'<text x="870" y="46" fill="{MUTED}" font-family="{FONT}" font-size="13" '
        f'text-anchor="end">@{USER} · updated daily</text>',
    ]

    for (label, value), x in zip(tiles, tile_x):
        cx = x + tw / 2
        parts.append(
            f'<rect x="{x}" y="{ty}" width="{tw}" height="{th}" rx="12" '
            f'fill="{TILE_BG}" stroke="{BORDER}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{cx}" y="120" fill="{ORANGE}" font-family="{FONT}" '
            f'font-size="42" font-weight="800" text-anchor="middle">{value}</text>'
        )
        parts.append(
            f'<text x="{cx}" y="142" fill="{MUTED}" font-family="{FONT}" '
            f'font-size="13" font-weight="600" letter-spacing="2" '
            f'text-anchor="middle">{label}</text>'
        )

    parts.append(
        f'<text x="30" y="188" fill="{ORANGE}" font-family="{FONT}" '
        f'font-size="16" font-weight="800" letter-spacing="3">TOP LANGUAGES</text>'
    )

    if top_langs:
        bar_y = 214
        for i, (name, count) in enumerate(top_langs):
            pct = round(count / total_lang * 100)
            y = bar_y + i * 26
            parts.append(
                f'<text x="30" y="{y}" fill="{TEXT}" font-family="{FONT}" '
                f'font-size="14" font-weight="600">{name}</text>'
            )
            parts.append(
                f'<rect x="140" y="{y - 12}" width="560" height="10" rx="5" '
                f'fill="{TILE_BG}"/>'
            )
            fill_w = max(8, round(560 * pct / 100))
            parts.append(
                f'<rect x="140" y="{y - 12}" width="{fill_w}" height="10" rx="5" '
                f'fill="{ORANGE}"/>'
            )
            parts.append(
                f'<text x="720" y="{y}" fill="{MUTED}" font-family="{FONT}" '
                f'font-size="14" font-weight="600" text-anchor="end">'
                f'{pct}% · {count} repos</text>'
            )
    else:
        parts.append(
            f'<text x="30" y="214" fill="{MUTED}" font-family="{FONT}" '
            f'font-size="14">No public repositories.</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
