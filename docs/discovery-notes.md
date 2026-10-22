# API discovery notes (SPEC §2)

What the ToxIndex API and the independent sources actually returned during discovery (21–22 October 2026). Every statement here is based on a recorded response or a downloaded original file; nothing is inferred from documentation alone unless stated.

## ToxIndex

Source: `GET https://platform.toxindex.com/v1/openapi.json` (2026-10-21), ToxIndex API v1.

- **Access method:** REST at `https://platform.toxindex.com/v1`. The API keys page also lists `/mcp` and `/a2a` endpoints.
- **Auth scheme:** `Authorization: Bearer <key>` (OpenAPI `securitySchemes.bearer`). Keys are created at `/settings/keys`.
- **API surfaces:**
  - `GET /tools`, `POST /tools/{name}`: the agent tool catalog. Each tool has a `name`, `description` and a JSON Schema `input_schema`. The response to an execute call is text, which may itself be JSON depending on the tool. Documented errors are `404` and `422`, both with body `{"error": string}`.
  - `GET /toxjobs/tool[?q=]`, `GET /toxjobs/tool/{name}`: "live analysis tools served by ready rigs". These carry both `input_schema` and `output_schema`, serialised as strings. Returns `501` when unavailable.
  - `/kiln/*`: curated reference datasets ("bricks"), full-text document search, and read-only SPARQL. **This looks like BioBricks data reachable through the same API.**
  - `/sysrev/*`: Sysrev projects, documents, reviews and exports.
  - `/agent/*`: ToxIndex's own conversations, plus `GET /agent/{conversation}/tool/{toolCallId}` for tool-call provenance.
  - `GET /whoami`: identity check for the credential.
- **Agent attribution headers:** `POST /tools/{name}` accepts the `X-ToxIndex-Agent-Name`, `-Model`, `-Harness` and `-Host` headers. The `sysrev_*` tools require them. ToxiTrace sends them so its calls are identifiable in ToxIndex's logs.
- **Not in the spec:** rate limits (no 429 is documented) and timeouts.

### Tool catalogs (`GET /tools`, `GET /toxjobs/tool`, 2026-10-21)

- **`/tools`: 43 agent tools.** The relevant ones:
  - `toxjobs_predict {tool, input | smiles}` runs any toxjobs model.
  - `tox_chemical_identity {identifier}` resolves a name, CAS, DTXSID, InChIKey or SMILES against EPA DSSTox. It returns up to 5 candidates (dtxsid, cas, inchikey, preferred name, formula, QSAR-ready SMILES) plus a `total`. `total > 1` means the identifier is ambiguous and `0` means no match.
  - `tox_genotoxicity`, `tox_carcinogenicity`, `tox_acute_toxicity`, etc. return evidence-backed GHS verdicts. `tox_genotoxicity` separates the bacterial, in vitro mammalian and in vivo assay results, and reports `findings`, `conflicts` and `gaps`.
  - `kiln_*` and `document_*` cover datasets and documents. `sysrev_*` covers reviews; those tools are write-capable, so we don't use them.
- **`/toxjobs/tool`: 175 models.** Most take `smiles`. The `output_schema` field is **empty** for the models checked (amesformer, vega-mutagenicity, ames-structural-alerts), so the response shape has to come from a real call.

### Candidate pipeline: Ames mutagenicity

- **Identity:** `tox_chemical_identity` turns a name or CAS into a DTXSID and SMILES, and lets us reject ambiguous input.
- **Prediction:** `toxjobs_predict` with `amesformer`. Per its description, this returns P(Ames-positive) and a call at a 0.5 threshold.
- **Evidence:** `tox_genotoxicity` returns curated experimental Ames results (ISSSTY, Hansen, EFSA) with each finding labelled by assay.
- **Caveat:** AmesFormer was trained on Hansen, ISSSTY and EURL data, which overlaps with the evidence sources. Agreement on a well-known chemical is therefore **not** an independent validation.

### First real calls (2026-10-21)

Raw responses were recorded locally; trimmed copies used by the unit tests are in `backend/tests/fixtures/toxindex/`. All calls were sent through `POST /v1/tools/{name}` with the `X-ToxIndex-Agent-*` headers. Each took about 1 second or less.

**`toxjobs_predict {tool: "amesformer", smiles}`.** Response shape:
```json
{"output": {"model": "AmesFormer-Pro", "mutagenic": true, "probability": 0.9977, "smiles": "CN(C)N=O", "threshold": 0.5}}
```
- `probability` is P(Ames-positive), a value from 0 to 1 with no unit.
- `mutagenic` is `probability >= threshold`.
- `smiles` is the model's canonicalised form of the input, which may differ textually from what we sent.

