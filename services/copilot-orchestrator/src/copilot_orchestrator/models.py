from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AnalyzeRequest(BaseModel):
    # Clients (console, smoke.py, `make analyze`) send camelCase `siteId` like the rest of the
    # API; `site_id` is still accepted (populate_by_name) for older callers.
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    site_id: str = Field(alias="siteId", pattern=r"^SITE-\d{3}$")
    window: str = Field(default="30m", pattern=r"^\d{1,3}m$")

    @property
    def window_minutes(self) -> int:
        return int(self.window.rstrip("m"))

    @field_validator("window")
    @classmethod
    def validate_window_range(cls, v: str) -> str:
        minutes = int(v.rstrip("m"))
        if not 1 <= minutes <= 720:
            raise ValueError("window must be between 1m and 720m")
        return v


class AlarmRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    siteId: str
    specificProblem: str
    perceivedSeverity: str
    alarmRaisedTime: str
    role: str


class AnomalyRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    cellId: str
    kpi: str
    ts: str
    score: float
    direction: str


class RunbookRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runbookId: str
    title: str
    section: str
    snippet: str


class Context(BaseModel):
    model_config = ConfigDict(extra="forbid")

    site_id: str
    window_minutes: int
    alarms: list[AlarmRef]
    anomalies: list[AnomalyRef]
    fault: dict[str, Any] | None
    runbooks: list[RunbookRef]

    def source_ids(self) -> set[str]:
        ids: set[str] = set()
        for a in self.alarms:
            ids.add(a.id)
        for an in self.anomalies:
            ids.add(an.id)
        for r in self.runbooks:
            ids.add(r.runbookId)
        return ids


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=300)
    sources: list[str] = Field(min_length=1, max_length=5)


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=300)
    runbookId: str = Field(pattern=r"^RB-[A-Z]{3}-\d{3}$")
    section: str


class Answer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suspectedCause: str = Field(min_length=1, max_length=300)
    faultType: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[Claim] = Field(min_length=1, max_length=5)
    # May be empty only when no runbook was retrieved (enforced in validate_answer).
    steps: list[Step] = Field(max_length=6)


class ToolCall(BaseModel):
    """One evidence call made for this answer (shown as a chip in the console)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    ok: bool
    durationMs: int
    transport: Literal["mcp", "http"]


class AnalyzeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    siteId: str
    window: str
    answer: Answer
    generatedBy: Literal["llm", "fallback"]
    model: str | None
    attempts: int
    errors: list[str]
    context: Context
    sourceIds: list[str] = Field(description="Every id the answer was allowed to cite")
    warnings: list[str] = Field(default_factory=list, description="Upstream services that failed")
    toolCalls: list[ToolCall] = Field(default_factory=list)
    durationMs: int


class AnswerInvalid(Exception):
    def __init__(self, messages: list[str]) -> None:
        self.messages = messages
        super().__init__("; ".join(messages))


class NoEvidence(Exception):
    pass


class LLMError(Exception):
    pass
