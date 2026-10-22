"""Rule R10: a plain-language explanation of the computed result, checked against the trace.

The LLM only narrates. The verdict, flags and numbers are computed beforehand; the narrative
is accepted only if every number and every trace reference in it can be found in the data it
was given. Otherwise, or if no key is configured or the call fails, a deterministic template is
used. Either way the analysis never depends on the LLM.
"""

import json
import re
import time

import anthropic

from app import mode
from app.config import settings
from app.schemas import AnalysisResult, Check, Interpretation
from app.trace import Tracer

# claude-opus-5-5's safety classifiers consistently declined this toxicology content in testing
# (2026-10-22); every request was then served by claude-opus-5 via the server-side fallback.
# Requesting claude-opus-5 directly avoids a refused first attempt; the fallback stays enabled.
MODEL = "claude-opus-5"
MAX_WORDS = 120  # the prompt asks for 90; a little slack, but no essays

SYSTEM = """You explain a toxicology analysis to a researcher in plain language.

You receive a JSON payload that a deterministic pipeline has already computed: a verdict, flags
from named rules, predictions, experimental evidence, sources that returned nothing, and context.
Write at most 90 words, in one or two short paragraphs, that help the researcher understand what
the result means and how far to trust it. Write for a scientist, not a programmer: describe the
verdict in plain words and never repeat internal labels such as "supported_positive".

Rules:
- Use only facts and numbers present in the payload. Do not add knowledge from elsewhere.
- Keep the verdict exactly as given; do not soften, strengthen or re-label it.
- Keep predictions and experimental results clearly apart.
- End each sentence that states a fact with the trace reference(s) it rests on, in square brackets, e.g. [toxindex-2].
- "Not retrieved" means not found by this analysis, never "not mutagenic" or "never tested".
- Mention the most important limitation or caution.
- No regulatory advice."""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "text": {"type": "string", "description": "The explanation, with [trace-ref] citations."},
        "refs": {"type": "array", "items": {"type": "string"}, "description": "All trace refs cited."},
    },
    "required": ["text", "refs"],
    "additionalProperties": False,
}

REF_TOKEN = re.compile(r"\b[a-z]+-\d+\b")
# Identifiers that contain digits but are not quantities.
IDENTIFIER = re.compile(r"\bR\d+\b|\b\d{2,7}-\d{2}-\d\b|DTXSID\d+|\b[A-Z]{14}-[A-Z]{10}-[A-Z]\b")
NUMBER = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)*")


def build_payload(result: AnalysisResult) -> dict:
    """The facts the narrative may use: computed results only, no raw upstream responses."""
    identity = result.identity
    return {
        "substance": {"name": identity.name, "cas": identity.cas, "in_epa_dsstox": identity.in_dsstox},
        "verdict": result.summary.model_dump() if result.summary else None,
        "flags": [f.model_dump() for f in result.flags],
        "predictions": [p.model_dump(exclude={"assay"}) for p in result.predictions],
        "experimental_evidence": [e.model_dump() for e in result.evidence],
        "not_retrieved": [n.model_dump() for n in result.not_retrieved],
        "regulatory": result.regulatory.model_dump() if result.regulatory else None,
        "toxicokinetics": result.toxicokinetics.model_dump(exclude={"half_lives"})
        if result.toxicokinetics else None,
        "limitations": result.limitations,
    }


def template(result: AnalysisResult) -> str:
    """Deterministic explanation used when no LLM narrative is available or accepted:
    the summary, then the two most important cautions it does not already state."""
    summary = result.summary.text if result.summary else ""
    parts = [summary] if summary else []
    important = [f for f in result.flags if f.severity in ("conflict", "caution")]
    important.sort(key=lambda f: f.severity != "conflict")
    for flag in [f for f in important if f.message not in summary][:2]:
        refs = f" [{', '.join(flag.refs)}]" if flag.refs else ""
        parts.append(f"{flag.message}{refs}")
    return "\n\n".join(parts)


def _numbers(text: str) -> list[str]:
    """Quantities in a text, without identifiers, years or version strings such as 2.7.4."""
    cleaned = REF_TOKEN.sub(" ", IDENTIFIER.sub(" ", text))
    found = []
    for raw in NUMBER.findall(cleaned):
        raw = raw.rstrip(",")
        token = raw.replace(",", "")
        is_year = "," not in raw and re.fullmatch(r"\d{4}", token) and 1900 <= int(token) <= 2100
        if token.count(".") > 1 or is_year:
            continue
        found.append(token)
    return found


def _grounded_number(token: str, allowed: list[float]) -> bool:
    """A number counts as grounded if some payload number rounds to it at the shown precision."""
    value = float(token)
    decimals = len(token.split(".")[1]) if "." in token else 0
    tolerance = 0.5 * 10 ** -decimals
    return any(abs(value - a) <= tolerance + 1e-12 for a in allowed)


