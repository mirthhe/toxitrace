"""Translate ToxIndex responses into ToxiTrace's predictions and evidence (rule R2).

Every finding is classified by its upstream `method` label, never by which tool returned it:
tox_genotoxicity is an "evidence" tool, but some of its findings are model predictions.
Response shapes: docs/discovery-notes.md.
"""

from app.schemas import Call, Evidence, NotRetrieved, Prediction, UpstreamVerdict

AMES_ASSAYS = {"bacterial reverse mutation", "structural alerts"}

# VEGA reports applicability in free text in `detail`; these are the phrasings observed.
VEGA_OUTSIDE_DOMAIN = "no model met the reliability threshold"
VEGA_IN_DOMAIN = "models reliable"


def normalise_call(value: object) -> Call:
    if isinstance(value, bool):
        return "positive" if value else "negative"
    text = str(value or "").strip().lower()
    if text in {"positive", "mutagenic", "mutagen"}:
        return "positive"
    if text in {"negative", "non-mutagenic", "non-mutagen"}:
        return "negative"
    if text == "equivocal":
        return "equivocal"
    return "unknown"


def from_amesformer(body: dict, ref: str) -> Prediction:
    """toxjobs_predict(amesformer): {"output": {model, mutagenic, probability, threshold, smiles}}."""
    out = body["output"]
    return Prediction(
        source=out.get("model", "AmesFormer"),
        call=normalise_call(out.get("mutagenic")),
        probability=out.get("probability"),
        threshold=out.get("threshold"),
        detail=f"P(Ames-positive) = {out['probability']:.4g}; call at threshold {out.get('threshold')}",
        tool_ref=ref,
    )


def from_vega(body: dict, ref: str) -> Prediction:
    """toxjobs_predict(vega-mutagenicity): one entry per VEGA model (CAESAR, ISS, SarPy, kNN).

    Summarised as one prediction, like tox_genotoxicity does, but keeping the model version and
    the applicability-domain (AD) indices that the aggregated finding leaves out. Reliability
    labels are taken from VEGA's own assessment text, not from our own AD thresholds.
    """
    out = body["output"]
    models = out.get("predictions", [])
    calls = [normalise_call(m.get("prediction")) for m in models]
    definite = {c for c in calls if c in ("positive", "negative")}
    call = definite.pop() if len(definite) == 1 and "unknown" not in calls else (
        "equivocal" if len(definite) > 1 else "unknown")
    reliabilities = {_reliability(m.get("assessment", "")) for m in models} - {None}
    low_only = reliabilities == {"low"} or not models
    ad = [m["ad_index"] for m in models if m.get("ad_index") is not None]
    ad_text = f"AD index {min(ad):.2f}–{max(ad):.2f}" if ad else "no AD index reported"
    return Prediction(
        source=f"VEGA mutagenicity models ({out.get('model', 'version not reported')})",
        call=call,
        confidence=", ".join(sorted(r.capitalize() for r in reliabilities)) or None,
        applicability="outside_domain" if low_only else "in_domain",
        detail=f"{sum(c == call for c in calls)} of {len(models)} models {call}; {ad_text}",
        tool_ref=ref,
    )


def _reliability(assessment: str) -> str | None:
    """VEGA assessments read like "Mutagenic (MODERATE reliability)"."""
    text = assessment.lower()
    for level in ("high", "moderate", "low"):
        if f"{level} reliability" in text:
            return level
    return None


def _applicability(finding: dict) -> str:
    detail = (finding.get("detail") or "").lower()
    if "vega" not in finding.get("source", "").lower():
        return "not_reported"
    if VEGA_OUTSIDE_DOMAIN in detail:
        return "outside_domain"
    if VEGA_IN_DOMAIN in detail:
        return "in_domain"
    return "not_reported"


def from_genotoxicity(
    body: dict, ref: str
) -> tuple[list[Prediction], list[Evidence], list[NotRetrieved], UpstreamVerdict | None, list[str]]:
    """Split tox_genotoxicity findings by method.

    Returns predictions, evidence, sources listed as gaps, the upstream verdict, and messages
    about findings that could not be classified (kept out of both lists, never guessed).
    """
    predictions, evidence, unclassified = [], [], []
    for finding in body.get("findings", []):
        method = (finding.get("method") or "").lower()
        common = {
            "source": finding.get("source", "unknown source"),
            "call": normalise_call(finding.get("call")),
            "assay": finding.get("assay", "unknown assay"),
            "detail": finding.get("detail"),
            "confidence": finding.get("confidence"),
            "tool_ref": ref,
        }
        if method == "predicted":
            predictions.append(Prediction(**common, applicability=_applicability(finding)))
        elif method in ("experimental", "curated"):
            evidence.append(Evidence(**common, method=method, system=finding.get("system")))
        else:
            unclassified.append(f"{common['source']}: unrecognised method '{finding.get('method')}'")

    gaps = [
        NotRetrieved(source=g, reason="queried by ToxIndex; no record for this substance", tool_ref=ref)
        for g in body.get("gaps", [])
    ]
    verdict = body.get("verdict")
    upstream = (
        UpstreamVerdict(
            conclusion=verdict.get("conclusion", ""),
            basis=verdict.get("basis"),
            confidence=verdict.get("confidence"),
            mechanism=verdict.get("mechanism"),
            tool_ref=ref,
        )
        if verdict
        else None
    )
    return predictions, evidence, gaps, upstream, unclassified


def is_ames(assay: str) -> bool:
    return assay.lower() in AMES_ASSAYS
