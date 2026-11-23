"""Cuts the web take into the finished demo: a short title card, the take, and one GIF of the finding for the README.

    reshoot edit tools/demo/edit.py takes/demo.mp4

Writes takes/demo-final.mp4, takes/demo-final.srt and docs/finding.gif.
"""
import sys, tempfile
from pathlib import Path

from reshoot import cut

BG, SAGE, GREY = (23, 35, 32), (156, 197, 176), (147, 165, 157)
W, H = 1920, 1080


def main(web):
    web = Path(web)
    b = cut.beats(web)
    out = web.parent
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        title = (cut.Card(W, H, BG)
                 .text(None, 430, "claim-evidence-check", 96, 700)
                 .text(None, 560, "a claim-vs-evidence rule for Claude Code sessions", 40, 500, SAGE)
                 .text(None, 640, "prototype, not affiliated with Stacktrace", 30, 400, GREY))
        parts = [cut.still(title.save(t / "title.png"), 2.6, t / "title.mp4"),
                 cut.trim(web, 0, cut.duration(web), t / "web.mp4", fade_in=0.3, fade_out=0.6)]
        cut.concat(parts, out / "demo-final.mp4")
        cut.write_srt(cut.cues(web, 0, cut.duration(web), 2.6), out / "demo-final.srt")
    docs = Path(__file__).resolve().parents[2] / "docs"
    cut.gif(web, b["replay"], b["natural"] - 0.2, docs / "finding.gif", fps=12, width=900)
    for f in (out / "demo-final.mp4", docs / "finding.gif"):
        print(f"  {f}  {cut.duration(f):5.1f}s  {f.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main(*(sys.argv[1:] or ["takes/demo.mp4"]))
