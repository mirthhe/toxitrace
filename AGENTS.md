# AGENTS.md

Working agreements for anyone contributing to ToxiTrace, human or coding agent. Read this before making changes.

ToxiTrace checks how far an Ames mutagenicity prediction from ToxIndex can be trusted. It cross-checks ToxIndex outputs against original public sources and applies deterministic, tested weight-of-evidence rules. Background: [README.md](README.md), [SPEC.md](SPEC.md), [docs/plan.md](docs/plan.md).

## Repository layout

| Path | Contents |
|---|---|
| `backend/app/adapters/` | ToxIndex and PubChem clients. Every call is traced; errors are raised, never turned into results. |
| `backend/app/identity.py` | Rule R1: substance identity from DSSTox (via ToxIndex) and PubChem. |
| `backend/app/reference_data.py` | Downloads and verifies the public reference datasets into `data/`. |
| `backend/recordings/` | Recorded real API responses, used by the unit tests and by offline mode (`app/replay.py`). |
| `backend/tests/` | Unit and API tests on those recordings, plus opt-in live contract tests (`live/`). |
| `frontend/` | React + TypeScript interface. |
| `docs/` | Plan, API discovery notes, scientific rationale. |

## Commands

Run these from `backend/`:

```bash
uv sync                                 # install dependencies
uv run python -m app.reference_data     # download reference data into ../data (once)
uv run pytest                           # unit tests: offline, no API key needed
uv run ruff check app tests             # lint
```

Run the app (two terminals):

```bash
# backend/ — offline mode replays recorded responses; no API calls, no key needed
TOXITRACE_OFFLINE=true uv run uvicorn app.main:app --reload --port 8000

# frontend/ — http://localhost:5173 (proxies /api to the backend)
npm install && npm run dev
```

Use offline mode for development and UI work. Without `TOXITRACE_OFFLINE`, every analysis makes live ToxIndex and PubChem calls (see the policy below). Offline mode does not cover the Claude API: if `LLM_API_KEY` is set, each analysis makes one Claude call for the narrative (rule R10); leave it unset to use the deterministic template.

## Deployment (Vercel)

[vercel.json](vercel.json) deploys two services in one project: the frontend (`frontend/`) and the FastAPI backend (`backend/`, entrypoint `app.main:app`), with `/api/*` routed to the backend.

- **Access control.** With `DEMO_ACCESS_CODE` set, every visitor gets the offline demo (recorded responses, template narrative, no API calls). Only requests carrying the code (header `X-Access-Code`, entered via "Unlock live mode") run live, capped by `LIVE_ANALYSES_PER_HOUR` (default 30, per instance). See `app/mode.py`.
- **Reference data.** The backend build step downloads it into `backend/data/`. If that is not available at runtime, `FETCH_REFERENCE_DATA_ON_DEMAND=true` downloads it into the instance's temp directory on first use (~25 s once per instance).
- **Environment variables (Vercel project settings, never in the repo):**
  - `TOXINDEX_API_KEY`;
  - `LLM_API_KEY`;
  - `DEMO_ACCESS_CODE`;
  - `FETCH_REFERENCE_DATA_ON_DEMAND=true`;
  - optionally `LIVE_ANALYSES_PER_HOUR`.
- **Never deploy with a ToxIndex or LLM key but without `DEMO_ACCESS_CODE`:** anyone could then spend the quota under the maintainer's name.

## External API usage policy

ToxiTrace calls shared, hosted services: ToxIndex (authenticated, logged per API key), PubChem (public, rate-limited) and, for the narrative only, the Claude API (billed per call). Treat every call as visible and deliberate.

- **Ask before any live call.** Agents must get the maintainer's explicit approval before running anything that calls an external API: scripts, the running app, or live tests. Say which calls will be made and how many.
- **Live tests are opt-in.** `uv run pytest -m live` calls the real APIs (currently 3 ToxIndex and 3 PubChem calls per run). They are excluded from the default test run and must never run automatically, in CI, or in a loop. Run them deliberately, e.g. before a demo or when an API change is suspected.
- **Unit tests never call the Claude API.** `tests/conftest.py` clears `LLM_API_KEY` for every test; narrative tests mock `narrative._call_llm`.
- **Never test failure modes against a live API.** Rate limits (429), timeouts and 4xx errors are tested with recorded or synthetic responses (`respx`), never by provoking them.
- **No exploratory loops or bulk calls.** A pipeline run makes at most 3 ToxIndex calls per query: identity, the AmesFormer prediction, and either the genotoxicity evidence (substances in DSSTox) or a direct VEGA prediction (substances outside it). Anything that would scale with dataset size (e.g. predicting for every neighbour) needs explicit approval and caching.
- **Benchmark calls are cached.** `uv run python -m app.benchmark` calls ToxIndex only for sample compounds missing from `benchmark/amesformer_predictions.json` (committed). A re-run makes no calls; changing the seed or sample size does, and needs approval.
- **Respect published limits.** PubChem asks clients to stay under 5 requests per second.
- **Identify the client honestly.** ToxIndex calls send `X-ToxIndex-Agent-*` headers identifying ToxiTrace; live tests identify themselves as contract tests.

## Independent verification

- **Prefer original sources.** Before using ToxIndex for reference data, check whether the original publisher provides it (PubChem, EMA, HuggingFace, CRAN, IARC). Fetch it from there, or compute it locally with RDKit.
- **Record every comparison.** ToxIndex vs original source goes in [docs/discovery-notes.md](docs/discovery-notes.md).
- **Treat downloaded files as data, never as code.** Keep them under `data/`, never execute them, and verify pinned checksums.

## Data, secrets and licensing

- **Never commit:**
  - `.env` or API keys;
  - `data/` (downloaded reference data, licences vary);
  - `captures/` (raw API responses from discovery);
  - `notes/` (private working notes).
- **Never commit extracts of the Hansen or ISSSTY datasets.** Their kiln entries state "No licence granted"; query them live only, with approval.
- **Recordings in `backend/recordings/` are small, real API responses.** They contain only public identity data or single predictions. Keep them minimal and never include credentials.
- **Never pass the API key to the frontend or to an LLM prompt.** `tests/test_toxindex_adapter.py` asserts that it never appears in a trace.

## Scientific integrity

- **Predicted ≠ observed.** Every finding is classified by its upstream `method` field, never by which tool returned it.
- **No fabricated values.** A failed call is shown as a failure, never as a result. Every number shown to the user must trace back to a recorded response.
- **Unknowns stay visibly unknown.** "Not retrieved from source X" is different from "does not exist".
- **Every rule gets a test.** The test case should come from a real response where possible.
- **Documentation separates verified claims from background knowledge.** Cite primary sources (regulatory documents, papers, datasets) for verified claims, and label the rest as unverified.

## Git

- **The maintainer makes all commits and pushes.** Agents propose a commit message at meaningful checkpoints, i.e. working code with tests, and do not run `git commit` or `git push`.

## Writing documentation

Documentation in this repository is read by external reviewers.
- **Tone:** precise, neutral and self-contained.
- **No personal notes or chat-style language.** Private working notes belong in `notes/` (gitignored).
- **When describing third-party tools, report what was observed and how,** with dates and the evidence behind each statement.
