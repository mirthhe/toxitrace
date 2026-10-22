# Roadmap: from prototype to product

ToxiTrace is a working prototype: one endpoint (Ames), ten tested rules, three demo cases, verified against the live API and a small independent benchmark. This page sets out what it would take to turn the approach into something a team could build on, and which questions only Insilica can answer.

## 1. Product: what comes next

The order reflects value for researchers against effort, judged from what this prototype revealed.

| When | Step | Why | Effort |
|---|---|---|---|
| **Now** | **Strain and S9 detail** for experimental Ames results | The largest scientific gap. For NDMA the S9 dependence is the key fact, and ToxiTrace shows only the overall call. The data exists per strain in ISSSTY (via kiln). | Small |
| **Now** | **CPCA as a cross-check** of the EMA list | ToxIndex has a `cpca-classifier` tool. Computing the category from structure and comparing it with EMA's published category is the same "check against an independent route" principle as R1, applied to regulation. It also covers nitrosamines that are not on the EMA list. | Small |
| **Next** | **Literature evidence** via kiln document search | ToxiTrace correctly says *not retrieved* for N-nitroso-varenicline, but the enhanced Ames data exists in the literature. Retrieved passages would go into the evidence matrix, labelled with their source and kept separate from curated data. | Medium |
| **Next** | **More endpoints** using the same rule engine | `tox_genotoxicity` has siblings: carcinogenicity, skin sensitisation, repeated dose and others. The rules (predicted ≠ observed, independence, applicability domain, not retrieved ≠ absent) are endpoint-agnostic. | Medium per endpoint |
| **Later** | **Metabolite-aware toxicokinetics** | Ames positives such as NDMA need metabolic activation. Linking hazard to internal exposure requires a PBK model with a metabolite compartment and a quantitative genotoxicity endpoint (e.g. in vitro micronucleus benchmark doses), not httk's parent-compound models. | Large |
| **Later** | **A nitrosamine benchmark** | The independent benchmark contained almost no nitrosamines. Enhanced Ames results for NDSRIs, if they can be compiled, would allow a class-specific evaluation of the models used in two of the three demo cases. | Medium (mostly data) |

**Two ways to deliver it:**
- **as a ToxIndex pipeline step,** so the rules run inside existing workflows;
- **as a quality check on `tox_genotoxicity`'s own output,** so its verdicts carry ToxiTrace's flags.

## 2. Platform improvements suggested by this work

Observations from building on the API, framed as proposals. Evidence for each is in [discovery-notes.md](discovery-notes.md).

- **Fill in the `output_schema` of toxjobs models,** and make the OpenAPI response types match the actual responses. Typed clients and contract tests then come for free.
- **Return model versions consistently.** The direct VEGA call does (`vega-mutagenicity-v1.2`); AmesFormer and the aggregated VEGA finding do not. Without a version, a prediction cannot be reproduced later.
- **Report cross-tool conflicts in `tox_genotoxicity`.** For PFOA, a single low-confidence alert drives the verdict while `conflicts` is empty, and AmesFormer is not consulted.
- **Update the httk tool.** httk 2.7.4 covers 18,476 chemicals, including NDMA and PFOA, which the tool reported as not found.
- **Fall back to other identity sources** when DSSTox has no entry (PubChem, or the platform's own EMA list), so that registry-absent substances such as NDSRIs can still reach the evidence tools.

## 3. Engineering practices for a team

What this prototype did on a small scale, and what would carry over to a team:

- **Contract tests per upstream tool:**
  - unit tests run on recorded real responses;
  - live contract tests run on a schedule, not on every push;
  - drift (a changed field, a changed value) becomes an alert, not a production surprise.
- **Provenance as a default,** not a feature: every value carries the call, dataset version and checksum it came from.
- **A cross-source discrepancy log:** every disagreement between ToxIndex and an original source, or between two tools, is recorded. Over time this becomes a data-quality signal for the platform itself.
- **LLMs that explain, not decide:**
  - computed verdicts;
  - generated explanations checked against the data;
  - a deterministic fallback;
  - model choice based on measurement (the narrative model was changed after measuring that the newest model's safety classifiers consistently declined this content).
- **Guardrails for coding agents ([AGENTS.md](../AGENTS.md)):**
  - explicit approval for side effects such as API calls;
  - tests that never touch live services;
  - documentation written for its real audience.

## 4. A European perspective

- **Regulatory context:**
  - EU work runs through EMA (medicines, including the nitrosamine acceptable intakes ToxiTrace already uses), ECHA (REACH, CLP classification) and EFSA (food and pesticides).
  - ToxIndex already holds relevant EU sources: the EMA nitrosamine list, ECHA's mammalian toxicokinetics database, EFSA genotoxicity data, IUCLID search tools and the OECD PFAS list.
  - Surfacing which regulatory framework a piece of evidence comes from would make results more directly usable by EU customers.
- **New approach methodologies:**
  - European research programmes are working towards chemical safety assessment with fewer animal tests, for example the EU partnership PARC and, in the Netherlands, VHP4Safety.
  - I worked at VHP4Safety as a software engineer on PBPK infrastructure, standardised PBPK software, AI-assisted literature research and frontend development. The *literature evidence* and *metabolite-aware toxicokinetics* items above build directly on that experience.
  - Tools that combine in silico predictions, in vitro data and toxicokinetics, and that are explicit about how far each can be trusted, fit that direction.
  - ToxiTrace's rules on independence, applicability domain and "not retrieved ≠ absent" are exactly the kind of transparency such assessments need.
- **PFAS** are a European regulatory priority. They also showed, in this prototype, how far animal toxicokinetics can be from human toxicokinetics (PFOA half-life: hours in female rats, years in humans).

## 5. Open questions for Insilica

These shape priorities, and a prototype cannot answer them:

- **Users:** who are the main users of ToxIndex's structured tools (regulatory toxicologists, pharma impurity teams, consultancies), and which decisions do they make with them?
- **Interface:** is the chat agent or the API the main interface for customers, and where would a deterministic trust layer add most value?
- **Upstream ownership:** how are upstream models and datasets versioned and updated today, and who owns their quality?
- **The EU branch:** what are its first priorities: EU customers, EU data sources, or regulatory engagement?
