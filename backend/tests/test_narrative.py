"""R10 with the LLM mocked: the grounding check decides, the analysis never depends on the LLM."""

import pytest

from app import narrative
from app.config import settings
from app.narrative import _numbers, check_grounding
from app.schemas import AnalysisResult, Flag, Identity, Summary
from app.trace import Tracer

pytestmark = pytest.mark.anyio

PAYLOAD = {"verdict": {"label": "conflicting", "basis": ["R3"]}, "flags": [{"rule_id": "R3"}],
           "predictions": [{"probability": 0.000647790206, "detail": "score 0.45"}],
           "toxicokinetics": {"source": "httk 2.7.4 (CRAN)"}, "message": "a factor of about 7,880"}
TRACE_REFS = {"toxindex-2", "toxindex-3", "local-2"}


def test_numbers_skip_identifiers_versions_and_refs():
    text = "httk 2.7.4, factor 7,880, P = 0.0006 [toxindex-2], R6, CAS 335-67-1, v1.2, 1975, 4 of 4"
    assert _numbers(text) == ["7880", "0.0006", "4", "4"]


def test_grounded_text_passes_with_rounded_numbers_and_rule_ids():
    text = "Conflicting [R3]: AmesFormer P = 0.00065 [toxindex-2]; alert score 0.45 [toxindex-3]; factor 7,880."
    assert check_grounding(text, ["toxindex-2"], PAYLOAD, TRACE_REFS).status == "passed"


def test_invented_number_is_rejected():
    check = check_grounding("P = 0.12 [toxindex-2]", [], PAYLOAD, TRACE_REFS)
    assert check.status == "failed"
    assert "0.12" in check.detail


def test_unknown_reference_is_rejected():
    check = check_grounding("Measured positive [toxindex-9].", [], PAYLOAD, TRACE_REFS)
    assert check.status == "failed"
    assert "toxindex-9" in check.detail


def test_uncited_text_is_rejected():
    assert check_grounding("PFOA is fine.", [], PAYLOAD, TRACE_REFS).status == "failed"


def result_with_flags() -> AnalysisResult:
    return AnalysisResult(
        chemical_input="335-67-1", endpoint="ames_mutagenicity",
        identity=Identity(input="335-67-1", input_type="cas", status="resolved", name="PFOA"),
        summary=Summary(label="conflicting", text="The sources disagree.", basis=["R3"]),
        flags=[Flag(rule_id="R3", severity="conflict", message="Predictions disagree.", refs=["toxindex-2"])],
    )


def tracer_with_refs() -> Tracer:
    tracer = Tracer()
    tracer.record("toxindex", "toxjobs_predict", "ok")
    tracer.record("toxindex", "toxjobs_predict", "ok")  # toxindex-2
    return tracer


async def test_without_key_the_template_is_used(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "")
    interpretation, check = await narrative.narrate(result_with_flags(), Tracer())
    assert interpretation.source == "template"
    assert "The sources disagree." in interpretation.text
    assert check.status == "not_run"


async def test_accepted_llm_narrative(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "test-key")

    async def fake_llm(payload):
        return ({"text": "The predictions disagree [R3] [toxindex-2].", "refs": ["toxindex-2"]},
                {"requested_model": "m", "model": "m", "fallbacks": [], "stop_reason": "end_turn"})

    monkeypatch.setattr(narrative, "_call_llm", fake_llm)
    monkeypatch.setattr(narrative, "MODEL", "m")
    tracer = tracer_with_refs()
    interpretation, check = await narrative.narrate(result_with_flags(), tracer)

    assert interpretation.source == "llm"
    assert check.status == "passed"
    assert tracer.entries[-1].source == "anthropic"


async def test_hallucinated_number_falls_back_to_template(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "test-key")

    async def fake_llm(payload):
        return ({"text": "Mutagenic with 87% certainty [toxindex-2].", "refs": []},
                {"requested_model": "m", "model": "m", "fallbacks": [], "stop_reason": "end_turn"})

    monkeypatch.setattr(narrative, "_call_llm", fake_llm)
    interpretation, check = await narrative.narrate(result_with_flags(), tracer_with_refs())

    assert interpretation.source == "template"
    assert "rejected by the grounding check" in interpretation.note
    assert check.status == "failed" and "87" in check.detail


async def test_llm_failure_falls_back_to_template(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "test-key")

    async def failing_llm(payload):
        raise RuntimeError("model declined (bio)")

    monkeypatch.setattr(narrative, "_call_llm", failing_llm)
    tracer = Tracer()
    interpretation, check = await narrative.narrate(result_with_flags(), tracer)

    assert interpretation.source == "template"
    assert "LLM call failed" in interpretation.note
    assert tracer.entries[-1].status == "error"
    assert check.status == "not_run"


async def test_fallback_model_is_disclosed(monkeypatch):
    monkeypatch.setattr(settings, "llm_api_key", "test-key")

    async def fallback_llm(payload):
        return ({"text": "The predictions disagree [toxindex-2].", "refs": []},
                {"requested_model": narrative.MODEL, "model": "fallback-model", "fallbacks": [],
                 "stop_reason": "end_turn"})

    monkeypatch.setattr(narrative, "_call_llm", fallback_llm)
    interpretation, _ = await narrative.narrate(result_with_flags(), tracer_with_refs())
    assert interpretation.model == "fallback-model"
    assert f"Requested {narrative.MODEL}; served by fallback-model" in interpretation.note


def test_unicode_ranges_in_the_payload_are_found():
    payload = {"predictions": [{"detail": "4 of 4 models positive; AD index 0.77–0.79"}]}
    assert check_grounding("AD index up to 0.79 [toxindex-2].", [], payload, TRACE_REFS).status == "passed"


def test_overlong_text_is_rejected():
    text = "word " * 130 + "[toxindex-2]"
    check = check_grounding(text, [], PAYLOAD, TRACE_REFS)
    assert check.status == "failed" and "too long" in check.detail
