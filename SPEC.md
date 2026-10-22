# ToxiTrace — Spec-Driven Development Plan

**Status:** Completed 2026-10-22. This document is the original plan, kept as written; the evaluation table (§7) and the checklist (§10) have been updated with the outcomes. Full verification results are recorded in the [README](README.md#verification), and the design as built is in [docs/plan.md](docs/plan.md).  
**Time budget:** approximately one working day  
**Audience:** developer and Insilica reviewers  
**Scope:** working vertical slice, with visible scientific provenance and limitations.

## 1. Problem and outcome

Scientific users investigating chemical safety need more than a model score. They need to see what was predicted, which underlying tools were used, whether any supporting evidence was retrieved, and which conclusions remain uncertain.

**User story:** As a researcher, I want to query a selected chemical, inspect a relevant toxicity prediction and its provenance, and understand the limits of the result so I can decide what to investigate next.

**Success:** A reviewer can run a real analysis using the app and trace every displayed model result back to an actual API response.

**Non-goals:** regulatory-grade assessment, broad evaluation of all models, general-purpose chat, user accounts, production deployment, large dataset ingestion, or a full Sysrev integration.

## 2. Discovery gate (before choosing endpoints)

Timebox: 45–60 minutes.

1. Create a ToxIndex API key using the supplied instructions.
2. Inspect the **actual** OpenAPI schema or MCP tool list.
3. Choose **one** working model endpoint, input type, and sample chemical.
4. Make a real call; note response schema, units, score semantics, model identifier, error conditions, and available provenance.
5. Choose a specific question the endpoint can answer without overstating results.

**Do not invent endpoint paths or schema fields.** Confirm all details against the authenticated service. Outcome: [docs/discovery-notes.md](docs/discovery-notes.md).

Optional BioBricks feasibility gate: locate a small compatible dataset and inspect its schema; only implement if chemical identity and endpoint matching are defensible. The BioBricks quickstart describes configuration with a token and installable datasets backed by Parquet files.

Sysrev: not part of the MVP. ToxIndex exposes Sysrev endpoints (`/v1/sysrev/*`); these were not explored in this project.

## 3. Functional requirements and acceptance tests

### FR-01: Supported input
- User can enter one verified chemical identifier format.
- Empty and unsupported inputs display helpful feedback.
- **Pass when:** a known sample query can be submitted without ambiguity.

### FR-02: Real model integration
- Server calls at least one real ToxIndex model/tool with a secret kept server-side.
- Raw response or a sanitized representation can be inspected.
- Errors and rate limits never produce fabricated predictions.
- **Pass when:** a successful API response appears in the tool trace and in the structured result.

### FR-03: Agentic workflow
- A single constrained agent uses allowlisted read-only tools to select/retrieve/summarize relevant data.
- All model claims are grounded in captured tool responses.
- Output is validated against typed schemas before UI rendering.
- **Pass when:** at least one real tool call is visible and any invented/unsupported source references are rejected or flagged.

### FR-04: Scientific presentation
- Predictions, experimental evidence (if available), narrative interpretation, and limitations have separate UI sections.
- Clearly label when evidence was **not retrieved**, as opposed to absent in the world.
- **Pass when:** a reviewer can distinguish the nature and origin of each claim.

### FR-05: Results verification
- Verify response structure/types; compare displayed prediction values to raw tool output.
- Preferably compare with *independent evidence for the same chemical and compatible endpoint* if feasible.
- **Pass when:** at least one actual test and outcome are recorded in README, with uncertainty honestly described.
- **Important:** A technical schema check is not proof of scientific predictive validity.

### FR-06: Usable interface
- Input form, running/complete/error states, predictions/evidence/limitations, expandable tool trace.
- **Pass when:** a new reviewer can complete a sample analysis without using a CLI.

### FR-07: Submission
- README documents objective, setup, design decisions, agent use, tests, and limitations.
- No secrets or confidential outputs in repository.
- **Pass when:** a fresh setup follows documented instructions and the reviewer understands the scope.

## 4. Agent workflow

```text
User chemical identifier
  -> validate format
  -> choose allowlisted endpoint
  -> call ToxIndex
  -> optional BioBricks lookup for compatible evidence
  -> validate/normalize returned data
  -> agent drafts grounded, cautious explanation
  -> validate source references against tool outputs
  -> UI renders predictions / evidence / limitations / execution trace
```

**Agent boundaries:** No fabricated citations, made-up measurements or unsupported risk classifications. No arbitrary web/code execution. Never pass API keys to the frontend or LLM prompt. Unknowns must remain visibly unknown.

## 5. Proposed application data contract

**This is our own schema, NOT a documented ToxIndex API response.** Revise after examining the API.

```json
{
  "chemical_input": "example-identifier",
  "endpoint": "verified-endpoint-id",
  "predictions": [
    {
      "source": "toxindex",
      "model_id": "actual-model-identifier",
      "raw_value": "actual-upstream-value",
      "unit": null,
      "tool_ref": "tool-call-1"
    }
  ],
  "evidence": [],
  "interpretation": "Cautious explanation grounded in tool output",
  "limitations": ["No compatible experimental evidence retrieved in this demo."],
  "checks": [
    {"name": "schema_validation", "status": "not_run"},
    {"name": "value_grounding", "status": "not_run"}
  ],
  "trace": [
    {"ref": "tool-call-1", "tool": "toxindex", "status": "example"}
  ]
}
```

Model output might be categorical, probabilistic or numeric; use actual semantics and avoid silently converting between them. Preserve source references available in upstream data.

## 6. Proposed technical structure

- **Frontend:** React + TypeScript, minimal responsive interface and expandable tool activity.
- **Backend:** Python + FastAPI, Pydantic response validation, explicit HTTP timeouts/error handling.
- **Agent:** one constrained tool-using LLM or a deterministic tool pipeline with an LLM explanation step. Multi-agent frameworks not required.
- **Adapters:** ToxIndex mandatory; BioBricks optional. Sysrev only if useful and feasible.
- **Storage:** none necessary for MVP; sanitize trace, keep secrets on server.
- **Testing:** unit tests for normalized responses and failure cases, plus one documented real end-to-end call.

Alternative framework choices are acceptable when they reduce complexity. Note the choice in the decision log.

## 7. Evaluation plan

| Scenario | Expected behavior | Execution status |
|---|---|---|
| Valid chemical | API prediction rendered | ✅ Passed: all three demo chemicals, offline and live ([README](README.md#verification)) |
| Empty chemical input | Validation error | ✅ Passed |
| Invalid/unsupported identifier | Error, not a fabricated result | ✅ Passed: invalid CAS rejected before lookup; unknown names return "not found" |
| API timeout or 429 | Clear failure state | ✅ Passed (mocked responses; never provoked against the live API) |
| Grounding check | UI values match raw API response | ✅ Passed: values asserted against recorded responses; LLM narrative checked against the trace (R10) |
| BioBricks evidence match (optional) | Same chemical and compatible endpoint | ➖ Not built as a separate integration: datasets reached via ToxIndex kiln and the MutagenLou2023 original ([decision](docs/discovery-notes.md#biobricks-decision)) |
| Fresh setup | Commands work as written | ✅ Passed: fresh clone from GitHub, 2026-10-22 |

If no compatible independent experimental evidence can be found, state that **software behavior was checked but scientific predictive accuracy was not independently assessed**.

## 8. Implementation plan and stop rules

| Phase | Budget | Exit criterion |
|---|---:|---|
| Discover API and sample data | 1 hour | Real tool response and known input semantics |
| Backend vertical slice | 1.5 hours | Input -> real normalized prediction |
| Controlled agent + grounding | 1.5 hours | Structured interpretation and trace |
| Frontend | 1.5 hours | Working end-to-end researcher interface |
| Testing, README, cleanup | 1.5 hours | Tested happy/failure cases, clear docs |

**Stop rule:** If a BioBricks/Sysrev integration is not yielding a working path within 45 minutes, drop it from the MVP and explain the trade-off in the README. Prioritize a reliable ToxIndex vertical slice over the number of connected products.

## 9. Technical decision log

| Decision | Reason | Update after implementation |
|---|---|---|
| One controlled agent | Auditable and feasible in one day | Confirm actual design |
| ToxIndex integration first | Core to the assignment | Record endpoint / model |
| Direct API vs MCP | Choose simpler effective tool boundary | Explain selection |
| Optional BioBricks | Avoid spending all time on data engineering | State included/excluded |
| Separate predicted and observed evidence | Scientific transparency | Check final UI |

## 10. Completion checklist

- [x] A real ToxIndex call works.
- [x] User can trigger it in the app.
- [x] Agent tool use is visible.
- [x] Results identify which information is predictive vs experimentally observed.
- [x] At least one verification was actually performed and documented.
- [x] One failure case is tested.
- [x] README contains **tested** setup commands and explains coding agent involvement.
- [x] Limitations are honest; no regulatory claims.
- [x] No credentials are committed.
- [x] Repository can be shared with the reviewers.

## 11. Documentation references

- ToxIndex API: https://platform.toxindex.com/v1/openapi.json
- ToxIndex account: https://platform.toxindex.com/connect
- BioBricks: https://docs.biobricks.ai/
- Sysrev: https://help.sysrev.com/en/article/sysrev-api
