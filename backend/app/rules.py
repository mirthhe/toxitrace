"""Weight-of-evidence rules R2-R8 (docs/plan.md §3) and the computed summary.

Each rule is a pure function over already-normalised data and returns flags; none of them
calls an API. The scientific rationale is in docs/science-notes.md.
"""

from rdkit import Chem

from app.findings import is_ames
from app.schemas import (
    Evidence,
    Flag,
    Identity,
    NotRetrieved,
    Prediction,
    RegulatoryContext,
    StructuralSupport,
    Summary,
    TkContext,
    UpstreamVerdict,
)

SIMILARITY_THRESHOLD = 0.4  # docs/plan.md §7: heuristic, raw similarity always shown
N_NITROSO = Chem.MolFromSmarts("[NX3;!$(N~[O,S])]-N=O")


def _refs(*items) -> list[str]:
    return sorted({i.tool_ref for i in items if getattr(i, "tool_ref", None)})


def _describe(p: Prediction) -> str:
    extra = f", P = {p.probability:.3g}" if p.probability is not None else ""
    extra += f", confidence {p.confidence}" if p.confidence else ""
    return f"{p.source}: {p.call}{extra}"


def r2_predicted_vs_observed(
    predictions: list[Prediction],
    evidence: list[Evidence],
    upstream: UpstreamVerdict | None,
    unclassified: list[str],
) -> list[Flag]:
    """Predictions and observations are kept apart by their upstream `method` label.

    An aggregate verdict whose basis is "predicted" is a model statement, not a hazard
    conclusion, and is flagged as such.
    """
    flags = []
    if upstream and (upstream.basis or "").lower() == "predicted":
        flags.append(Flag(
            rule_id="R2", severity="caution", refs=[upstream.tool_ref],
            message=f"ToxIndex's aggregate verdict \"{upstream.conclusion}\" rests on predictions "
                    "only (basis: predicted). It is shown as a model statement, not as a hazard "
                    "conclusion.",
        ))
    for item in unclassified:
        flags.append(Flag(rule_id="R2", severity="caution", refs=[],
                          message=f"Finding left out because its method could not be classified: {item}."))
    return flags


def r3_disagreement(predictions: list[Prediction], evidence: list[Evidence]) -> list[Flag]:
    """Disagreement is information: show it, never average it away."""
    flags = []
    calls = [p for p in predictions if is_ames(p.assay) and p.call in ("positive", "negative")]
    if len({p.call for p in calls}) > 1:
        flags.append(Flag(
            rule_id="R3", severity="conflict", refs=_refs(*calls),
            message="Predictions disagree: " + "; ".join(_describe(p) for p in calls) + ".",
        ))
    elif len(calls) >= 2:
        flags.append(Flag(
            rule_id="R3", severity="info", refs=_refs(*calls),
            message=f"All {len(calls)} predictions with a call agree: {calls[0].call}.",
        ))

    observed = [e for e in evidence if is_ames(e.assay) and e.call in ("positive", "negative")]
    observed_calls = {e.call for e in observed}
    if len(observed_calls) > 1:
        flags.append(Flag(
            rule_id="R3", severity="conflict", refs=_refs(*observed),
            message="Experimental Ames results disagree: "
                    + "; ".join(f"{e.source}: {e.call}" for e in observed) + ".",
        ))
    elif observed_calls:
        measured = observed_calls.pop()
        contradicted = [p for p in calls if p.call != measured]
        if contradicted:
            flags.append(Flag(
                rule_id="R3", severity="conflict", refs=_refs(*contradicted, *observed),
                message=f"Measured Ames results are {measured}, but "
                        + "; ".join(_describe(p) for p in contradicted) + ".",
            ))
    return flags


def r4_applicability(predictions: list[Prediction]) -> list[Flag]:
    """A model that declines to predict is telling us the substance is outside its domain."""
    return [
        Flag(rule_id="R4", severity="caution", refs=[p.tool_ref],
             message=f"{p.source} declined to predict: no model met its reliability threshold, "
                     "so the substance is outside their applicability domain.")
        for p in predictions
        if p.applicability == "outside_domain"
    ]


def r5_independence(evidence: list[Evidence], support: StructuralSupport | None) -> list[Flag]:
    """Agreement with data a model was trained on is expected, not validation."""
    flags = []
    trained = [e for e in evidence if "training set" in e.source.lower().replace("-", " ")]
    if trained:
        flags.append(Flag(
            rule_id="R5", severity="caution", refs=_refs(*trained),
            message="Part of the evidence is a model's own training-set value ("
                    + ", ".join(e.source for e in trained)
                    + "), so agreement with that model is not independent.",
        ))
    match = support.exact_match if support else None
    if match and match.split in ("train", "test"):
        flags.append(Flag(
            rule_id="R5", severity="caution", refs=[support.tool_ref],
            message=f"This substance is in the MutagenLou2023 {match.split} split (measured: "
                    f"{match.call}), which is drawn from Hansen and ISSSTY, the datasets "
                    "AmesFormer-Pro was trained on. Agreement between the prediction and this "
                    "result is expected, not independent validation.",
        ))
    elif match:
        flags.append(Flag(
            rule_id="R5", severity="info", refs=[support.tool_ref],
            message=f"This substance is in the MutagenLou2023 external validation split (measured: "
                    f"{match.call}), which is not drawn from AmesFormer-Pro's stated training sources.",
        ))
    return flags


