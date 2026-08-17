#!/usr/bin/env python3
"""Generate output/stats.svg for the jryahia profile README.

Pulls REAL data from the GitHub REST + GraphQL APIs and renders a
branded dark/green SVG (GitHub contribution palette on #0a0a0b).
Runs daily via .github/workflows/profile-stats.yml.
"""
import json
import os
import re
import sys
import urllib.request

API = "https://api.github.com"
USER = "jryahia"
TOKEN = os.environ.get("STATS_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
PRIVATE_FALLBACK = int(os.environ.get("PRIVATE_REPOS", "0") or 0)

# H2S Computer DNA palette → now all GitHub green
OUTER_BG = "#0a0a0b"
TILE_BG = "#161b22"
BORDER = "#21262d"
ORANGE = "#39d353"
GREEN = "#39d353"
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
    streaks = {"current": "n/a", "longest": "n/a", "year": "n/a"}
    if TOKEN:
        try:
            data = graphql(
                '{ user(login: "%s") { contributionsCollection {'
                " totalCommitContributions contributionCalendar { totalContributions"
                " weeks { contributionDays { date contributionCount } } } } } }" % USER
            )
            cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
            commits = data["data"]["user"]["contributionsCollection"][
                "totalCommitContributions"
            ]
            streaks = compute_streaks(cal["weeks"])
            streaks["year"] = cal["totalContributions"]
        except Exception as e:
            commits = "n/a"
            print(f"WARN streak/commit data: {e}")

    followers = user["followers"]

    svg = render_svg(repo_total, commits, forks, followers, top_langs, total_lang)
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "output")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "stats.svg"), "w", encoding="utf-8") as f:
        f.write(svg)

    streak_svg = render_streak_svg(streaks)
    with open(os.path.join(out_dir, "streak.svg"), "w", encoding="utf-8") as f:
        f.write(streak_svg)

    icons = load_icons()
    if len(icons) < 30:
        print(f"WARN only {len(icons)}/35 icons available, skipping skills.svg")
    else:
        skills_svg = render_skills_svg(icons)
        with open(os.path.join(out_dir, "skills.svg"), "w", encoding="utf-8") as f:
            f.write(skills_svg)

    print(f"OK stats.svg: repos={repo_total} (incl. private) commits={commits} "
          f"forks={forks} followers={followers} langs={dict(top_langs)} "
          f"streak={streaks}")


def compute_streaks(weeks):
    """Current (today or yesterday-anchored), longest and yearly totals from the
    contribution calendar — same semantics as GitHub's own streak."""
    days = []
    for w in weeks:
        for d in w["contributionDays"]:
            days.append((d["date"], d["contributionCount"]))
    if not days:
        return {"current": 0, "longest": 0, "year": 0}

    counts = [c for _, c in days]
    year = sum(counts)

    # longest run of consecutive contributing days
    longest = cur = 0
    for c in counts:
        cur = cur + 1 if c > 0 else 0
        longest = max(longest, cur)

    # current streak: count back from today; if today is 0, start from yesterday
    today = days[-1][1]
    i = len(days) - 1
    if today == 0:
        i -= 1
    current = 0
    while i >= 0 and days[i][1] > 0:
        current += 1
        i -= 1
    return {"current": current, "longest": longest, "year": year}


def load_icons():
    """Load the 35 normalized 256x256 icon tiles from scripts/icons/."""
    icon_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
    icons = {}
    for fname in os.listdir(icon_dir):
        if not fname.endswith(".svg"):
            continue
        name = fname[:-4]
        raw = open(os.path.join(icon_dir, fname), encoding="utf-8").read()
        m = re.search(r'<svg[^>]*viewBox="0 0 256 256"[^>]*>(.*?)</svg>', raw, re.S)
        if m:
            icons[name] = m.group(1)
    return icons


