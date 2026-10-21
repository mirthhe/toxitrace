# Discovery notes (SPEC §2)

Fill in from the real, authenticated API. No guessed fields.

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
- **Agent attribution headers:** `POST /tools/{name}` accepts the `X-ToxIndex-Agent-Name`, `-Model`, `-Harness` and `-Host` headers. The `sysrev_*` tools require them. Sending them would label our calls honestly in ToxIndex's logs.
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

Still to fill in after a real call:

- Chosen endpoint / tool:
- Model identifier:
- Input type + sample chemical:
- Response schema (paste a sanitised example):
- Score semantics / units:
- Error conditions observed:
- Provenance fields available:
- Question this endpoint can answer without overstating:

## BioBricks (optional)

Possibly reachable through `/kiln/brick` instead of a separate BioBricks client. Still to check.

- Dataset:
- Schema:
- Chemical identity match possible?
- Compatible endpoint?
- Decision (include / drop, and why):
