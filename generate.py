"""Render profile.svg — a neofetch-style panel with live GitHub stats.

Always dark (Solarized Dark, matching my terminal): GitHub renders README
images identically in both site themes, so the panel is a fixed terminal card.

The aquarium is deterministic in the day number — each nightly refresh
advances the fish a few columns, re-rolls the bubbles, and sways the kelp.

Runs nightly via GitHub Actions (GITHUB_TOKEN env) and locally with
`GITHUB_TOKEN=$(gh auth token) python3 generate.py`.
"""
import json
import logging
import math
import os
import random
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

LOGIN = "DJuboor"
BORN = date(1992, 12, 5)
EPOCH = date(2026, 1, 1)  # aquarium frame counter origin
FONT = 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace'
CHAR_W, LINE_H, FONT_SIZE = 7.85, 19, 13
PAD, ART_INFO_GAP = 28, 34
INFO_WIDTH = 62  # characters per info line, including the ". " prefix
ART_W, ART_H = 42, 29

# Solarized Dark, straight from the terminal profile.
THEME = {
    "bg": "#002b36", "border": "#073642",
    "title": "#93a1a1", "key": "#cb4b16", "val": "#268bd2", "dots": "#586e75",
    "good": "#859900", "bad": "#dc322f",
    "kelp": "#859900", "bub": "#2aa198", "water": "#2aa198",
    "fish1": "#b58900", "fish2": "#d33682", "fish3": "#6c71c4",
}

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

Seg = tuple[str, str]  # (css class, text)