**`tox_genotoxicity {identifier}`.** Response shape:
- top-level fields: `chemical` (resolved identity), `verdict {conclusion, basis, confidence[, mechanism]}`, `bacterial_reverse_mutation {call, basis, findings[]}`, `in_vitro_mammalian`, `in_vivo`, `findings[]`, `conflicts[]` and `gaps[]` (names of sources that returned nothing);
- each finding has `source`, `method` (`experimental` | `curated` | `predicted`), `call`, `assay`, `system`, `detail` and, optionally, `confidence`;
- **the "evidence" tool mixes predictions into its findings.** The VEGA models and structural alerts come back as `method: "predicted"`. ToxiTrace must sort findings into Predictions vs Evidence **by `method`, not by which tool returned them**;
- an identifier not found in DSSTox returns **422** `{"error": "no substance in the EPA DSSTox registry matches ..."}`.

| Chemical | AmesFormer | Experimental Ames evidence | Other |
|---|---|---|---|
| NDMA | P = 0.998, mutagenic | ISSSTY curated: Positive; VEGA training set: Positive | VEGA 4/4 positive; alerts positive; in vivo micronucleus **Equivocal**; verdict "Not classifiable" (High) |
| PFOA | P = 0.0006, non-mutagenic | **none retrieved** (`gaps`: ISSSTY, Hansen, EFSA, ISSMIC) | VEGA: no model reliable (4 ran); 1 structural alert positive (score 0.45, Low); verdict "In vitro genotoxicant", basis predicted, confidence Low; `conflicts: []` |
| N-nitroso-varenicline | P = 0.951, mutagenic | not available: 422, not in DSSTox | — |

- **Chosen endpoint:** Ames mutagenicity. The prediction comes from AmesFormer-Pro via `toxjobs_predict`; identity from `tox_chemical_identity`; evidence from `tox_genotoxicity`.
- **Input type:** a CAS number, name or SMILES. It's resolved via DSSTox; when that finds nothing, a SMILES string can be used directly for the prediction only.
- **Rate limits:** none observed and none documented.

### VEGA called directly (2026-10-22)

`toxjobs_predict {tool: "vega-mutagenicity", smiles}` for N-nitroso-varenicline (1 call, recorded in `backend/recordings/toxindex/`). Response shape:
- `output.model`: a **versioned** model id (`vega-mutagenicity-v1.2`). AmesFormer reports no version.
- `output.predictions[]`: one entry per model (caesar, iss, sarpy, knn) with `prediction`, `assessment` (e.g. "Mutagenic (MODERATE reliability)"), `ad_index` and `reliability`.
- Result: all 4 models "Mutagenic", moderate reliability, AD index 0.77–0.79.
- **Compared with `tox_genotoxicity`:** its aggregated VEGA finding reduces this to "4 of 4 models reliable", without the version or the AD indices. ToxiTrace calls VEGA directly only for substances outside DSSTox, where `tox_genotoxicity` cannot be used.

### Kiln datasets and httk (2026-10-22)

`kiln_list_bricks` returns 770 bricks. The relevant ones:

| Brick | Contents | License |
|---|---|---|
| `mutagenlou2023` | 10,045 compounds: 8,576 from Hansen + ISSSTY, **plus 1,469 external validation compounds from DrugBank and DGM/NIHS**. Columns: `id, is_mutagen (Bool), molecular_weight, row_key, smiles, split` | CC BY 4.0 |
| `hansen-ames` | 6,512 compounds, binary call, SMILES, CAS, source database (VITIC, CCRIS, EPA, GENETOX) | **No licence granted** |
| `iss-ames-mutagenicity` | ISSSTY, 7,367 chemicals, results per strain ± S9 | **No licence granted** |
| `ema-nitrosamine-ai` | 252 N-nitroso compounds with EMA acceptable intakes (ng/day) and source drug | EMA legal notice |
| `ccris`, `iss-micronucleus`, `efsa-pesticide-genotoxicity`, `echa-mamtkdb`, `oecd-pfas-list`, `pfas-tox` | possibly useful later | — |

- **Independence (rules R5/R6):** AmesFormer's stated training sources are Hansen, ISSSTY and EURL. The MutagenLou2023 external validation split (DrugBank, DGM/NIHS) is a candidate **independent** benchmark. Overlap still needs checking by structure (InChIKey), since DrugBank compounds can also appear in Hansen or ISSSTY.
- **Licensing:** Hansen and ISSSTY have no licence granted. Extracts of them are never committed to this repository. MutagenLou2023 (CC BY 4.0) may be redistributed with attribution.