def render_skills_svg(icons):
    """Animated tech-stack card: 3 grouped rows of skill tiles.

    Titles slide in and land CENTERED with an underline growing out from the
    middle; every icon pops in one by one (spring), then all icons float and
    sway forever at varied speeds/phases; soft glow dots drift behind. Pure
    CSS keyframes inside the SVG, so it animates via <img> in the README.
    """
    GROUPS = [
        ("FULL-STACK",
         ["python", "javascript", "typescript", "react", "nextjs", "nodejs",
          "express", "fastapi", "mongodb", "postgres", "mysql", "redis",
          "docker", "git"]),
        ("PROMPT ENGINEERING &amp; AI AUTOMATION",
         ["openai", "anthropic", "langchain", "huggingface", "n8n",
          "playwright", "selenium", "postman", "vercel", "linux", "github"]),
        ("WEB DESIGN",
         ["html", "css", "threejs", "vite", "tailwind", "figma", "webflow",
          "wordpress", "ps", "xd"]),
    ]
    GREEN = "#39d353"
    ICON, GAP = 48, 12
    TITLE_H, PAD = 40, 24
    pitch = ICON + GAP
    max_row = max(len(g[1]) for g in GROUPS)
    W = max_row * pitch - GAP + 2 * PAD
    H = len(GROUPS) * (TITLE_H + ICON) + 2 * PAD
    scale = ICON / 256.0

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" fill="none">',
        "<style>",
        "@keyframes pop{0%{opacity:0;transform:scale(.3)}"
        "60%{transform:scale(1.18)}100%{opacity:1;transform:scale(1)}}",
        ".pop{animation:pop .8s cubic-bezier(.2,.8,.3,1.35) forwards;"
        "opacity:0;transform-box:fill-box;transform-origin:center}",
        "@keyframes floaty{0%,100%{transform:translateY(0) rotate(-3deg)}"
        "50%{transform:translateY(-9px) rotate(3deg)}}",
        ".fl{animation:floaty 2.6s ease-in-out infinite;"
        "transform-box:fill-box;transform-origin:center}",
        "@keyframes titleIn{from{opacity:0;transform:translateX(-34px)}"
        "to{opacity:1;transform:translateX(0)}}",
        ".t{animation:titleIn .9s cubic-bezier(.2,.8,.3,1) forwards;opacity:0}",
        "@keyframes grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}",
        ".ul{animation:grow .7s cubic-bezier(.2,.8,.3,1.2) forwards;"
        "transform-box:fill-box;transform-origin:center}",
        "@keyframes drift{0%,100%{transform:translateY(0);opacity:.18}"
        "50%{transform:translateY(-18px);opacity:.55}}",
        ".dot{animation:drift 5s ease-in-out infinite}",
        "</style>",
        f'<rect width="{W}" height="{H}" rx="16" fill="{OUTER_BG}"/>',
    ]
    dots = [(60, 40), (W - 70, 46), (W // 2, 14), (70, H - 26), (W - 80, H - 30)]
    for di, (dx, dy) in enumerate(dots):
        parts.append(
            f'<circle cx="{dx}" cy="{dy}" r="3" fill="{GREEN}" class="dot" '
            f'style="animation-delay:-{di * 1.1}s;'
            f'animation-duration:{4.4 + di * 0.7:.1f}s"/>'
        )
    idx = 0
    for gi, (title, names) in enumerate(GROUPS):
        y = PAD + gi * (TITLE_H + ICON)
        cx = W / 2
        parts.append(
            f'<text x="{cx:.1f}" y="{y + 15}" fill="{GREEN}" font-family="{FONT}" '
            f'font-size="15" font-weight="800" letter-spacing="4" '
            f'text-anchor="middle" class="t" '
            f'style="animation-delay:{gi * 0.3}s">{title}</text>'
        )
        parts.append(
            f'<rect x="{cx - 46:.1f}" y="{y + 22}" width="92" height="2" rx="1" '
            f'fill="{GREEN}" class="ul" '
            f'style="animation-delay:{gi * 0.3 + 0.35}s"/>'
        )
        row_w = len(names) * pitch - GAP
        x0 = (W - row_w) / 2
        for ni, name in enumerate(names):
            body = icons.get(name)
            if not body:
                continue
            x = x0 + ni * pitch
            pop_delay = idx * 0.055
            float_dur = 2.2 + (idx % 5) * 0.3
            float_delay = -idx * 0.24
            parts.append(
                f'<g transform="translate({x:.1f},{y + TITLE_H}) scale({scale:.4f})">'
                f'<g class="pop" style="animation-delay:{pop_delay:.2f}s">'
                f'<g class="fl" style="animation-delay:{float_delay:.2f}s;'
                f'animation-duration:{float_dur:.1f}s">{body}</g></g></g>'
            )
            idx += 1
    parts.append("</svg>")
    return "\n".join(parts)


def render_streak_svg(streaks):
    """GitHub-green contribution streak card — animated current-streak counter."""
    W, H = 560, 190
    GREEN = "#39d353"
    tiles = [("CURRENT STREAK", f"{streaks['current']}", "days"),
             ("TOTAL CONTRIBUTIONS", f"{streaks['year']}", "this year"),
             ("LONGEST STREAK", f"{streaks['longest']}", "days")]
    tx = [30, 210, 390]
    tw, th, ty = 140, 92, 66

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" fill="none">',
        "<style>"
        "@keyframes pop { 0% { opacity: 0; transform: scale(0.6); } "
        "60% { transform: scale(1.15); } 100% { opacity: 1; transform: scale(1); } }"
        "@keyframes fadein { from { opacity: 0; } to { opacity: 1; } }"
        ".pop { animation: pop 0.9s cubic-bezier(.2,.8,.3,1.2) forwards; }"
        ".fade { animation: fadein 0.8s ease forwards; opacity: 0; }"
        "</style>",
        f'<rect width="{W}" height="{H}" rx="16" fill="{OUTER_BG}"/>',
        f'<text x="30" y="44" fill="{GREEN}" font-family="{FONT}" '
        f'font-size="20" font-weight="800" letter-spacing="4">STREAK</text>',
        f'<text x="530" y="44" fill="{MUTED}" font-family="{FONT}" font-size="13" '
        f'text-anchor="end">@{USER} · updated daily</text>',
    ]

    for i, ((label, value, unit), x) in enumerate(zip(tiles, tx)):
        cx = x + tw / 2
        parts.append(
            f'<rect x="{x}" y="{ty}" width="{tw}" height="{th}" rx="12" '
            f'fill="{TILE_BG}" stroke="{BORDER}" stroke-width="1"/>'
        )
        anim = 'class="pop"' if i == 0 else 'class="fade"'
        color = GREEN if i == 0 else TEXT
        parts.append(
            f'<text x="{cx}" y="118" fill="{color}" font-family="{FONT}" '
            f'font-size="40" font-weight="800" text-anchor="middle" {anim}>'
            f'{value}</text>'
        )
        parts.append(
            f'<text x="{cx}" y="142" fill="{MUTED}" font-family="{FONT}" '
            f'font-size="12" font-weight="600" letter-spacing="2" '
            f'text-anchor="middle">{label}</text>'
        )
        parts.append(
            f'<text x="{cx}" y="156" fill="{GREEN}" font-family="{FONT}" '
            f'font-size="11" font-weight="600" letter-spacing="1" '
            f'text-anchor="middle">{unit}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


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
