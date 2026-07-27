"""Render profile.svg — a neofetch-style panel with live GitHub stats.

Always dark: GitHub renders README images identically in both site themes
(CSS prefers-color-scheme tracks the OS, not the GitHub theme setting), so
the panel is a fixed dark terminal card like a screenshot would be.

Runs nightly via GitHub Actions (GITHUB_TOKEN env) and locally with
`GITHUB_TOKEN=$(gh auth token) python3 generate.py`.
"""
import json
import logging
import os
import urllib.request
from datetime import date
from pathlib import Path

LOGIN = "DJuboor"
BORN = date(1992, 12, 5)
FONT = 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace'
CHAR_W, LINE_H, FONT_SIZE = 7.85, 19, 13
PAD, ART_INFO_GAP = 28, 34
INFO_WIDTH = 62  # characters per info line, including the ". " prefix
BUBBLE_CHARS = set("oO°")

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

Seg = tuple[str, str]  # (css class, text)


def github_stats() -> dict[str, int]:
    """Fetch public repo/star/follower/commit counts via the GraphQL API."""
    query = """
    query($login: String!) {
      user(login: $login) {
        followers { totalCount }
        repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC) {
          totalCount
          nodes { stargazerCount }
        }
        repositoriesContributedTo(contributionTypes: [COMMIT]) { totalCount }
        contributionsCollection { totalCommitContributions }
      }
    }"""
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": {"login": LOGIN}}).encode(),
        headers={"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}"},
    )
    with urllib.request.urlopen(req) as resp:
        user = json.load(resp)["data"]["user"]
    return {
        "repos": user["repositories"]["totalCount"],
        "stars": sum(n["stargazerCount"] for n in user["repositories"]["nodes"]),
        "followers": user["followers"]["totalCount"],
        "contributed": user["repositoriesContributedTo"]["totalCount"],
        "commits": user["contributionsCollection"]["totalCommitContributions"],
    }


def kv(key: str, value: str, width: int = INFO_WIDTH - 2) -> list[Seg]:
    """`. Key: ..... value` — dotted leaders pad the value to the right edge."""
    dots = "." * max(1, width - len(key) - len(value) - 3)
    return [("dots", ". "), ("key", f"{key}:"), ("dots", f" {dots} "), ("val", value)]


def pair(k1: str, v1: str, k2: str, v2: str) -> list[Seg]:
    """Two stats on one line, original-style: `. K1: .. v1 | K2: .. v2`."""
    left = kv(k1, v1, width=35)
    right = kv(k2, v2, width=INFO_WIDTH - 2 - 35 - 3)[1:]  # no ". " prefix
    return left + [("dots", " | ")] + right


def rule(title: str, cls: str) -> list[Seg]:
    prefix = "" if cls == "title" else "- "
    bar = "─" * (INFO_WIDTH - len(prefix) - len(title) - 4)
    return [("dots", prefix), (cls, title), ("dots", f" {bar}-·-")]