def r6_structural_support(support: StructuralSupport | None, model: Prediction | None) -> list[Flag]:
    """How much measured data is structurally close to the query?"""
    if support is None or not support.neighbours:
        return []
    flags, ref = [], support.tool_ref
    best = support.neighbours[0]
    for n in support.neighbours:
        if n.similarity >= 0.999:
            flags.append(Flag(
                rule_id="R6", severity="info", refs=[ref],
                message=f"A measured compound ({n.smiles}) has fingerprint similarity "
                        f"{n.similarity:.2f} but a different InChIKey: the fingerprint cannot tell "
                        "them apart, so it is treated as a close analogue, not the same substance.",
            ))
    if best.similarity < SIMILARITY_THRESHOLD:
        flags.append(Flag(
            rule_id="R6", severity="caution", refs=[ref],
            message=f"Low structural support: the most similar measured compound has similarity "
                    f"{best.similarity:.2f} (threshold {SIMILARITY_THRESHOLD}). The prediction is "
                    "not anchored in measured analogues.",
        ))
        return flags

    close = [n for n in support.neighbours if n.similarity >= SIMILARITY_THRESHOLD]
    if model and model.call in ("positive", "negative"):
        agreeing = sum(n.call == model.call for n in close)
        severity = "conflict" if agreeing * 2 < len(close) else "info"
        flags.append(Flag(
            rule_id="R6", severity=severity, refs=[ref, model.tool_ref],
            message=f"{agreeing} of {len(close)} measured analogues (similarity ≥ "
                    f"{SIMILARITY_THRESHOLD}) are {model.call}, "
                    + ("consistent with" if severity == "info" else "contradicting")
                    + f" the {model.source} prediction.",
        ))
    return flags


def r7_not_retrieved(not_retrieved: list[NotRetrieved], evidence: list[Evidence]) -> list[Flag]:
    """Not retrieved is not the same as negative, or as never tested."""
    if not not_retrieved or any(is_ames(e.assay) for e in evidence):
        return []
    return [Flag(
        rule_id="R7", severity="caution", refs=_refs(*not_retrieved),
        message="No experimental Ames result was retrieved ("
                + ", ".join(n.source for n in not_retrieved)
                + "). This means not retrieved here, not 'not mutagenic' and not 'never tested'.",
    )]


def r8_nitrosamine(identity: Identity, ema_lookup, ref: str) -> tuple[RegulatoryContext, list[Flag]]:
    """N-nitroso compounds get regulatory context: cohort of concern, EMA limits."""
    mol = Chem.MolFromSmiles(identity.smiles or "")
    n_nitroso = bool(mol and mol.HasSubstructMatch(N_NITROSO))
    entry = ema_lookup(identity.inchikey) if n_nitroso else None
    context = RegulatoryContext(n_nitroso=n_nitroso, ema=entry, tool_ref=ref)
    if not n_nitroso:
        return context, []

    flags = [Flag(
        rule_id="R8", severity="info", refs=[ref],
        message="N-nitroso compound: part of the ICH M7 'cohort of concern'. Regulators recommend "
                "an enhanced Ames protocol for nitrosamines, as the standard protocol can "
                "under-detect them.",
    )]
    if entry:
        parts = [f"CPCA category {entry.cpca_category}"] if entry.cpca_category else []
        if entry.ai_ng_per_day is not None:
            parts.append(f"acceptable intake {entry.ai_ng_per_day:g} ng/day")
        flags.append(Flag(
            rule_id="R8", severity="info", refs=[ref],
            message=f"Listed by EMA as {entry.name}: " + ", ".join(parts)
                    + (f" ({entry.revision})." if entry.revision else "."),
        ))
    else:
        flags.append(Flag(rule_id="R8", severity="info", refs=[ref],
                          message="Not on the EMA nitrosamine acceptable-intake list."))
    return context, flags


def _duration(hours: float) -> str:
    if hours >= 24 * 365:
        return f"{hours / (24 * 365):.1f} years"
    if hours >= 48:
        return f"{hours / 24:.0f} days"
    return f"{hours:.3g} h"


