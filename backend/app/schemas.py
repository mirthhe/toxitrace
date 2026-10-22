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


Call = Literal["positive", "negative", "equivocal", "unknown"]
Applicability = Literal["in_domain", "outside_domain", "not_reported"]


class Prediction(BaseModel):
    """A model or rule-based call. Never presented as an observation (rule R2)."""

    source: str  # e.g. "AmesFormer-Pro", "VEGA mutagenicity models"
    call: Call
    assay: str = "bacterial reverse mutation"
    # Upstream semantics kept as given: a probability is not converted into a call or back.
    probability: float | None = None
    threshold: float | None = None
    confidence: str | None = None  # upstream label, e.g. "Low"; not a probability
    applicability: Applicability = "not_reported"
    detail: str | None = None
    tool_ref: str


class Evidence(BaseModel):
    """A measured or curated experimental result, as labelled by its upstream source."""

    source: str
    method: Literal["experimental", "curated"]
    call: Call
    assay: str
    system: str | None = None
    detail: str | None = None
    confidence: str | None = None
    tool_ref: str


class NotRetrieved(BaseModel):
    """A source that was queried (or could not be) and returned nothing: absence of a result,
    not evidence of absence (rule R7)."""

    source: str
    reason: str
    tool_ref: str | None = None


class UpstreamVerdict(BaseModel):
    """ToxIndex's own aggregate verdict, shown for transparency next to ToxiTrace's summary."""

    conclusion: str
    basis: str | None = None
    confidence: str | None = None
    mechanism: str | None = None
    tool_ref: str


class Neighbour(BaseModel):
    smiles: str
    inchikey: str
    call: Call
    split: str
    similarity: float


class StructuralSupport(BaseModel):
    """Measured compounds near the query in the reference dataset (rules R5, R6)."""

    dataset: str
    fingerprint: str
    exact_match: Neighbour | None = None
    neighbours: list[Neighbour] = []
    tool_ref: str


class EmaEntry(BaseModel):
    name: str
    cpca_category: str | None = None
    ai_ng_per_day: float | None = None
    publication_date: str | None = None
    revision: str | None = None


class RegulatoryContext(BaseModel):
    """Nitrosamine context (rule R8)."""

    n_nitroso: bool
    ema: EmaEntry | None = None
    tool_ref: str


class HalfLife(BaseModel):
    species: str
    sex: str
    hours: float
    reference: str | None = None


TkStatus = Literal["half_lives", "parameters_only", "no_human_parameters", "not_in_httk", "not_assessed"]


class TkContext(BaseModel):
    """Toxicokinetic context from httk data (rule R9). Context only: never changes the verdict."""

    status: TkStatus
    compound: str | None = None
    clint_median: float | None = None  # human intrinsic hepatic clearance, uL/min/10^6 cells
    clint_reference: str | None = None
    fup_median: float | None = None  # human fraction unbound in plasma
    fup_reference: str | None = None
    half_lives: list[HalfLife] = []
    source: str | None = None
    tool_ref: str | None = None


SummaryLabel = Literal[
    "supported_positive", "supported_negative", "conflicting", "prediction_only", "insufficient"
]


class Summary(BaseModel):
    """ToxiTrace's computed overall assessment; derived from the flags, not generated."""

    label: SummaryLabel
    text: str
    basis: list[str] = []  # rule ids that determined the label


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
    summary: Summary | None = None
    flags: list[Flag] = []
    predictions: list[Prediction] = []
    evidence: list[Evidence] = []
    not_retrieved: list[NotRetrieved] = []
    upstream_verdict: UpstreamVerdict | None = None
    structural_support: StructuralSupport | None = None
    regulatory: RegulatoryContext | None = None
    toxicokinetics: TkContext | None = None
    interpretation: str | None = None
    limitations: list[str] = []
    checks: list[Check] = []
    trace: list[TraceEntry] = []
