from app import rules
from app.schemas import (
    EmaEntry,
    Evidence,
    Identity,
    Neighbour,
    NotRetrieved,
    Prediction,
    StructuralSupport,
    UpstreamVerdict,
)

NNV_SMILES = "O=NN1CC2CC(C1)c1cc3nccnc3cc12"


def pred(source, call, **kw):
    return Prediction(source=source, call=call, tool_ref=kw.pop("tool_ref", "toxindex-2"), **kw)


def evid(source, call, assay="bacterial reverse mutation"):
    return Evidence(source=source, method="curated", call=call, assay=assay, tool_ref="toxindex-3")


def neighbour(sim, call, split="train", key="X"):
    return Neighbour(smiles="C", inchikey=key, call=call, split=split, similarity=sim)


def support(neighbours, exact=None):
    return StructuralSupport(dataset="d", fingerprint="f", neighbours=neighbours, exact_match=exact,
                             tool_ref="local-2")


def severities(flags):
    return [(f.rule_id, f.severity) for f in flags]


# R2
def test_r2_flags_prediction_based_upstream_verdict():
    upstream = UpstreamVerdict(conclusion="In vitro genotoxicant", basis="predicted", tool_ref="toxindex-3")
    assert severities(rules.r2_predicted_vs_observed([], [], upstream, [])) == [("R2", "caution")]


def test_r2_quiet_for_experimental_verdict():
    upstream = UpstreamVerdict(conclusion="Not classifiable", basis="experimental", tool_ref="toxindex-3")
    assert rules.r2_predicted_vs_observed([], [], upstream, []) == []


# R3
def test_r3_conflicting_predictions_pfoa_pattern():
    flags = rules.r3_disagreement(
        [pred("AmesFormer-Pro", "negative", probability=0.0006),
         pred("VEGA", "equivocal"),
         pred("Ames structural alerts", "positive", confidence="Low", assay="structural alerts")],
        [],
    )
    assert severities(flags) == [("R3", "conflict")]
    assert "AmesFormer-Pro: negative" in flags[0].message


def test_r3_agreement_is_info():
    flags = rules.r3_disagreement([pred("A", "positive"), pred("B", "positive")], [])
    assert severities(flags) == [("R3", "info")]


def test_r3_prediction_contradicted_by_measurement():
    flags = rules.r3_disagreement([pred("AmesFormer-Pro", "negative")], [evid("ISSSTY", "positive")])
    assert severities(flags) == [("R3", "conflict")]
    assert "Measured Ames results are positive" in flags[0].message


def test_r3_ignores_non_ames_evidence():
    flags = rules.r3_disagreement(
        [pred("AmesFormer-Pro", "positive")], [evid("ISSMIC", "negative", assay="in vivo micronucleus")])
    assert flags == []


# R4
def test_r4_outside_domain():
    flags = rules.r4_applicability([pred("VEGA mutagenicity models", "equivocal", applicability="outside_domain")])
    assert severities(flags) == [("R4", "caution")]


# R5
def test_r5_training_set_evidence_with_hyphen():
    flags = rules.r5_independence([evid("VEGA training-set experimental Ames value", "positive")], None)
    assert severities(flags) == [("R5", "caution")]


def test_r5_exact_match_in_training_split():
    flags = rules.r5_independence([], support([], exact=neighbour(1.0, "positive", split="train")))
    assert severities(flags) == [("R5", "caution")]


def test_r5_exact_match_in_validation_split_is_info():
    flags = rules.r5_independence([], support([], exact=neighbour(1.0, "negative", split="validation")))
    assert severities(flags) == [("R5", "info")]


# R6
def test_r6_low_structural_support_nnv_pattern():
    flags = rules.r6_structural_support(support([neighbour(0.32, "positive")]), pred("AmesFormer-Pro", "positive"))
    assert severities(flags) == [("R6", "caution")]
    assert "0.32" in flags[0].message


def test_r6_fingerprint_collision_is_named():
    flags = rules.r6_structural_support(
        support([neighbour(1.0, "negative", key="PFDA"), neighbour(0.47, "negative")]),
        pred("AmesFormer-Pro", "negative"),
    )
    assert ("R6", "info") in severities(flags)
    assert any("cannot tell them apart" in f.message for f in flags)


