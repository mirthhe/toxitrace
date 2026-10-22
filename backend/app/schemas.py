"""Application data contract (SPEC §5).

This is OUR schema, not a ToxIndex response. Upstream response shapes are documented in
docs/discovery-notes.md; adapters translate them into these models.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

CheckStatus = Literal["passed", "failed", "not_run"]
TraceStatus = Literal["ok", "not_found", "error", "timeout", "rate_limited"]
Severity = Literal["info", "caution", "conflict"]
InputType = Literal["cas", "smiles", "dtxsid", "name"]
IdentityStatus = Literal["resolved", "ambiguous", "not_found"]


class AnalysisRequest(BaseModel):
    chemical_input: str = Field(min_length=1)


class Flag(BaseModel):
    """Output of one weight-of-evidence rule (docs/plan.md §3)."""

    rule_id: str
    severity: Severity
    message: str
    refs: list[str] = []  # trace refs the flag is based on


class Candidate(BaseModel):
    """One substance a registry matched; several of these means the input is ambiguous."""

    name: str | None = None
    dtxsid: str | None = None
    cas: str | None = None
    inchikey: str | None = None
    smiles: str | None = None
    formula: str | None = None


class Identity(BaseModel):
    input: str
    input_type: InputType
    status: IdentityStatus
    name: str | None = None
    smiles: str | None = None  # the structure every downstream step uses
    inchikey: str | None = None
    formula: str | None = None
    dtxsid: str | None = None
    cas: str | None = None
    pubchem_cid: int | None = None
    in_dsstox: bool = False
    candidates: list[Candidate] = []  # filled when status == "ambiguous"


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
    source: str  # "toxindex", "pubchem", "local"
    tool: str
    status: TraceStatus
    request: dict[str, Any] = {}
    # Sanitized upstream response; never contains credentials.
    response: Any = None
    error: str | None = None
    duration_ms: int | None = None
    retrieved_at: datetime


class AnalysisResult(BaseModel):
    chemical_input: str
    endpoint: str
    identity: Identity | None = None
    flags: list[Flag] = []
    predictions: list[Prediction] = []
    evidence: list[Evidence] = []
    evidence_retrieved: bool = False
    interpretation: str | None = None
    limitations: list[str] = []
    checks: list[Check] = []
    trace: list[TraceEntry] = []
