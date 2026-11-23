"""FastAPI backend for the demo UI.

  uv run uvicorn claimcheck.server:app --port 8000
"""

import json
import os
import tempfile
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile

from .claims import LLMRateLimited
from .rules import Report, check_file

ROOT = Path(__file__).resolve().parent.parent
SESSIONS = Path(os.environ.get("CEC_SESSIONS", ROOT / "sessions"))
app = FastAPI(title="claim-evidence-check")


def _load_env():
    p = ROOT / ".env"
    if p.exists():
        for ln in p.read_text().splitlines():
            if "=" in ln and not ln.lstrip().startswith("#"):
                k, v = ln.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"'))


_load_env()


def _labels() -> dict:
    p = SESSIONS / "labels.json"
    return json.loads(p.read_text()) if p.exists() else {}


@lru_cache(maxsize=64)
def _check(name: str) -> Report:
    # The UI shows the local (--no-llm) result live; LLM numbers come from the saved benchmark run.
    return check_file(SESSIONS / name, use_llm=False)


def _view(rep: Report) -> dict:
    events = []
    for e in rep.events:
        d = e.model_dump(exclude_none=True)
        if len(d.get("text", "")) > 2000:
            d["text"] = d["text"][:1000] + "\n…\n" + d["text"][-1000:]
        events.append(d)
    return {"events": events, "runs": [r.model_dump() for r in rep.runs], "claims": [c.model_dump() for c in rep.claims],
            "findings": [f.model_dump() | {"notifies": f.notifies} for f in rep.findings], "seconds": rep.seconds}


@app.get("/api/sessions")
def sessions():
    out = []
    for name, lab in _labels().items():
        rep = _check(name)
        top = next((f for f in rep.findings if f.notifies), rep.findings[0] if rep.findings else None)
        first = next((e.timestamp for e in rep.events if e.timestamp), None)
        out.append({"id": name, **lab, "found": sorted({f.rule_id for f in rep.findings}),
                    "severity": top.severity if top else None, "confidence": top.confidence if top else None,
                    "time": first, "events": len(rep.events), "runs": len(rep.runs)})
    return out


@app.get("/api/sessions/{sid}")
def session(sid: str):
    labels = _labels()
    if sid not in labels:
        raise HTTPException(404, "unknown session")
    return {"id": sid, **labels[sid], **_view(_check(sid))}


@app.get("/api/hook/{sid}")
def hook(sid: str):
    """What the Stop hook would answer if the agent tried to stop at the end of this session."""
    from .hook import decide
    if sid not in _labels() and not (SESSIONS / "steer" / sid).exists():
        raise HTTPException(404, "unknown session")
    path = SESSIONS / sid if (SESSIONS / sid).exists() else SESSIONS / "steer" / sid
    return {"input": {"hook_event_name": "Stop", "transcript_path": f"sessions/{sid}", "stop_hook_active": False},
            "output": decide({"transcript_path": str(path), "stop_hook_active": False})}


@app.get("/api/steer")
def steer():
    p = SESSIONS / "steer" / "labels.json"
    labels = json.loads(p.read_text()) if p.exists() else {}
    out = []
    for name, lab in labels.items():
        rep = check_file(SESSIONS / "steer" / name, use_llm=False)
        out.append({"id": name, **lab, **_view(rep)})
    return out


@app.post("/api/check")
async def check(file: UploadFile, llm: bool = False):
    data = await file.read()
    if len(data) > 50_000_000:
        raise HTTPException(413, "file too large")
    with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False) as tmp:
        tmp.write(data)
    try:
        rep = check_file(tmp.name, use_llm=llm)
    except LLMRateLimited as e:
        raise HTTPException(429, f"Groq rate limit: {e}")
    finally:
        os.unlink(tmp.name)
    return {"id": file.filename, **_view(rep)}


@app.get("/api/benchmark")
def benchmark():
    p = SESSIONS / "benchmark.json"
    if not p.exists():
        raise HTTPException(404, "run: python cli.py --all sessions/ --json (see README)")
    return json.loads(p.read_text())