**httk via `toxjobs_predict {tool: "httk", input: {chemicals: <CAS>}}`:**
- NDMA (62-75-9) and PFOA (335-67-1) both returned HTTP 200 with `{"output": [{"available": false, "error": "Chemical name not found ..."}]}`.
- **A 200 response can still contain a per-chemical failure.** The adapter must check `available`.
- The error says "name not found", so the CAS may have been interpreted as a name. Not yet retried by name or DTXSID.

## Independent verification against original sources (2026-10-22)

The files were downloaded directly from each publisher (reproducible with `uv run python -m app.reference_data`; pinned versions and checksums are recorded in `data/manifest.json`). The analysis ran locally with RDKit, pandas and rdata; no ToxIndex calls were made for this section.

| What | Original source | Result | Agrees with ToxIndex? |
|---|---|---|---|
| MutagenLou2023 | HuggingFace `maomlab/MutagenLou2023` (CC BY 4.0) | train 6,862 / test 1,714 / validation 1,469 = 10,045 rows. Validation = 805 DrugBank approved drugs + 664 strong Ames positives from DGM/NIHS, none in the original training set | ✅ same row count as the kiln copy |
| N-nitroso-varenicline structure | PubChem PUG REST | CID 163880833, InChIKey `PTBAEGOZXFWTJH-UHFFFAOYSA-N`, identical to the SMILES constructed from varenicline and checked with RDKit | n/a (not in DSSTox) |
| N-nitroso-varenicline regulatory status | EMA Appendix 1 xlsx (EMA/CHMP/219920/2026 Rev. 14, dated 2026-10-01) | CAS 2755871-02-2, **CPCA category 3, AI 400 ng/day**, source drug varenicline | not checked against `ema-nitrosamine-ai` brick yet |
| NDMA regulatory status | same EMA file | **AI 96 ng/day**, based on the harmonic mean TD50 (CPDB) | — |
| httk coverage | CRAN `httk` 2.7.4 (Tables.RData stamped 2025-12-04) | `chem.physical_and_invitro.data` has **18,476 chemicals**, not ~553. NDMA is present but has **no human in vitro TK parameters**. PFOA is present with Clint 0 (Crizer 2024), fup ≈ 0.002 (Smeltz 2023), and in the `pfas.clearance` table | ❌ the ToxIndex httk tool returned "not found" for both. Its description says ~553 chemicals, so it is probably an older httk or a lookup-by-name issue |
| PFOA IARC class | IARC Monographs Vol. 135 (meeting Nov 2023) | **Group 1** (carcinogenic to humans); PFOS is Group 2B | ❌ the ToxIndex chat agent said Group 2B |

**Local RDKit analysis of MutagenLou2023** (Morgan radius 2, 2048 bits, Tanimoto):
- **Composition per split:**
  - N-nitroso compounds: 240 in train (218 positive), 7 in test, **1 in validation**;
  - perfluoroalkyl chains: 7 in train, 3 in test, 12 in validation.
- **NDMA:** an exact match (InChIKey) in **train**.
- **PFOA:** no exact match. The nearest neighbours (perfluorodecanoic acid, perfluoroheptane, chlorofluoro acids) are **all Ames-negative**.
  - PFDA has Tanimoto **1.0** to PFOA. That's a fingerprint collision: Morgan radius 2 cannot distinguish chain length.
  - Lesson: similarity 1.0 ≠ same molecule, so always confirm identity with InChIKey.
- **N-nitroso-varenicline:** the nearest neighbour has Tanimoto **0.32** (small cyclic nitrosamines). There is no structurally close measured compound in this dataset.
- **Consequence for the design:** the independent validation split contains almost no nitrosamines, so a per-class independent benchmark for nitrosamines is not possible with this data. ToxiTrace therefore shows measured structural neighbours per query (rule R6) instead of a class-level accuracy figure.

## BioBricks (decision)

- **What we checked:** the BioBricks datasets relevant to this project (Hansen, ISSSTY, MutagenLou2023, ISSMIC and others) are reachable through ToxIndex's kiln endpoints, and MutagenLou2023 is also published directly on HuggingFace.
- **Decision:** ToxiTrace does not use a separate BioBricks client. Measured neighbour data comes from the MutagenLou2023 original (CC BY 4.0), and curated evidence comes from `tox_genotoxicity`.
- **Why:** this avoids a second integration and the licensing questions around the Hansen and ISSSTY extracts.
