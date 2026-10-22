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
