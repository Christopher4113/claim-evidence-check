from typing import Literal

from pydantic import BaseModel

Level = Literal["low", "medium", "high"]
ClaimKind = Literal["tests_pass", "build_ok", "bug_fixed", "task_done"]


class Event(BaseModel):
    line: int  # 1-based line in the .jsonl
    kind: Literal["user", "assistant_text", "tool_use", "tool_result"]
    text: str = ""
    tool_name: str | None = None
    tool_input: dict | None = None
    tool_use_id: str | None = None
    is_error: bool = False
    timestamp: str | None = None


class TestRun(BaseModel):
    __test__ = False  # not a pytest class
    event_line: int  # line of the tool_use
    result_line: int | None = None  # line of the tool_result
    tool_use_id: str
    command: str
    status: Literal["pass", "fail", "unknown"]
    exact: bool  # True when a runner summary line was parsed; False = exit code only / nothing
    passed: int | None = None
    failed: int | None = None
    failing_names: list[str] = []
    excerpt: str = ""  # real summary line(s) copied from the output


class Claim(BaseModel):
    line: int
    text: str  # the matched sentence
    context: str = ""  # sentence plus neighbours
    kind: ClaimKind
    scope: str | None = None
    hedged: bool = False


class Evidence(BaseModel):
    line: int
    role: Literal["claim", "test_call", "test_result", "edit"]
    text: str
    tool_use_id: str | None = None


class Finding(BaseModel):
    rule_id: str
    severity: Level
    confidence: Level
    message: str
    evidence: list[Evidence]
    fix: str

    @property
    def notifies(self) -> bool:
        # Stacktrace grading: notify only when severity >= medium AND confidence == high.
        return self.severity in ("medium", "high") and self.confidence == "high"