def test_r6_analogues_contradicting_prediction_is_conflict():
    flags = rules.r6_structural_support(
        support([neighbour(0.6, "negative"), neighbour(0.5, "negative"), neighbour(0.45, "positive")]),
        pred("AmesFormer-Pro", "positive"),
    )
    assert severities(flags) == [("R6", "conflict")]
    assert "1 of 3" in flags[0].message


# R7
def test_r7_not_retrieved_without_evidence():
    flags = rules.r7_not_retrieved([NotRetrieved(source="ISSSTY", reason="no record", tool_ref="toxindex-3")], [])
    assert severities(flags) == [("R7", "caution")]
    assert "not 'not mutagenic'" in flags[0].message


def test_r7_quiet_when_ames_evidence_exists():
    assert rules.r7_not_retrieved([NotRetrieved(source="Hansen", reason="no record")], [evid("ISSSTY", "positive")]) == []


# R8
def identity(smiles, key="KEY"):
    return Identity(input=smiles, input_type="smiles", status="resolved", smiles=smiles, inchikey=key)


def test_r8_nnv_on_ema_list():
    entry = EmaEntry(name="N-nitroso-varenicline", cpca_category="3", ai_ng_per_day=400, revision="Rev. 14")
    context, flags = rules.r8_nitrosamine(identity(NNV_SMILES), {"KEY": entry}.get, "local-3")

    assert context.n_nitroso is True
    assert context.ema.ai_ng_per_day == 400
    assert any("CPCA category 3, acceptable intake 400 ng/day" in f.message for f in flags)


def test_r8_nitrosamine_not_on_list():
    _, flags = rules.r8_nitrosamine(identity("CCN(CC)N=O"), lambda _k: None, "local-3")
    assert any("Not on the EMA" in f.message for f in flags)


def test_r8_silent_for_non_nitrosamine():
    context, flags = rules.r8_nitrosamine(identity("OC(=O)C(F)(F)F"), lambda _k: None, "local-3")
    assert context.n_nitroso is False and flags == []


def test_r8_nitro_group_is_not_n_nitroso():
    context, _ = rules.r8_nitrosamine(identity("c1ccccc1[N+](=O)[O-]"), lambda _k: None, "local-3")
    assert context.n_nitroso is False


# Summary
def test_summary_conflicting_wins():
    flags = rules.r3_disagreement([pred("A", "positive"), pred("B", "negative")], [])
    assert rules.summarise(flags, [], []).label == "conflicting"


def test_summary_supported_positive_with_independence_caveat():
    flags = rules.r5_independence([evid("VEGA training set value", "positive")], None)
    summary = rules.summarise(flags, [pred("A", "positive")], [evid("ISSSTY", "positive")])
    assert summary.label == "supported_positive"
    assert "not independent" in summary.text


def test_summary_prediction_only():
    assert rules.summarise([], [pred("A", "positive")], []).label == "prediction_only"


def test_summary_insufficient():
    assert rules.summarise([], [pred("VEGA", "equivocal")], []).label == "insufficient"


def test_summary_conflict_notes_weak_side_without_changing_label():
    preds = [pred("AmesFormer-Pro", "negative", probability=0.0006),
             pred("Ames structural alerts", "positive", confidence="Low", assay="structural alerts")]
    flags = rules.r3_disagreement(preds, [])
    analogues = support([neighbour(0.47, "negative"), neighbour(0.42, "negative"), neighbour(0.41, "negative")])

    summary = rules.summarise(flags, preds, [], analogues)

    assert summary.label == "conflicting"
    assert "only positive signal is low-confidence (Ames structural alerts)" in summary.text
    assert "3 of 3 measured analogues are negative" in summary.text
    assert "R6" in summary.basis


def test_summary_conflict_without_weak_side_has_no_lean():
    preds = [pred("A", "negative"), pred("B", "positive")]
    summary = rules.summarise(rules.r3_disagreement(preds, []), preds, [])
    assert "leans" not in summary.text


def test_summary_prediction_only_mentions_low_support():
    analogues = support([neighbour(0.32, "positive")])
    flags = rules.r6_structural_support(analogues, pred("AmesFormer-Pro", "positive"))
    summary = rules.summarise(flags, [pred("AmesFormer-Pro", "positive")], [], analogues)
    assert "best similarity 0.32" in summary.text
    assert "R6" in summary.basis
