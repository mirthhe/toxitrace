# ToxiTrace design plan

**Status:** agreed design, 2026-10-22. This plan builds on [SPEC.md](../SPEC.md) and replaces its open discovery questions with what we actually found ([discovery-notes.md](discovery-notes.md), [science-notes.md](science-notes.md)).

## 1. Positioning

ToxIndex can already predict Ames mutagenicity, aggregate genotoxicity evidence, and reason about conflicts in its chat agent. ToxiTrace does not rebuild any of that. It adds two things:

1. **Cross-checking against original sources.** The ToxIndex outputs are compared with data fetched directly from the publishers (PubChem, MutagenLou2023, EMA, httk/CRAN), so the user can see where they agree and where they don't.
2. **Deterministic, tested weight-of-evidence rules.** The judgement calls that the ToxIndex chat agent makes in prose become code with unit tests. The LLM only *explains* a verdict the code has already computed.

**Research question:** *For this chemical, how much should a researcher trust the Ames prediction, and what do independent sources add or contradict?*

**Demo chemicals:**

| Chemical | What it shows |
|---|---|
| NDMA | Data-rich, but model and evidence agreement is circular (it's in the training data) |
| PFOA | No retrieved experimental data, conflicting predictions, Ames-negative neighbours, and a TK story |
| N-nitroso-varenicline | Not in the EPA registry: the prediction is the only signal, with no structural support, but a regulatory acceptable intake exists |

## 2. Sources

Per query, ToxiTrace makes **at most 3 ToxIndex calls**. Everything else is local.

| Source | Accessed via | Used for | Licence |
|---|---|---|---|
| ToxIndex `tox_chemical_identity` | API | DSSTox identity, SMILES, DTXSID | — |
| ToxIndex `toxjobs_predict` → `amesformer` | API | Prediction: P(Ames+), call | — |
| ToxIndex `tox_genotoxicity` | API | Evidence + VEGA/alert predictions, `gaps`, verdict | — |
| PubChem PUG REST | public HTTP | Independent identity check (InChIKey, CID) | public domain |
| MutagenLou2023 (HuggingFace) | downloaded at setup, local | Measured neighbours; "in training data" proxy | CC BY 4.0 |
| EMA nitrosamine AI list (xlsx) | downloaded at setup, local | CPCA category, acceptable intake | EMA legal notice |
| httk 2.7.4 data (CRAN) | downloaded at setup, local | TK context (half-lives, parameter availability) | GPL-3 |
| RDKit | local library | Parsing, InChIKey, fingerprints, substructure | BSD |

Reference data goes in `data/` (gitignored) via a setup script. **Nothing with an unclear licence is committed.**

## 3. Weight-of-evidence rules

Each rule produces a **flag**: `{rule_id, severity: info | caution | conflict, message, refs: [trace refs]}`. Each rule has unit tests built on the captured real responses.

| ID | Rule | Scientific reasoning | Test case |
|---|---|---|---|
| R1 | **Identity must agree.** The DSSTox InChIKey must equal the PubChem InChIKey. `total > 1` → ambiguous, so stop and ask the user. `total = 0` → flag "not in EPA registry", continue with the SMILES (predictions only). | Everything downstream depends on the right molecule. Not being in the registry is a finding, not an error. | NNV (not in DSSTox, in PubChem) |
| R2 | **Predicted ≠ observed.** Each finding is sorted by `method`: experimental/curated → Evidence, predicted → Predictions. A verdict with `basis: predicted` is shown as "prediction-based", never as a hazard conclusion. | Model output is not a measurement (SPEC FR-04). | PFOA verdict |
| R3 | **Sources disagree.** Compare AmesFormer's call, the VEGA consensus and the structural alerts; disagreement → `conflict` flag listing each one. Also compare the predictions with any experimental Ames results, and experimental results with each other. | Disagreement is information; averaging hides it. | PFOA: AmesFormer −, alert +, VEGA ? |
| R4 | **Outside the applicability domain.** VEGA "no model met the reliability threshold" → caution: "VEGA declines to predict". | A model refusing to predict is a signal about the chemical, not missing data. | PFOA |
| R5 | **Agreement isn't independent.** If the query's InChIKey is in MutagenLou2023 train/test (proxy for AmesFormer's Hansen/ISSSTY training data), or a finding says "training set" → caution: "prediction and evidence are not independent". | You can't validate a model on data it was trained on. | NDMA |
| R6 | **Structural support.** Find the k = 5 nearest measured neighbours (Morgan r2, Tanimoto) in MutagenLou2023 and show their labels, similarity and split. Max similarity below the threshold → caution "low structural support". Neighbour labels that mostly disagree with the prediction → conflict. Identity is always confirmed by InChIKey, never by similarity alone. | How much measured data is near this chemical? This is the core of the cross-check against independent data. | NNV (0.32); PFOA (neighbours negative, PFDA collision) |
| R7 | **Not retrieved ≠ absent.** List each source that was queried but returned nothing (`gaps`, 422, no neighbours) as "not retrieved from X". | SPEC principle; avoids "no evidence = safe". | PFOA, NNV |
| R8 | **Nitrosamine context.** An N-nitroso substructure → info: "ICH M7 cohort of concern; standard Ames may under-detect, enhanced Ames recommended". If the chemical is on the EMA list → show the CPCA category, AI and EMA revision. | A regulatory reality for this class; ties predictions to how they're used. | NDMA (96 ng/day), NNV (cat. 3, 400 ng/day) |
| R9 | **TK context.** If httk has a PFAS clearance entry, show half-lives by species and sex. If httk has the chemical but no human parameters, say "no TK context". If httk doesn't have the chemical, say "not in httk". | Marks where the hazard question ends and exposure begins; TK models have domains too. | PFOA (rat ♀ 2.8 h vs ♂ 236 h vs human ~2.5 y), NDMA (no params) |
| R10 | **Grounding.** Every number and source name in the LLM narrative must exist in the trace. Unmatched → the narrative is rejected and a template summary is used instead. | No fabricated values (SPEC FR-03). | Synthetic bad narrative |

**Overall summary** (computed, not generated): one of *Supported positive*, *Supported negative*, *Conflicting*, *Prediction only*, *Insufficient*. Each summary lists the flags that led to it. Exact mapping to be decided in implementation, with tests.

## 4. Pipeline

```text
input (name | CAS | SMILES)
  → R1 identity: ToxIndex DSSTox + PubChem + RDKit InChIKey
  → ToxIndex amesformer (SMILES)                          ┐
  → ToxIndex tox_genotoxicity (in DSSTox)                 │ in parallel
    or toxjobs_predict vega-mutagenicity (not in DSSTox)  ┘
  → local: neighbours (MutagenLou2023), EMA lookup, httk lookup
  → rules R2–R9 → flags + overall summary
  → LLM narrative (optional; falls back to a template) → R10 grounding check
  → AnalysisResult (Pydantic) → UI
```

Every external call and local lookup becomes a trace entry: `{ref, source, request, response (sanitised), status, duration, retrieved_at}`.

## 5. UI sections

1. **Identity:** names, IDs, registry status, and whether the sources agree.
2. **Summary:** the computed overall summary plus flags.
3. **Predictions:** AmesFormer, VEGA, alerts. Each is labelled "predicted".
4. **Evidence:** experimental/curated findings only, plus "not retrieved from …" lines.
5. **Structural support:** neighbour table with similarity, label and split.
6. **Regulatory context:** EMA/CPCA, only for nitrosamines.
7. **TK context:** httk half-lives or "no TK context".
8. **Interpretation:** the LLM narrative, marked as generated, with a grounding badge.
9. **Limitations.**
10. **Trace:** expandable, raw responses.

## 6. Scope and order (stop rules)

| Step | Exit criterion | Stop rule |
|---|---|---|
| 1. Setup script for reference data | `data/` filled reproducibly | — |
| 2. Adapters (ToxIndex, PubChem) + identity (R1) | Real calls work; tests with captured responses | — |
| 3. Rules R2–R8 + tests on the 3 demo chemicals | All rule tests pass | — |
| 4. API endpoint + minimal UI | Reviewer can run all 3 cases | — |
| 5. R9 TK context | PFOA panel shows half-lives | Not working in 45 min → future work |
| 6. LLM narrative + R10 | Grounded narrative or template fallback | Not working in 45 min → template only |
| 7. README, verification, limitations | FR-07 | — |

**Out of scope:** running AmesFormer on the neighbours (more API calls; possible stretch goal with caching), a CPCA calculator, metabolite PBK, Sysrev, user accounts.

## 7. Decisions (settled 2026-10-22)

- **R6 similarity threshold: 0.4** (Morgan r2, 2048 bits, Tanimoto). The raw similarity is always shown next to the label. Reasoning: around 0.4 is a common rule of thumb for meaningful shared structure with Morgan fingerprints; it is a heuristic, not a validated cut-off.
- **Narrative: Claude, with a template fallback.** The template is used when no `LLM_API_KEY` is set or when the R10 grounding check fails, so reviewers can run the full app without an LLM key.
- **Input: name, CAS and SMILES.** R1 resolves all three. If a name or CAS matches more than one substance, the user is asked to pick one.
