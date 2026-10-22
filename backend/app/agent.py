"""Analysis pipeline (docs/plan.md §4).

identity (R1) -> ToxIndex prediction + evidence (in parallel) -> local reference data
-> rules R2-R9 -> computed summary. The LLM narrative (R10) follows later.

At most 3 ToxIndex calls per analysis: identity, AmesFormer, genotoxicity.
"""

import asyncio
import time

from app import findings, reference, rules
from app.adapters import toxindex
from app.identity import resolve_identity
from app.reference import FINGERPRINT, MUTAGEN_DATASET
from app.schemas import AnalysisResult, Flag, NotRetrieved, Prediction, StructuralSupport
from app.trace import Tracer

ENDPOINT = "ames_mutagenicity"
EVIDENCE_SOURCES = "ToxIndex genotoxicity evidence (ISSSTY, Hansen, EFSA, ISSMIC)"

LIMITATIONS = [
    (
        "Ames detects gene mutations only. A negative result does not exclude clastogenic or "
        "aneugenic effects, or carcinogenicity through non-genotoxic mechanisms."
    ),
    (
        "AmesFormer-Pro reports no applicability domain; its probability is a model score, not a "
        "measure of how reliable the prediction is for this substance."
    ),
    (
        "The MutagenLou2023 train and test splits are used as a proxy for AmesFormer-Pro's "
        "training data (Hansen, ISSSTY). Its third stated source, EURL, is not covered."
    ),
    (
        "Structural similarity uses Morgan fingerprints (radius 2), which cannot distinguish some "
        "homologues; identity is therefore always checked by InChIKey."
    ),
    (
        "Experimental Ames results are shown as overall calls only; strain-level and metabolic "
        "activation (S9) detail is not displayed, although it matters for interpretation."
    ),
    "This is a research aid, not a regulatory assessment.",
]


async def _call(coro):
    """Run a ToxIndex call, returning the error instead of raising it."""
    try:
        return await coro
    except toxindex.ToxIndexError as exc:
        return exc


async def run_analysis(chemical_input: str) -> AnalysisResult:
    tracer = Tracer()
    identity, flags = await resolve_identity(chemical_input, tracer)
    result = AnalysisResult(chemical_input=chemical_input, endpoint=ENDPOINT, identity=identity)
    if identity.status != "resolved":
        result.flags, result.trace = flags, tracer.entries
        return result

    # ToxIndex: the prediction needs only the structure; the evidence tool is keyed on DSSTox,
    # so it is not called for substances outside the registry (it would return 422).
    ames_call = _call(toxindex.predict_ames(identity.smiles, tracer))
    if identity.in_dsstox:
        ames, genotox = await asyncio.gather(ames_call, _call(toxindex.genotoxicity(identity.dtxsid, tracer)))
    else:
        ames, genotox = await ames_call, None

    predictions: list[Prediction] = []
    not_retrieved: list[NotRetrieved] = []
    model = None
    if isinstance(ames, toxindex.ToxIndexError):
        not_retrieved.append(NotRetrieved(source="AmesFormer-Pro prediction",
                                          reason=f"call failed: {ames}", tool_ref=ames.ref))
    else:
        model = findings.from_amesformer(ames[1], ames[0])
        predictions.append(model)

    evidence, upstream, unclassified = [], None, []
    if genotox is None:
        not_retrieved.append(NotRetrieved(
            source=EVIDENCE_SOURCES,
            reason="not queried: the substance is not in EPA DSSTox, which these sources are keyed on",
        ))
    elif isinstance(genotox, toxindex.ToxIndexError):
        not_retrieved.append(NotRetrieved(source=EVIDENCE_SOURCES,
                                          reason=f"call failed: {genotox}", tool_ref=genotox.ref))
    else:
        more_predictions, evidence, gaps, upstream, unclassified = findings.from_genotoxicity(
            genotox[1], genotox[0]
        )
        predictions += more_predictions
        not_retrieved += gaps

    # Local reference data (independent of ToxIndex).
    ref_data = await asyncio.to_thread(reference.load)
    support = None
    if ref_data is None:
        not_retrieved.append(NotRetrieved(
            source="Local reference data (MutagenLou2023, EMA)",
            reason="not installed: run `uv run python -m app.reference_data`",
        ))
        regulatory_ref = tracer.record("local", "EMA acceptable-intake lookup", "error",
                                       error="reference data not installed")
        regulatory, r8_flags = rules.r8_nitrosamine(identity, lambda _key: None, regulatory_ref)
    else:
        support = _structural_support(ref_data, identity.smiles, identity.inchikey, tracer)
        regulatory_ref = tracer.record(
            "local", "EMA acceptable-intake lookup", "ok",
            {"inchikey": identity.inchikey, "revision": ref_data.ema_revision},
            ref_data.ema.get(identity.inchikey).model_dump() if identity.inchikey in ref_data.ema else None,
        )
        regulatory, r8_flags = rules.r8_nitrosamine(identity, ref_data.ema.get, regulatory_ref)

    tk_ref = tracer.record(
        "local", "httk lookup", "ok" if ref_data else "error",
        {"dtxsid": identity.dtxsid, "httk_version": ref_data.httk_version if ref_data else None},
        {"parameters": ref_data.httk_params.get(identity.dtxsid),
         "half_lives": [h.model_dump() for h in ref_data.httk_half_lives.get(identity.dtxsid, [])]}
        if ref_data and identity.dtxsid else None,
        error=None if ref_data else "reference data not installed",
    )
    toxicokinetics, r9_flags = rules.r9_toxicokinetics(identity.dtxsid, ref_data, tk_ref)

    flags += rules.r2_predicted_vs_observed(predictions, evidence, upstream, unclassified)
    flags += rules.r3_disagreement(predictions, evidence)
    flags += rules.r4_applicability(predictions)
    flags += rules.r5_independence(evidence, support)
    flags += rules.r6_structural_support(support, model)
    flags += rules.r7_not_retrieved(not_retrieved, evidence)
    flags += r8_flags
    flags += r9_flags

    result.flags = flags
    result.predictions = predictions
    result.evidence = evidence
    result.not_retrieved = not_retrieved
    result.upstream_verdict = upstream
    result.structural_support = support
    result.regulatory = regulatory
    result.toxicokinetics = toxicokinetics
    # A substance outside DSSTox only has PubChem's systematic name; EMA's common name is clearer.
    if not identity.in_dsstox and regulatory.ema:
        flags.append(Flag(rule_id="R1", severity="info", refs=[regulatory.tool_ref],
                          message=f"Name taken from the EMA list; PubChem's systematic name is "
                                  f"{identity.name}."))
        identity.name = regulatory.ema.name

    result.summary = rules.summarise(flags, predictions, evidence, support)
    result.limitations = LIMITATIONS
    result.trace = tracer.entries
    return result


def _structural_support(ref_data, smiles: str, key: str, tracer: Tracer) -> StructuralSupport:
    start = time.perf_counter()
    exact = ref_data.exact_match(key)
    neighbours = ref_data.nearest(smiles, k=5, exclude_key=key)
    ref = tracer.record(
        "local", "MutagenLou2023 neighbour search", "ok",
        {"smiles": smiles, "inchikey": key, "k": 5, "fingerprint": FINGERPRINT},
        {"exact_match": exact.model_dump() if exact else None,
         "neighbours": [n.model_dump() for n in neighbours]},
        duration_ms=round((time.perf_counter() - start) * 1000),
    )
    return StructuralSupport(dataset=MUTAGEN_DATASET, fingerprint=FINGERPRINT,
                             exact_match=exact, neighbours=neighbours, tool_ref=ref)
