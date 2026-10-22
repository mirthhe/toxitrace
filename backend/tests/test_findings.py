from app.findings import from_amesformer, from_genotoxicity, from_vega, normalise_call
from tests.conftest import fixture


def test_amesformer_keeps_probability_and_threshold():
    pred = from_amesformer(fixture("toxindex/amesformer_pfoa.json"), "toxindex-2")

    assert pred.source == "AmesFormer-Pro"
    assert pred.call == "negative"
    assert pred.probability == fixture("toxindex/amesformer_pfoa.json")["output"]["probability"]
    assert pred.threshold == 0.5
    assert pred.applicability == "not_reported"


def test_pfoa_findings_are_all_predictions_despite_coming_from_the_evidence_tool():
    preds, evidence, gaps, upstream, unclassified = from_genotoxicity(
        fixture("toxindex/genotox_pfoa.json"), "toxindex-3")

    assert evidence == []
    assert {p.source for p in preds} == {"VEGA mutagenicity models", "Ames structural alerts"}
    vega = next(p for p in preds if p.source.startswith("VEGA"))
    assert vega.call == "equivocal"
    assert vega.applicability == "outside_domain"
    assert len(gaps) == 4
    assert upstream.basis == "predicted"
    assert unclassified == []


def test_ndma_findings_split_by_method():
    preds, evidence, gaps, _, _ = from_genotoxicity(fixture("toxindex/genotox_ndma.json"), "toxindex-3")

    assert {e.method for e in evidence} == {"experimental", "curated"}
    assert all(p.applicability != "outside_domain" for p in preds)
    vega = next(p for p in preds if p.source.startswith("VEGA"))
    assert vega.applicability == "in_domain"
    assert [g.source for g in gaps] == ["Hansen Ames benchmark", "EFSA regulatory in vitro genotoxicity studies"]


def test_unknown_method_is_left_out_not_guessed():
    body = {"findings": [{"source": "Mystery", "method": "inferred", "call": "Positive",
                          "assay": "bacterial reverse mutation"}]}

    preds, evidence, _, _, unclassified = from_genotoxicity(body, "toxindex-3")

    assert preds == [] and evidence == []
    assert "Mystery" in unclassified[0]


def test_normalise_call():
    assert normalise_call(True) == "positive"
    assert normalise_call("Negative") == "negative"
    assert normalise_call("Equivocal") == "equivocal"
    assert normalise_call("Data unavailable") == "unknown"


def test_vega_direct_keeps_version_and_ad_indices():
    pred = from_vega(fixture("toxindex/vega_n-nitroso-varenicline.json"), "toxindex-3")

    assert pred.source == "VEGA mutagenicity models (vega-mutagenicity-v1.2)"
    assert pred.call == "positive"
    assert pred.applicability == "in_domain"
    assert pred.confidence == "Moderate"
    assert pred.detail == "4 of 4 models positive; AD index 0.77–0.79"


def test_vega_mixed_calls_are_equivocal_and_low_reliability_is_outside_domain():
    body = {"output": {"model": "v", "predictions": [
        {"prediction": "Mutagenic", "assessment": "Mutagenic (LOW reliability)", "ad_index": 0.4},
        {"prediction": "NON-Mutagenic", "assessment": "NON-Mutagenic (LOW reliability)", "ad_index": 0.5},
    ]}}
    pred = from_vega(body, "toxindex-3")
    assert pred.call == "equivocal"
    assert pred.applicability == "outside_domain"
