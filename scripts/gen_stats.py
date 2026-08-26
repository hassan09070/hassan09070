#!/usr/bin/env python3
"""Regenerate the profile's stat panels (htop-style SVGs) from the GitHub API.

Runs in the nightly workflow. Exits non-zero on API failure so the deploy step
is skipped and yesterday's panels keep serving — never publish broken cards.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from html import escape

USER = "hassan09070"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = sys.argv[1] if len(sys.argv) > 1 else "dist"

NEON = "#e8ff47"
GREEN = "#3fdc6e"
CYAN = "#9ee8ff"
DIM = "#8b949e"
BG = "#0d1117"
BORDER = "#1f2a1f"
MONO = "ui-monospace,Menlo,monospace"


def api(path):
    req = urllib.request.Request(f"https://api.github.com{path}")
    req.add_header("Accept", "application/vnd.github+json")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def chrome(width, height, title):
    """Terminal window chrome shared by both panels."""
    return (
        f'<rect width="{width}" height="{height}" rx="10" fill="{BG}" '
        f'stroke="{BORDER}" stroke-width="1"/>'
        f'<circle cx="22" cy="20" r="5" fill="#ff5f56"/>'
        f'<circle cx="40" cy="20" r="5" fill="#ffbd2e"/>'
        f'<circle cx="58" cy="20" r="5" fill="#27c93f"/>'
        f'<text x="{width/2}" y="24" text-anchor="middle" font-family="{MONO}" '
        f'font-size="12" fill="{DIM}">{escape(title)}</text>'
        f'<line x1="12" y1="34" x2="{width-12}" y2="34" stroke="#21262d"/>'
    )


def meter(x, y, w, frac, label, value, color=NEON):
    """One htop-style row: label, segmented bar, value."""
    frac = max(0.0, min(1.0, frac))
    segs = 22
    lit = round(segs * frac)
    cells = []
    seg_w = w / segs
    for i in range(segs):
        fill = color if i < lit else "#21262d"
        op = "1" if i < lit else "0.9"
        cells.append(
            f'<rect x="{x + 110 + i*seg_w:.1f}" y="{y-11}" width="{seg_w-2.2:.1f}" '
            f'height="13" rx="1.5" fill="{fill}" opacity="{op}"/>'
        )
    return (
        f'<text x="{x}" y="{y}" font-family="{MONO}" font-size="13" fill="{CYAN}">{escape(label)}</text>'
        f'{"".join(cells)}'
        f'<text x="{x + 110 + w + 10}" y="{y}" font-family="{MONO}" font-size="13" '
        f'fill="{NEON}" font-weight="bold">{escape(str(value))}</text>'
    )


def main():
    user = api(f"/users/{USER}")
    repos = api(f"/users/{USER}/repos?per_page=100&type=owner")
    own = [r for r in repos if not r["fork"]]
    stars = sum(r["stargazers_count"] for r in own)
    merged = api(f"/search/issues?q=type:pr+author:{USER}+is:merged")["total_count"]
    followers = user["followers"]
    created = datetime.fromisoformat(user["created_at"].replace("Z", "+00:00"))
    years = (datetime.now(timezone.utc) - created).days / 365.25

    # NeetCode progress, read live from that repo's README (self-updating badge).
    # Fail-soft: if the format ever changes, drop the row rather than kill the job.
    neetcode = None
    try:
        import re
        raw = urllib.request.urlopen(
            f"https://raw.githubusercontent.com/{USER}/neetcode250/main/README.md",
            timeout=30).read().decode()
        m = re.search(r"(\d+)\s*/\s*250", raw)
        if m:
            neetcode = int(m.group(1))
    except Exception as e:
        print(f"warn: neetcode fetch failed: {e}", file=sys.stderr)

    langs = {}
    for r in own:
        for lang, n in api(f"/repos/{USER}/{r['name']}/languages").items():
            langs[lang] = langs.get(lang, 0) + n
    total = sum(langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: -kv[1])[:6]

    os.makedirs(OUT, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # ---- panel 1: stats ----
    W, H = 480, 230
    rows = [
        ("repos", len(own), len(own) / 15),
        ("merged PRs", merged, merged / 200),
        ("papers", 2, 2 / 5),  # SemEval-2026, CLEF 2026 — bump on the next one
    ]
    if neetcode is not None:
        rows.append(("neetcode", f"{neetcode}/250", neetcode / 250))
    body = [chrome(W, H, f"hassan@habib: ~/stats — htop")]
    y = 66
    for label, val, frac in rows:
        body.append(meter(24, y, 250, frac, label, val))
        y += 32
    body.append(
        f'<text x="24" y="{y+4}" font-family="{MONO}" font-size="13" fill="{GREEN}">'
        f'uptime</text>'
        f'<text x="134" y="{y+4}" font-family="{MONO}" font-size="13" fill="{DIM}">'
        f'{years:.1f} years on GitHub · refreshed {stamp}</text>'
    )
    body.append(
        f'<rect x="{W-26}" y="{H-24}" width="9" height="14" fill="{NEON}">'
        f'<animate attributeName="opacity" values="1;0;1" dur="1.2s" repeatCount="indefinite"/></rect>'
    )
    with open(f"{OUT}/stats.svg", "w") as f:
        f.write(f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
                f'xmlns="http://www.w3.org/2000/svg">{"".join(body)}</svg>')

    # ---- panel 2: languages ----
    W2, H2 = 480, 230
    body = [chrome(W2, H2, "hassan@habib: ~/langs — by bytes, no flattery")]
    y = 66
    for lang, n in top:
        frac = n / total
        body.append(meter(24, y, 250, frac, lang[:12], f"{frac*100:.1f}%", color=GREEN))
        y += 27
    with open(f"{OUT}/langs.svg", "w") as f:
        f.write(f'<svg width="{W2}" height="{H2}" viewBox="0 0 {W2} {H2}" '
                f'xmlns="http://www.w3.org/2000/svg">{"".join(body)}</svg>')

    print(f"stats: {len(own)} repos, {stars} stars, {merged} merged PRs, {followers} followers")
    print("langs:", ", ".join(f"{l} {v/total*100:.1f}%" for l, v in top))


if __name__ == "__main__":
    main()
