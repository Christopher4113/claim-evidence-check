# Demo video

Recorded from the web UI with [reshoot](https://pypi.org/project/reshoot/) in headless Chrome. Only the page is captured, and it shows only the demo-repo sessions in `sessions/`.

```bash
uv run uvicorn claimcheck.server:app --port 8000          # terminal 1
npm --prefix web run dev -- --port 5173                    # terminal 2
reshoot web tools/demo/storyboard.py takes/demo.mp4        # record (about 1 min)
reshoot check takes/demo.assets.json takes/demo.mp4 --review takes/review --every 2   # privacy sheets, look at each
reshoot edit tools/demo/edit.py takes/demo.mp4             # takes/demo-final.mp4, docs/finding.gif
```

- The UI is opened with `?demo`, which keeps routing in memory and pads the page bottom. Headless Chrome treats a hash change as a page load that never finishes, and the padding lets a section scroll to the top.
- Zoom: automatic zoom is capped at 1x. Only two explicit `__demo.zoom` calls move the camera: the finding card, and the Stop hook's block output.
- `takes/` is git-ignored. The storyboard and edit script are the recipe for reshooting after the UI changes.
