#!/usr/bin/env python3
"""
GitHub Stats SVG Generator
Fetches real stats from GitHub API and produces a self-contained SVG card.
Run via GitHub Actions — output committed back to repo as stats/github-stats.svg
"""

import os
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone

# ── Config ────────────────────────────────────────────────────────────────────
USERNAME = os.environ.get("GITHUB_USERNAME", "sudin-tech")
TOKEN    = os.environ.get("GH_TOKEN", "")
OUT_FILE = os.environ.get("OUTPUT_FILE", "stats/github-stats.svg")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "stats-generator/1.0",
}

# ── GitHub API helpers ────────────────────────────────────────────────────────
def gh_get(path: str) -> dict | list:
    url = f"https://api.github.com{path}"
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def gh_graphql(query: str, variables: dict = {}) -> dict:
    url  = "https://api.github.com/graphql"
    body = json.dumps({"query": query, "variables": variables}).encode()
    req  = urllib.request.Request(url, data=body, headers={**HEADERS, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


# ── Fetch data ────────────────────────────────────────────────────────────────
def fetch_stats() -> dict:
    # Basic profile
    user = gh_get(f"/users/{USERNAME}")

    # All repos (paginate)
    repos, page = [], 1
    while True:
        page_data = gh_get(f"/users/{USERNAME}/repos?per_page=100&page={page}&type=owner")
        if not page_data:
            break
        repos.extend(page_data)
        if len(page_data) < 100:
            break
        page += 1

    total_stars = sum(r.get("stargazers_count", 0) for r in repos)
    total_forks = sum(r.get("forks_count", 0)       for r in repos)
    languages   = {}
    for r in repos:
        lang = r.get("language")
        if lang:
            languages[lang] = languages.get(lang, 0) + 1
    top_lang = max(languages, key=languages.get) if languages else "N/A"

    # Contributions via GraphQL (current year)
    year  = datetime.now(timezone.utc).year
    gql   = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          totalCommitContributions
          totalPullRequestContributions
          totalIssueContributions
          totalRepositoryContributions
        }
      }
    }
    """
    gql_data = gh_graphql(gql, {
        "login": USERNAME,
        "from":  f"{year}-01-01T00:00:00Z",
        "to":    f"{year}-12-31T23:59:59Z",
    })
    col = gql_data["data"]["user"]["contributionsCollection"]

    return {
        "name":        user.get("name") or USERNAME,
        "followers":   user.get("followers", 0),
        "following":   user.get("following", 0),
        "public_repos":user.get("public_repos", 0),
        "stars":       total_stars,
        "forks":       total_forks,
        "top_lang":    top_lang,
        "commits":     col["totalCommitContributions"],
        "prs":         col["totalPullRequestContributions"],
        "issues":      col["totalIssueContributions"],
        "repos_contributed": col["totalRepositoryContributions"],
        "updated_at":  datetime.now(timezone.utc).strftime("%b %d, %Y · %H:%M UTC"),
        "year":        year,
    }


# ── SVG Template ──────────────────────────────────────────────────────────────
def fmt(n: int) -> str:
    """Format large numbers: 1200 → 1.2k"""
    if n >= 1000:
        return f"{n/1000:.1f}k"
    return str(n)


def build_svg(s: dict) -> str:
    W, H = 860, 230

    stats_items = [
        ("COMMITS",   fmt(s["commits"]),       "this year"),
        ("STARS",     fmt(s["stars"]),          "earned"),
        ("PULL REQ",  fmt(s["prs"]),            "opened"),
        ("REPOS",     fmt(s["public_repos"]),   "public"),
        ("FORKS",     fmt(s["forks"]),          "total"),
        ("FOLLOWERS", fmt(s["followers"]),      ""),
    ]

    # Build stat cells — 6 columns across
    COLS    = 6
    cell_w  = (W - 80) / COLS
    cells   = ""
    for i, (label, value, sub) in enumerate(stats_items):
        x = 40 + cell_w * i + cell_w / 2
        y_val  = 118
        y_lbl  = 143
        y_sub  = 160

        cells += f"""
  <!-- {label} -->
  <text x="{x:.1f}" y="{y_val}" text-anchor="middle"
        font-family="'JetBrains Mono', 'Fira Code', monospace"
        font-size="26" font-weight="700" fill="#E6EDF3"
        letter-spacing="-0.5">{value}</text>
  <text x="{x:.1f}" y="{y_lbl}" text-anchor="middle"
        font-family="'JetBrains Mono', 'Fira Code', monospace"
        font-size="9" font-weight="600" fill="#8B949E"
        letter-spacing="2">{label}</text>"""
        if sub:
            cells += f"""
  <text x="{x:.1f}" y="{y_sub}" text-anchor="middle"
        font-family="'JetBrains Mono', 'Fira Code', monospace"
        font-size="8" fill="#484F58">{sub}</text>"""

    # Dividers between cells
    dividers = ""
    for i in range(1, COLS):
        dx = 40 + cell_w * i
        dividers += f'<line x1="{dx:.1f}" y1="100" x2="{dx:.1f}" y2="170" stroke="#21262D" stroke-width="1"/>'

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}"
     viewBox="0 0 {W} {H}" role="img"
     aria-label="GitHub stats for {s['name']}">

  <title>GitHub Stats — {s['name']}</title>

  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%"   stop-color="#0D1117"/>
      <stop offset="100%" stop-color="#161B22"/>
    </linearGradient>
    <linearGradient id="accent" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%"   stop-color="#58A6FF"/>
      <stop offset="100%" stop-color="#3FB950"/>
    </linearGradient>
    <filter id="glow">
      <feGaussianBlur stdDeviation="3" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <clipPath id="round">
      <rect width="{W}" height="{H}" rx="12"/>
    </clipPath>
  </defs>

  <!-- Background -->
  <rect width="{W}" height="{H}" fill="url(#bg)" clip-path="url(#round)" rx="12"/>

  <!-- Top accent bar -->
  <rect x="0" y="0" width="{W}" height="3" fill="url(#accent)" rx="1.5"/>

  <!-- Subtle grid texture -->
  <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
    <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#21262D" stroke-width="0.4"/>
  </pattern>
  <rect width="{W}" height="{H}" fill="url(#grid)" opacity="0.35" clip-path="url(#round)"/>

  <!-- Header: name + tag -->
  <text x="40" y="46"
        font-family="'JetBrains Mono', 'Fira Code', monospace"
        font-size="11" font-weight="600" fill="#58A6FF"
        letter-spacing="3">GITHUB STATS</text>

  <text x="40" y="74"
        font-family="'JetBrains Mono', 'Fira Code', monospace"
        font-size="20" font-weight="700" fill="#E6EDF3"
        letter-spacing="-0.5">{s["name"]}</text>

  <!-- Top lang badge -->
  <rect x="{W - 160}" y="38" width="120" height="26" rx="5"
        fill="#21262D" stroke="#30363D" stroke-width="1"/>
  <text x="{W - 100}" y="55.5" text-anchor="middle"
        font-family="'JetBrains Mono', 'Fira Code', monospace"
        font-size="9" fill="#8B949E" letter-spacing="1.5">TOP LANG</text>
  <text x="{W - 40}" y="55.5" text-anchor="end"
        font-family="'JetBrains Mono', 'Fira Code', monospace"
        font-size="10" font-weight="700" fill="#3FB950" letter-spacing="0.5">{s["top_lang"]}</text>

  <!-- Separator -->
  <line x1="40" y1="92" x2="{W - 40}" y2="92" stroke="#21262D" stroke-width="1"/>

  <!-- Stat cells -->
  {cells}

  <!-- Vertical dividers -->
  {dividers}

  <!-- Bottom separator -->
  <line x1="40" y1="178" x2="{W - 40}" y2="178" stroke="#21262D" stroke-width="1"/>

  <!-- Footer -->
  <text x="40" y="205"
        font-family="'JetBrains Mono', 'Fira Code', monospace"
        font-size="9" fill="#484F58">↻ Updated {s["updated_at"]}</text>

  <text x="{W - 40}" y="205" text-anchor="end"
        font-family="'JetBrains Mono', 'Fira Code', monospace"
        font-size="9" fill="#484F58">{s["year"]} contributions</text>

</svg>"""

    return svg


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"[stats] Fetching data for @{USERNAME} …")
    try:
        stats = fetch_stats()
    except urllib.error.HTTPError as e:
        print(f"[stats] GitHub API error {e.code}: {e.reason}")
        raise SystemExit(1)

    svg = build_svg(stats)

    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(svg)

    print(f"[stats] Written → {OUT_FILE}")
    print(f"[stats] Commits: {stats['commits']} | Stars: {stats['stars']} | PRs: {stats['prs']}")


if __name__ == "__main__":
    main()