def gh_request(url: str, payload: dict | None = None) -> tuple[int, dict | list]:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode() if payload else None,
        headers={
            "Authorization": f"bearer {os.environ['GITHUB_TOKEN']}",
            "Accept": "application/vnd.github+json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, {}


def github_stats() -> dict:
    """Repo/star/follower/commit counts via GraphQL (private repos included
    when the token can see them)."""
    query = """
    query($login: String!) {
      user(login: $login) {
        followers { totalCount }
        repositories(first: 100, ownerAffiliations: OWNER) {
          totalCount
          nodes { name stargazerCount }
        }
        repositoriesContributedTo(contributionTypes: [COMMIT]) { totalCount }
        contributionsCollection { totalCommitContributions }
      }
    }"""
    _, data = gh_request("https://api.github.com/graphql", {"query": query, "variables": {"login": LOGIN}})
    user = data["data"]["user"]
    return {
        "repos": user["repositories"]["totalCount"],
        "repo_names": [n["name"] for n in user["repositories"]["nodes"]],
        "stars": sum(n["stargazerCount"] for n in user["repositories"]["nodes"]),
        "followers": user["followers"]["totalCount"],
        "contributed": user["repositoriesContributedTo"]["totalCount"],
        "commits": user["contributionsCollection"]["totalCommitContributions"],
    }


def github_loc(repo_names: list[str]) -> tuple[int, int]:
    """Sum my line additions/deletions across repos (REST contributor stats).

    First hit per repo often returns 202 while GitHub computes the stats;
    retry briefly, skip on repeated 202 or any error — close is fine here.
    """
    adds = dels = 0
    for name in repo_names:
        url = f"https://api.github.com/repos/{LOGIN}/{name}/stats/contributors"
        for _ in range(3):
            status, data = gh_request(url)
            if status != 202:
                break
            time.sleep(2)
        if status != 200 or not isinstance(data, list):
            continue
        for contributor in data:
            if (contributor.get("author") or {}).get("login") == LOGIN:
                adds += sum(w["a"] for w in contributor["weeks"])
                dels += sum(w["d"] for w in contributor["weeks"])
    return adds, dels


def human(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if n >= 10_000:
        return f"{n / 1000:.0f}K"
    return f"{n:,}"


def aquarium(frame: int) -> list[list[Seg]]:
    """Day-indexed aquarium: swimming fish, rising bubbles, swaying kelp."""
    grid = [[(" ", "art")] * ART_W for _ in range(ART_H)]

    def put(x: int, y: int, c: str, cls: str, over: bool = False) -> None:
        if 0 <= x < ART_W and 0 <= y < ART_H and (over or grid[y][x][0] == " "):
            grid[y][x] = (c, cls)

    surface = "~^~~·~~^~~~·~^~"
    for x in range(ART_W):
        put(x, 0, surface[(x + frame) % len(surface)], "water")
    bed = "_.~,_.·,~_.,~·_.~,._~,.·~_.,~._·~,._~.,_.~"
    for x in range(ART_W):
        put(x, ART_H - 1, bed[x % len(bed)], "art")

    for x0, top, ph in [(7, 17, 0.0), (19, 13, 2.1), (32, 19, 4.2)]:
        sway = ph + frame * 0.35
        for y in range(top, ART_H - 1):
            x = x0 + round(1.4 * math.sin((ART_H - y) / 3.5 + sway))
            put(x, y, "|", "kelp")
            if y > top:
                if y % 2 == 0:
                    put(x - 1, y, "\\", "kelp")
                    if y % 4 == 0:
                        put(x - 2, y, ")", "kelp")
                else:
                    put(x + 1, y, "/", "kelp")
                    if y % 4 == 1:
                        put(x + 2, y, "(", "kelp")

    # (sprite, row, speed cols/day, phase, class); negative speed swims left
    fish = [
        ("><(((°>", 4, 3, 5, "fish1"),
        ("<°)))><", 9, -2, 21, "fish2"),
        ("><>", 14, 4, 12, "fish3"),
        ("<><", 6, -3, 30, "fish1"),
        ("><}}°>", 20, 2, 0, "fish2"),
    ]
    for sprite, row, speed, phase, cls in fish:
        span = ART_W + len(sprite) + 10  # off-screen gap before wrapping
        pos = (phase + speed * frame) % span
        x0 = pos - len(sprite) if speed > 0 else ART_W - pos
        for i, c in enumerate(sprite):
            put(x0 + i, row, c, cls, over=True)  # fish swim in front of kelp

    rng = random.Random(frame)
    for _ in range(24):
        y = 1 + int(abs(rng.gauss(0, ART_H * 0.3)))
        put(rng.randrange(1, ART_W - 1), y, rng.choice("°°oo.O"), "bub")

    lines: list[list[Seg]] = []
    for row in grid:
        segs: list[Seg] = []
        for c, cls in row:
            if segs and (segs[-1][0] == cls or c == " "):
                segs[-1] = (segs[-1][0], segs[-1][1] + c)
            else:
                segs.append((cls, c))
        lines.append(segs)
    return lines


def kv(key: str, value: str, width: int = INFO_WIDTH - 2) -> list[Seg]:
    """`. Key: ..... value` — dotted leaders pad the value to the right edge."""
    dots = "." * max(1, width - len(key) - len(value) - 3)
    return [("dots", ". "), ("key", f"{key}:"), ("dots", f" {dots} "), ("val", value)]


def pair(k1: str, v1: str, k2: str, v2: str) -> list[Seg]:
    """Two stats on one line, original-style: `. K1: .. v1 | K2: .. v2`."""
    left = kv(k1, v1, width=35)
    right = kv(k2, v2, width=INFO_WIDTH - 2 - 35 - 3)[1:]  # no ". " prefix
    return left + [("dots", " | ")] + right


def loc_line(adds: int, dels: int) -> list[Seg]:
    net, a, d = f"{adds - dels:,}", f"+{human(adds)}", f"-{human(dels)}"
    tail_len = len(net) + len(a) + len(d) + 8  # "net ( +a, -d )"
    dots = "." * max(1, INFO_WIDTH - 2 - len("GitHub LOC:") - tail_len - 2)
    return [
        ("dots", ". "), ("key", "GitHub LOC:"), ("dots", f" {dots} "), ("val", f"{net} "),
        ("dots", "( "), ("good", a), ("dots", ", "), ("bad", d), ("dots", " )"),
    ]


def rule(title: str, section: bool = False) -> list[Seg]:
    prefix = "- " if section else ""
    bar = "─" * (INFO_WIDTH - len(prefix) - len(title) - 4)
    return [("dots", prefix), ("title", title), ("dots", f" {bar}-·-")]


def build_lines(stats: dict, adds: int, dels: int) -> list[list[Seg]]:
    today = date.today()
    years = today.year - BORN.year - ((today.month, today.day) < (BORN.month, BORN.day))
    months = (today.month - BORN.month - (today.day < BORN.day)) % 12
    anchor_month = today.month - (today.day < BORN.day)
    anchor = date(today.year - (anchor_month < 1), (anchor_month - 1) % 12 + 1, BORN.day)
    days = (today - anchor).days
    year_pct = today.timetuple().tm_yday * 100 // 365
    bar = ("█" * (year_pct // 8)).ljust(12, "░")
    return [
        rule("davidj@imagineering"),
        [],
        kv("OS", "macOS / Ubuntu (aarch64)"),
        kv("Uptime", f"{years} years, {months} months, {days} days"),
        kv("Host", "Princ. MLE @ Imagineering"),
        kv("Kernel", "ChemE (Drexel) → Applied ML"),
        kv("IDE", "ST4, Vim"),
        [],
        kv("Languages.AI", "Agents, Harnesses, RAG"),
        kv("Languages.Programming", "Python, TypeScript, Bash, C++"),
        kv("Languages.Human", "English, Spanish"),
        [],
        kv("Hobbies.Software", "Automation, DocVQA, Deep Learning"),
        kv("Hobbies.Hardware", "DGX Spark, Homelab, Embedded"),
        kv("Hobbies.Others", "PingPong, Scuba, Jazz"),
        [],
        rule("Contact", section=True),
        kv("Portfolio", "davidj.today"),
        kv("LinkedIn", "in/davidnjuboor"),
        kv("Discord", "Mr.Bubbles"),
        [],
        rule("GitHub Stats", section=True),
        pair("Repos", f"{stats['repos']} {{Contributed: {stats['contributed']}}}", "Stars", str(stats["stars"])),
        pair("Commits", f"{stats['commits']:,}", "Followers", str(stats["followers"])),
        loc_line(adds, dels),
        [],
        kv("Status", f"LOADING.. [{bar}] {year_pct}%"),
    ]


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(art: list[list[Seg]], lines: list[list[Seg]]) -> str:
    info_x = PAD + ART_W * CHAR_W + ART_INFO_GAP
    width = round(info_x + INFO_WIDTH * CHAR_W + PAD)
    rows = max(len(art), len(lines))
    height = round(rows * LINE_H + 2 * PAD)
    art_y0 = PAD + ((rows - len(art)) // 2) * LINE_H

    css = "\n".join(f"    .{name} {{ fill: {color}; }}" for name, color in THEME.items() if name not in ("bg", "border"))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="davidj profile">',
        f"<style>\n    text {{ font-family: {FONT}; font-size: {FONT_SIZE}px; "
        f"font-weight: 500; white-space: pre; }}\n"
        f"    .title {{ font-weight: 700; }}\n{css}\n  </style>",
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="8" '
        f'fill="{THEME["bg"]}" stroke="{THEME["border"]}"/>',
    ]

    def emit(segs: list[Seg], x: float, y: int) -> None:
        for cls, s in segs:
            if s.strip():
                # textLength pins glyph advance so layout matches across
                # platform monospace fonts — no overflow, no drift.
                parts.append(
                    f'<text class="{cls}" x="{x:.1f}" y="{y}" xml:space="preserve" '
                    f'textLength="{len(s) * CHAR_W:.1f}" lengthAdjust="spacingAndGlyphs">{esc(s)}</text>'
                )
            x += len(s) * CHAR_W

    for i, segs in enumerate(art):
        emit(segs, PAD, art_y0 + (i + 1) * LINE_H - 5)
    for i, segs in enumerate(lines):
        emit(segs, info_x, PAD + (i + 1) * LINE_H - 5)
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> None:
    stats = github_stats()
    adds, dels = github_loc(stats["repo_names"])
    frame = (date.today() - EPOCH).days
    Path("profile.svg").write_text(render(aquarium(frame), build_lines(stats, adds, dels)))
    log.info("profile.svg written (frame %d, +%d/-%d, %s)", frame, adds, dels, stats)


if __name__ == "__main__":
    main()