def check_grounding(text: str, refs: list[str], payload: dict, trace_refs: set[str]) -> Check:
    """R10: every cited ref must exist in the trace and every number must come from the payload."""
    payload_text = json.dumps(payload, ensure_ascii=False)
    # Rule ids (e.g. R3) are legitimate citations too, if the analysis actually contains them.
    rule_ids = set(re.findall(r"\bR\d+\b", payload_text))
    bracketed = {r.strip() for group in re.findall(r"\[([^\]]+)\]", text) for r in group.split(",")}
    cited = {r for r in bracketed | set(refs) if REF_TOKEN.fullmatch(r) or re.fullmatch(r"R\d+", r)}
    unknown_refs = sorted(cited - trace_refs - rule_ids)
    allowed = [float(n) for n in _numbers(payload_text)]
    ungrounded = sorted({n for n in _numbers(text) if not _grounded_number(n, allowed)})
    words = len(text.split())

    problems = []
    if not cited:
        problems.append("no trace references cited")
    if unknown_refs:
        problems.append(f"cites refs not in the trace: {', '.join(unknown_refs)}")
    if ungrounded:
        problems.append(f"numbers not found in the analysis: {', '.join(ungrounded)}")
    if words > MAX_WORDS:
        problems.append(f"too long ({words} words)")
    return Check(
        name="R10 grounding",
        status="failed" if problems else "passed",
        detail="; ".join(problems) if problems else
        f"{len(cited)} trace refs and {len(_numbers(text))} numbers checked against the analysis",
    )


async def _call_llm(payload: dict) -> tuple[dict, dict]:
    """One Claude call with structured output. Returns (parsed output, usage/metadata)."""
    client = anthropic.AsyncAnthropic(api_key=settings.llm_api_key, timeout=45.0, max_retries=1)
    response = await client.beta.messages.create(
        model=MODEL,
        max_tokens=4000,
        system=SYSTEM,
        messages=[{"role": "user", "content": json.dumps(payload, indent=1, ensure_ascii=False)}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    fallbacks = [
        {"from": b.from_.model, "to": b.to.model}
        for b in response.content if b.type == "fallback"
    ]
    meta = {
        "requested_model": MODEL,
        "model": response.model,
        "fallbacks": fallbacks,
        "stop_reason": response.stop_reason,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "request_id": getattr(response, "_request_id", None),
    }
    if response.stop_reason == "refusal":
        raise RuntimeError(f"model declined ({getattr(response.stop_details, 'category', None)})")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("response hit max_tokens")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text), meta


async def narrate(result: AnalysisResult, tracer: Tracer) -> tuple[Interpretation, Check]:
    """Return an accepted LLM narrative, or the template with the reason it was used."""
    fallback = Interpretation(text=template(result), source="template")
    if not mode.llm_enabled():
        return fallback.model_copy(update={"note": "Public demo mode: no LLM call is made."}), Check(
            name="R10 grounding", status="not_run", detail="template used: public demo mode")
    if not settings.llm_api_key:
        return fallback.model_copy(update={"note": "No LLM key configured."}), Check(
            name="R10 grounding", status="not_run", detail="template used: no LLM key configured")

    payload = build_payload(result)
    start = time.perf_counter()
    try:
        output, meta = await _call_llm(payload)
    except (anthropic.APIError, RuntimeError, json.JSONDecodeError, StopIteration) as exc:
        ref = tracer.record("anthropic", f"messages ({MODEL})", "error", {"payload": payload},
                            error=str(exc), duration_ms=round((time.perf_counter() - start) * 1000))
        return fallback.model_copy(update={"note": f"LLM call failed, template used [{ref}]."}), Check(
            name="R10 grounding", status="not_run", detail=f"template used: LLM call failed ({exc})")

    ref = tracer.record("anthropic", f"messages ({meta['model']})", "ok", {"payload": payload},
                        {"output": output, **meta}, duration_ms=round((time.perf_counter() - start) * 1000))
    trace_refs = {e.ref for e in tracer.entries}
    try:
        check = check_grounding(output.get("text", ""), output.get("refs", []), payload, trace_refs)
    except Exception as exc:  # noqa: BLE001 - the check reads model output and must never break the analysis
        check = Check(name="R10 grounding", status="failed", detail=f"check could not run: {exc}")
    if check.status == "failed":
        return fallback.model_copy(update={"note": f"LLM narrative rejected by the grounding check [{ref}]."}), check
    note = (f"Requested {MODEL}; served by {meta['model']} through Anthropic's server-side fallback."
            if meta["model"] != MODEL else None)
    return Interpretation(text=output["text"], source="llm", model=meta["model"], tool_ref=ref, note=note), check