def build_lines(stats: dict[str, int]) -> list[list[Seg]]:
    today = date.today()
    years = today.year - BORN.year - ((today.month, today.day) < (BORN.month, BORN.day))
    months = (today.month - BORN.month - (today.day < BORN.day)) % 12
    anchor_month = today.month - (today.day < BORN.day)
    anchor = date(today.year - (anchor_month < 1), (anchor_month - 1) % 12 + 1, BORN.day)
    days = (today - anchor).days
    year_pct = today.timetuple().tm_yday * 100 // 365
    bar = ("█" * (year_pct // 8)).ljust(12, "░")
    return [
        rule("davidj@imagineering", "title"),
        [],
        kv("OS", "macOS / Ubuntu (aarch64)"),
        kv("Uptime", f"{years} years, {months} months, {days} days"),
        kv("Host", "Princ. MLE @ Imagineering"),
        kv("Kernel", "ChemE (Drexel) → Applied ML"),
        kv("Shell", "Python · PyTorch"),
        kv("Packages", "9 patents (5 granted) · 3 papers"),
        kv("Shipped", "JARVIS · PhotoPass · OpenAnnotate"),
        [],
        kv("Languages.Programming", "Python, SQL, Bash"),
        kv("Languages.Computer", "JSON, YAML, LaTeX, Markdown"),
        kv("Languages.Real", "English, Spanish (in progress)"),
        [],
        kv("Hobbies.Software", "homelab inference, agent harnesses"),
        kv("Hobbies.Hardware", "DGX Spark, Pi cluster, OPNsense"),
        kv("Hobbies.Others", "scuba diving, jazz theory"),
        [],
        rule("Contact", "key"),
        kv("Web", "davidj.today"),
        kv("GitHub", "github.com/DJuboor"),
        kv("LinkedIn", "in/davidnjuboor"),
        kv("Gaming", "Mr.Bubbles"),
        [],
        rule("GitHub Stats", "key"),
        pair("Repos", f"{stats['repos']} {{Contributed: {stats['contributed']}}}", "Stars", str(stats["stars"])),
        pair("Commits", f"{stats['commits']:,}", "Followers", str(stats["followers"])),
        [],
        kv("Status", f"LOADING.. [{bar}] {year_pct}%"),
    ]


def art_segments(line: str) -> list[Seg]:
    """Split an art line into kelp (green) and bubble (blue) runs."""
    segs: list[Seg] = []
    for c in line:
        cls = "bub" if c in BUBBLE_CHARS else "art"
        if segs and segs[-1][0] == cls:
            segs[-1] = (cls, segs[-1][1] + c)
        else:
            segs.append((cls, c))
    return segs


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(art: list[str], lines: list[list[Seg]]) -> str:
    art_w = max(len(l) for l in art) * CHAR_W
    info_x = PAD + art_w + ART_INFO_GAP
    width = round(info_x + INFO_WIDTH * CHAR_W + PAD)
    rows = max(len(art), len(lines))
    height = round(rows * LINE_H + 2 * PAD)
    art_y0 = PAD + ((rows - len(art)) // 2) * LINE_H

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="davidj profile">',
        f"""<style>
    text {{ font-family: {FONT}; font-size: {FONT_SIZE}px; white-space: pre; }}
    .bg {{ fill: #0d1117; stroke: #30363d; }}
    .art {{ fill: #3fb950; }}
    .bub {{ fill: #79c0ff; }}
    .title {{ fill: #58a6ff; font-weight: 600; }}
    .key {{ fill: #ffa657; }}
    .dots {{ fill: #3d444d; }}
    .val {{ fill: #e6edf3; }}
  </style>""",
        f'<rect class="bg" x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="8"/>',
    ]

    def seg(cls: str, x: float, y: int, s: str) -> str:
        # textLength pins glyph advance so layout is identical across platform
        # monospace fonts (SF Mono, Consolas, ...) — no overflow, no drift.
        return (
            f'<text class="{cls}" x="{x:.1f}" y="{y}" xml:space="preserve" '
            f'textLength="{len(s) * CHAR_W:.1f}" lengthAdjust="spacingAndGlyphs">{esc(s)}</text>'
        )

    def emit(segs: list[Seg], x: float, y: int) -> None:
        for cls, s in segs:
            if s.strip():
                parts.append(seg(cls, x, y, s))
            x += len(s) * CHAR_W

    for i, line in enumerate(art):
        emit(art_segments(line), PAD, art_y0 + (i + 1) * LINE_H - 5)
    for i, segs in enumerate(lines):
        emit(segs, info_x, PAD + (i + 1) * LINE_H - 5)
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> None:
    art = Path("art.txt").read_text().rstrip("\n").splitlines()
    stats = github_stats()
    Path("profile.svg").write_text(render(art, build_lines(stats)))
    log.info("profile.svg written (%s)", stats)


if __name__ == "__main__":
    main()
