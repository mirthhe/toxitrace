"""Application data contract (SPEC §5).

This is OUR schema, not a documented ToxIndex response. Revise once the real API has been inspected.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

CheckStatus = Literal["passed", "failed", "not_run"]
TraceStatus = Literal["ok", "error", "timeout", "rate_limited"]


class AnalysisRequest(BaseModel):
    chemical_input: str = Field(min_length=1)


class Prediction(BaseModel):
    source: Literal["toxindex"] = "toxindex"
    model_id: str
    # Keep upstream semantics: categorical, probabilistic or numeric. No silent conversion.
    raw_value: Any
    unit: str | None = None
    tool_ref: str


class Evidence(BaseModel):
    source: str
    description: str
    value: Any
    unit: str | None = None
    tool_ref: str


class Check(BaseModel):
    name: str
    status: CheckStatus = "not_run"
    detail: str | None = None


class TraceEntry(BaseModel):
    ref: str
    tool: str
    status: TraceStatus
    request: dict[str, Any] = {}
    # Sanitized upstream response; never contains credentials.
    response: Any = None
    error: str | None = None


class AnalysisResult(BaseModel):
    chemical_input: str
    endpoint: str
    predictions: list[Prediction] = []
    evidence: list[Evidence] = []
    evidence_retrieved: bool = False
    interpretation: str | None = None
    limitations: list[str] = []
    checks: list[Check] = []
    trace: list[TraceEntry] = []