def r9_toxicokinetics(dtxsid: str | None, ref_data, ref: str) -> tuple[TkContext, list[Flag]]:
    """Where the hazard question ends and the exposure question begins.

    TK context never changes the verdict; it shows how far animal results transfer to humans,
    and states plainly when httk has nothing for this substance.
    """
    source = f"httk {ref_data.httk_version} (CRAN)" if ref_data and ref_data.httk_version else "httk"
    if not dtxsid or ref_data is None:
        reason = ("httk is keyed on DTXSID and this substance is not in EPA DSSTox"
                  if not dtxsid else "reference data not installed")
        return TkContext(status="not_assessed", source=source, tool_ref=ref), [Flag(
            rule_id="R9", severity="info", refs=[ref], message=f"No toxicokinetic context: {reason}.")]

    params = ref_data.httk_params.get(dtxsid)
    half_lives = ref_data.httk_half_lives.get(dtxsid, [])
    context = TkContext(status="not_in_httk", source=source, tool_ref=ref, half_lives=half_lives,
                        **(params or {}))
    if half_lives:
        context.status = "half_lives"
        low = min(half_lives, key=lambda h: h.hours)
        high = max(half_lives, key=lambda h: h.hours)
        message = (f"Measured half-lives range from {_duration(low.hours)} ({low.species.lower()}, "
                   f"{low.sex.lower()}) to {_duration(high.hours)} ({high.species.lower()}, "
                   f"{high.sex.lower()}), a factor of about {high.hours / low.hours:,.0f}. Animal "
                   "results do not transfer to humans without a toxicokinetic model.")
    elif params and (params["clint_median"] is not None or params["fup_median"] is not None):
        context.status = "parameters_only"
        message = ("httk has human in vitro toxicokinetic parameters but no measured half-life; "
                   "no simulation is run here.")
    elif params:
        context.status = "no_human_parameters"
        message = (f"{source} lists this substance but has no human in vitro toxicokinetic "
                   "parameters, so no toxicokinetic context is available.")
    else:
        message = f"Not in {source}; no toxicokinetic context is available."
    return context, [Flag(rule_id="R9", severity="info", refs=[ref], message=message)]


def _weak_side_note(predictions: list[Prediction], support: StructuralSupport | None) -> str:
    """Describe, without resolving it, when one side of a prediction conflict is only
    low-confidence signals and measured analogues side with the other."""
    sides = {call: [p for p in predictions if is_ames(p.assay) and p.call == call]
             for call in ("positive", "negative")}
    if not (sides["positive"] and sides["negative"]):
        return ""
    weak = [c for c, ps in sides.items() if all((p.confidence or "").lower() == "low" for p in ps)]
    if len(weak) != 1:
        return ""
    weak_call = weak[0]
    other = "negative" if weak_call == "positive" else "positive"
    note = (f" The only {weak_call} signal is low-confidence ("
            + ", ".join(p.source for p in sides[weak_call]) + ")")
    close = [n for n in (support.neighbours if support else []) if n.similarity >= SIMILARITY_THRESHOLD]
    agreeing = sum(n.call == other for n in close)
    if close and agreeing * 2 > len(close):
        note += f", and {agreeing} of {len(close)} measured analogues are {other}"
    return note + ". This leans " + other + ", but the conflict is not resolved by ToxiTrace."


def summarise(
    flags: list[Flag],
    predictions: list[Prediction],
    evidence: list[Evidence],
    support: StructuralSupport | None = None,
) -> Summary:
    """The overall label follows from the flags; it is computed, never generated.

    Explanatory notes may describe how the signals lean, but never change the label: weighing
    sources is a scientific judgement left to the reader.
    """
    conflicts = [f for f in flags if f.severity == "conflict"]
    if conflicts:
        note = _weak_side_note(predictions, support)
        return Summary(
            label="conflicting",
            text="The sources disagree. " + " ".join(f.message for f in conflicts)
                 + (note or " Weigh the individual results before relying on any of them."),
            basis=sorted({f.rule_id for f in conflicts} | ({"R6"} if "analogues" in note else set())),
        )
    observed = {e.call for e in evidence if is_ames(e.assay) and e.call in ("positive", "negative")}
    if len(observed) == 1:
        call = observed.pop()
        caveat = any(f.rule_id == "R5" and f.severity == "caution" for f in flags)
        return Summary(
            label=f"supported_{call}",
            text=f"Measured Ames results are {call} and the predictions do not contradict them."
                 + (" The agreement is not independent: the models have seen this result." if caveat else ""),
            basis=["R2", "R3"] + (["R5"] if caveat else []),
        )
    if any(p.call in ("positive", "negative") for p in predictions):
        low_support = any(f.rule_id == "R6" and f.severity == "caution" for f in flags)
        best = support.neighbours[0].similarity if support and support.neighbours else None
        return Summary(
            label="prediction_only",
            text="Only predictions are available; no experimental Ames result was retrieved."
                 + (f" No measured analogue is structurally close (best similarity {best:.2f})."
                    if low_support and best is not None else "")
                 + " Treat the call as a hypothesis to test, not a finding.",
            basis=["R2", "R7"] + (["R6"] if low_support else []),
        )
    return Summary(
        label="insufficient",
        text="Neither a usable prediction nor experimental evidence was obtained.",
        basis=["R7"],
    )
