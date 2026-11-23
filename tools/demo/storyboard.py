"""claim-evidence-check demo, about 75 seconds, recorded from the web UI.

Two deliberate zooms only: the finding card and the Stop hook's answer.
Everything else stays at full view so the viewer keeps their bearings.

    uv run uvicorn claimcheck.server:app --port 8000        # terminal 1
    npm --prefix web run dev -- --port 5173                  # terminal 2
    reshoot web tools/demo/storyboard.py takes/demo.mp4      # terminal 3
"""

URL = "http://localhost:5173/?demo"
SIZE = "1280x720@1.5"
ZOOM = {"scale": 1.0, "watch": False}  # automatic zoom capped at 1x (off); only the two __demo.zoom calls move the camera
# WARM is left out: hash-only views never fire a load event, which stalls the first beat.

W = "await __demo.waitFor"
# Put the replay (controls, steps, finding card) at the top of the view, so a zoom on the card clears the caption.
REPLAY = ("window.scrollTo({top: document.querySelector('[data-testid=\"replay\"]').getBoundingClientRect().top + scrollY - 120, "
          "behavior: 'smooth'}); await new Promise(r => setTimeout(r, 800)); ")
# Bring the screen's content (below the header) into view.
MAIN = ("window.scrollTo({top: document.querySelector('main').offsetTop - 4, behavior: 'smooth'}); "
        "await new Promise(r => setTimeout(r, 800)); ")

BEATS = [
    ("intro",
     "__demo.caption('Agents say the tests pass', 'This checks what the tests actually said'); "
     f"{W}('[data-testid=\"row-syn-ts-diagnose\"]', 15000)", 3.2),

    ("sessions",
     "__demo.caption('20 labelled Claude Code sessions', '16 real runs, 4 synthetic'); "
     "await __demo.scroll(240)", 2.8),

    ("open",
     "__demo.caption(null); await __demo.click('[data-testid=\"row-syn-ts-diagnose\"]'); "
     f"{W}('[data-testid=\"replay-steps\"]', 15000); " + REPLAY, 0.2),

    ("replay",
     "__demo.caption('Replay the session step by step', 'request, test run, final message'); "
     f"{W}('[data-testid=\"finding\"]', 30000)", 1.6),

    ("finding",
     "__demo.caption('The claim against its own test output'); "
     "await __demo.zoom('[data-testid=\"finding\"]', {scale: 1.35})", 4.8),

    ("cited",
     "__demo.zoomOut(); __demo.caption('Both cited steps are highlighted', 'line 41: Tests 7 failed | 1 passed'); "
     "await __demo.to('[data-line=\"41\"]')", 3.2),

    ("natural",
     "__demo.caption('A real run: \"Fixed all 6 failures\"', 'the agent said it did not rerun the tests'); "
     "await __demo.click('[data-testid=\"tab-sessions\"]'); "
     f"{W}('[data-testid=\"row-py-no-rerun\"]', 15000); "
     "await __demo.click('[data-testid=\"row-py-no-rerun\"]'); " +
     f"{W}('[data-testid=\"replay\"]', 15000); " + REPLAY +
     f"{W}('[data-testid=\"finding\"]', 40000)", 0.8),

    ("natural-result",
     "__demo.caption('Hedged, so medium confidence', 'recorded, not notified'); "
     "await __demo.to('[data-testid=\"finding\"]')", 3.4),

    ("steer",
     "__demo.caption('A Stop hook blocks the false \"done\"'); "
     "await __demo.click('[data-testid=\"tab-steer\"]'); "
     f"{W}('[data-testid=\"hook\"] pre', 15000); " + MAIN, 1.2),

    ("hook",
     "__demo.caption('and hands the failing tests back to the agent'); "
     "await __demo.zoom('[data-testid=\"hook-out\"]', {scale: 1.7})", 4.6),

    ("bench",
     "__demo.zoomOut(); __demo.caption(null); "
     "await __demo.click('[data-testid=\"tab-benchmark\"]'); "
     f"{W}('[data-testid=\"stats-no-llm\"]', 15000); " + MAIN, 0.4),

    ("stats",
     "__demo.caption('6 of 6 found, 0 false positives', 'fully local; the LLM mode matches'); "
     "await __demo.to('[data-testid=\"stats-no-llm\"]')", 4.2),

    ("stacktrace",
     "__demo.caption('Stacktrace\\u2019s live sidecar: no rule for this yet'); "
     "document.querySelector('[data-testid=\"stacktrace\"]').scrollIntoView({behavior: 'smooth', block: 'center'}); "
     "await new Promise(r => setTimeout(r, 900))", 3.4),

    ("end",
     "__demo.caption('claim-evidence-check', 'Prototype by Christopher Lam, not affiliated with Stacktrace'); "
     "__demo.hide()", 3.2),
]
