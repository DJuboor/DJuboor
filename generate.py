"""Render profile.svg — a neofetch-style panel with live GitHub stats.

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
CAREER_START = date(2011, 1, 1)
FONT = 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace'
CHAR_W, LINE_H, FONT_SIZE = 7.85, 19, 13
PAD, ART_INFO_GAP = 28, 34
INFO_WIDTH = 62  # characters, key + leader dots + value

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)


def github_stats() -> dict[str, int]:
    """Fetch public repo/star/follower counts via the GraphQL API."""
    query = """
    query($login: String!) {
      user(login: $login) {
        followers { totalCount }
        repositories(first: 100, ownerAffiliations: OWNER, privacy: PUBLIC) {
          totalCount
          nodes { stargazerCount }
        }
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
    }


def kv(key: str, value: str) -> tuple[str, str, str]:
    """A key line with dotted leaders padding the value to the right edge."""
    dots = "." * max(1, INFO_WIDTH - len(key) - len(value) - 4)
    return (f"{key}:", f" {dots} ", value)


def build_lines(stats: dict[str, int]) -> list[tuple[str, ...]]:
    today = date.today()
    years = (today - CAREER_START).days // 365
    year_pct = today.timetuple().tm_yday * 100 // 365
    return [
        ("davidj@imagineering", "", ""),
        ("─" * INFO_WIDTH, "", ""),
        kv("OS", "macOS / Ubuntu (aarch64)"),
        kv("Host", "Walt Disney Imagineering"),
        kv("Kernel", "ChemE (Drexel) → Applied ML"),
        kv("Uptime", f"{years}+ years in production"),
        kv("Shell", "Python · PyTorch"),
        ("", "", ""),
        kv("Focus.Current", "LLM agents, multimodal doc intel"),
        kv("Focus.Vision", "CV, OCR, style transfer, relighting"),
        kv("Focus.Robotics", "animatronics (45-DOF)"),
        kv("Infra", "vLLM · LiteLLM · self-hosted"),
        ("", "", ""),
        kv("Patents", "9 (5 granted)"),
        kv("Papers", "3 (ACS OPRD, VQA, embeddings)"),
        kv("Ships", "JARVIS · PhotoPass · OpenAnnotate"),
        kv("Gaming", "Mr.Bubbles"),
        ("", "", ""),
        kv("Repos.Public", str(stats["repos"])),
        kv("Stars", str(stats["stars"])),
        kv("Followers", str(stats["followers"])),
        ("", "", ""),
        kv("Web", "davidj.today"),
        kv("GitHub", "github.com/DJuboor"),
        kv("LinkedIn", "in/davidnjuboor"),
        ("", "", ""),
        kv("Status", f"LOADING.. [{('█' * (year_pct // 8)).ljust(12, '░')}] {year_pct}%"),
    ]


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(art: list[str], lines: list[tuple[str, ...]]) -> str:
    art_w = max(len(l) for l in art) * CHAR_W
    info_x = PAD + art_w + ART_INFO_GAP
    width = round(info_x + INFO_WIDTH * CHAR_W + PAD)
    rows = max(len(art), len(lines))
    height = round(rows * LINE_H + 2 * PAD)
    art_y0 = PAD + ((rows - len(art)) // 2) * LINE_H  # vertically center the art

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="davidj profile">',
        f"""<style>
    text {{ font-family: {FONT}; font-size: {FONT_SIZE}px; white-space: pre; }}
    .bg {{ fill: #f6f8fa; stroke: #d0d7de; }}
    .art {{ fill: #1a7f37; }}
    .title {{ fill: #0969da; font-weight: 600; }}
    .key {{ fill: #953800; }}
    .dots {{ fill: #8c959f; }}
    .val {{ fill: #24292f; }}
    @media (prefers-color-scheme: dark) {{
      .bg {{ fill: #161b22; stroke: #30363d; }}
      .art {{ fill: #3fb950; }}
      .title {{ fill: #58a6ff; }}
      .key {{ fill: #ffa657; }}
      .dots {{ fill: #484f58; }}
      .val {{ fill: #c9d1d9; }}
    }}
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

    for i, line in enumerate(art):
        y = art_y0 + (i + 1) * LINE_H - 5
        parts.append(seg("art", PAD, y, line))
    for i, (key, dots, val) in enumerate(lines):
        y = PAD + (i + 1) * LINE_H - 5
        cls = "title" if i == 0 else "dots" if i == 1 else "key"
        x = info_x
        for c, s in ((cls, key), ("dots", dots), ("val", val)):
            if s:
                parts.append(seg(c, x, y, s))
                x += len(s) * CHAR_W
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> None:
    art = Path("art.txt").read_text().rstrip("\n").splitlines()
    stats = github_stats()
    Path("profile.svg").write_text(render(art, build_lines(stats)))
    log.info("profile.svg written (%s)", stats)


if __name__ == "__main__":
    main()
