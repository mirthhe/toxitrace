# ToxiTrace — Scientific AI Research Assistant

> **Status: planned proof of concept.** This README describes the intended demo, not completed features. Update checkboxes, setup, examples, and validation results before submitting.

## Purpose

ToxiTrace explores a focused chemical-safety question by combining a **real toxicity-model response**, optional **scientific dataset evidence**, and a transparent **agent-assisted explanation** in a small, usable web interface.

Rather than claiming to automate regulatory assessment, the app helps users distinguish **model predictions**, **retrieved evidence**, and **interpretation**. It also exposes the tool calls and limitations behind an answer.

This is a time-boxed technical assignment (~one day), not production software.

## Research question

**For a selected chemical, what does a supported toxicity prediction tell us, and what evidence and limitations should a researcher inspect before relying on it?**

The specific chemical, input format, and endpoint(s) are **TBD until the real ToxIndex API schema has been inspected**.

## Planned demo

1. User enters a chemical identifier in a supported format.
2. A constrained agent/workflow selects a supported model tool and executes a real ToxIndex request.
3. Optional: retrieve compatible scientific records from a small BioBricks dataset.
4. Validate the returned data and generate a cautious, structured explanation.
5. Display four sections: **Predictions**, **Evidence**, **Limitations**, and **Tool activity / provenance**.

**Scientific principle:** “No evidence retrieved” does *not* mean “no evidence exists.” Model predictions are not experimental measurements.

## Scope

### Must have

- [ ] Small web UI with input, loading, result, and error states.
- [ ] At least one working **real ToxIndex API or MCP tool call**.
- [ ] Agentic or constrained tool-using workflow with visible execution trace.
- [ ] Structured results that distinguish predictions, evidence, and interpretation.
- [ ] At least one **executed verification**: check response schema/types and displayed values against raw model output; ideally compare against a compatible independent reference record.
- [ ] Honest limitations and documented testing.

### Nice to have

- [ ] One selected BioBricks dataset integration, only if mapping identifiers/endpoints is straightforward.
- [ ] Export report/trace as JSON or Markdown.
- [ ] A few repeatable example cases.
- [ ] Sysrev public-project data only if useful, accessible, and feasible.

### Out of scope

Production authentication, deployment, a general-purpose autonomous agent, extensive ETL, a systematic literature review, regulatory decisions, and claims of scientific validation based on one example.

## Proposed architecture

```text
React / TypeScript UI
         |
         v
Python / FastAPI backend
         |
         v
One controlled tool-using agent
         |                     |
         v                     v
ToxIndex adapter       BioBricks adapter (optional)
         +-----------+---------+
                     v
   Typed result, provenance, validation
                     |
                     v
        UI: results + execution trace
```

**Why this design?** A small, inspectable workflow is preferable to unnecessary multi-agent complexity. Direct API calls are acceptable; MCP is optional if it adds demonstrable value.

## Getting started

> **TODO after implementation:** Add the actual installation commands, version requirements, start commands, screenshot, and one working test query. The commands below are *not* a verified implementation.

1. Register at [ToxIndex Connect](https://platform.toxindex.com/connect) and create an API key.
2. Inspect the [ToxIndex OpenAPI schema](https://platform.toxindex.com/v1/openapi.json) or tool list. Confirm real paths, authentication, supported input identifiers, and response semantics.
3. Configure server-side secrets in a local `.env` file (never commit it).
4. Install frontend/backend dependencies and run the app using the commands added after implementation.

Proposed `.env.example` keys (subject to actual API requirements):

```dotenv
TOXINDEX_API_KEY=your-key-here
TOXINDEX_BASE_URL=https://platform.toxindex.com
# LLM_API_KEY=your-key-here  # only if needed
```

## Verification and limitations

Record actual tests and outcomes *after* running them:

| Test | Expected outcome | Actual result |
|---|---|---|
| Supported chemical | Real model data returned | Not run |
| Invalid chemical | Clear error; no invented results | Not run |
| API failure/rate limit | Clear error state | Not run |
| Grounding check | UI prediction matches raw API response | Not run |
| Evidence comparison (optional) | Same chemical and compatible endpoint | Not run |

**Anticipated limitations:** small sample size; uncertainty and applicability limits of models; potential mismatches between experimental endpoints and predictions; possible LLM interpretation errors; API/data availability. This demonstration is **not** validated for clinical, toxicological, or regulatory decisions.

## Design decisions

| Decision | Rationale |
|---|---|
| ToxIndex first | Prioritize an end-to-end real model call before expanding scope. |
| One constrained agent | Easier to audit, debug and document in one day. |
| Separate prediction and evidence | Avoid treating computed outputs as experimental observations. |
| Preserve source references and tool trace | Help users inspect the basis of a claim. |
| Keep BioBricks/Sysrev optional | Avoid spending the entire exercise on access and data wrangling. |

## How coding agents were used

> **TODO after development:** Specify tools used, tasks delegated (scaffolding, tests, UI, documentation), which outputs were personally reviewed, and what you verified independently. Do not present AI-generated interpretations as independently checked scientific findings.

## Proposed repository structure

```text
README.md
SPEC.md
backend/
  app/
    main.py
    agent.py
    schemas.py
    adapters/toxindex.py
    adapters/biobricks.py  # optional
  tests/
frontend/
.env.example
.gitignore
```

This tree is a proposal, not a claim that code exists yet.

## References

- [ToxIndex Connect](https://platform.toxindex.com/connect)
- [ToxIndex OpenAPI](https://platform.toxindex.com/v1/openapi.json)
- [BioBricks documentation](https://docs.biobricks.ai/)
- [Sysrev API help](https://help.sysrev.com/en/article/sysrev-api) — API key access is documented for Premium/Enterprise accounts.
