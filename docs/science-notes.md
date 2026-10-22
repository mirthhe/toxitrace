# Scientific rationale

The scientific background behind ToxiTrace's choices: which endpoint, which chemicals, and which rules.

**How sources are marked:**
- **Verified:** checked against a primary source or a recorded API response, which is linked.
- **Background (unverified):** standard domain knowledge not yet checked against a primary source for this project. Treat it as context, not as a finding.

## Key concepts

**Ames test (bacterial reverse mutation test, OECD TG 471).**
- **How it works:** histidine-dependent *Salmonella typhimurium* (and *E. coli*) strains are exposed to a chemical. A mutagen causes reversions that restore growth; a significant increase in revertant colonies over the control is a positive result.
- **Role:** the standard first-tier genotoxicity assay, e.g. for pharmaceutical impurities under ICH M7.

**Metabolic activation (S9).**
- **What it is:** bacteria lack mammalian metabolism, so the assay is run with and without S9, a liver homogenate fraction supplying CYP450 enzymes.
- **Why it matters:** many mutagens are only active after metabolism.
- *Background (unverified):* nitrosamines are α-hydroxylated (mainly by CYP2E1) to a diazonium ion that alkylates DNA.
- **Link to toxicokinetics:** how much reactive metabolite forms *in vivo*, and where, depends on toxicokinetics that an in vitro S9 mix only approximates.

**Ames ≠ genotoxicity ≠ carcinogenicity.**
- **What Ames detects:** gene (point) mutations.
- **What it doesn't detect:** clastogens (chromosome breaks) and aneugens (changes in chromosome number). Those need other assays, e.g. the micronucleus test.
- **Non-genotoxic carcinogens** act without direct DNA damage and are Ames-negative.
- **Consequence for ToxiTrace:** an Ames-negative result is never presented as "not genotoxic" or "not carcinogenic".

**QSAR / ML predictions and their limits.**
- **The idea:** a model predicts an endpoint from structure alone.
- **Applicability domain:** it is only reliable for chemicals resembling its training data.
- **Overlap with evidence:** when the query chemical was in the training set, agreement with experimental data is expected and does not show predictive accuracy.

## Why Ames, and why these three chemicals

- **Why Ames:** the endpoint is binary, has extensive public experimental data, and is central to regulatory practice.
- **The three demo chemicals:** each represents a different evidence situation, which together exercise all of ToxiTrace's rules.

| Chemical | Evidence situation | Rules it exercises |
|---|---|---|
| N-nitrosodimethylamine (NDMA, CAS 62-75-9) | Data-rich; model and evidence agree, but the compound is in the training data | R5 independence, R8 nitrosamine context |
| Perfluorooctanoic acid (PFOA, CAS 335-67-1) | No experimental Ames data retrieved; predictions conflict; measured analogues exist | R2, R3, R4, R6, R7, R9 |
| N-nitroso-varenicline (CAS 2755871-02-2) | Not in EPA DSSTox; no evidence retrievable; the prediction is the only signal | R1, R6, R7, R8 |

## Observations from the recorded API responses (2026-10-21)

Response shapes and raw values are in [discovery-notes.md](discovery-notes.md).

### NDMA: model and evidence agree, but not independently

- **AmesFormer-Pro:** P(Ames+) = 0.998.
- **Evidence:** the ISSSTY curated call is Positive, and `tox_genotoxicity` reports the compound "carries a measured Ames value in the VEGA training set".
- **Training data:** NDMA is also in the MutagenLou2023 training split (verified locally by InChIKey).
- **Why this matters:** AmesFormer's stated training sources (Hansen, ISSSTY, EURL) overlap with these, so the agreement is expected and is not evidence of predictive accuracy.
- **In vivo:** the in vivo micronucleus result is **Equivocal**, so the GHS germ cell mutagenicity verdict is "Not classifiable" despite clear Ames positivity.
  - **Assay mismatch:** the micronucleus test detects clastogenic and aneugenic effects, whereas NDMA's mechanism is point mutation through DNA alkylation. An equivocal micronucleus result is therefore weak evidence either way; a transgenic rodent gene-mutation assay would be the appropriate in vivo test. This explanation was given by the ToxIndex chat agent (2026-10-22) and is consistent with the strain pattern below.
  - *Background (unverified):* toxicokinetics may contribute. NDMA is activated mainly in the liver, with high first-pass extraction, so bone marrow may see little reactive metabolite.
- **S9 dependence:** the ISSSTY strain-level data (as reported by the ToxIndex chat agent) is positive only with S9, in the base-pair substitution strains TA100, TA1535 and TA104, and negative in the frameshift strains TA98 and TA97. That pattern is consistent with methyldiazonium-mediated guanine alkylation. ToxiTrace currently reports only the overall call, not strain or S9 detail.

### PFOA: conflicting predictions, no experimental data retrieved

- **AmesFormer-Pro:** P(Ames+) = 0.0006, non-mutagenic.
- **VEGA:** none of its 4 models met its reliability threshold, so PFOA is outside their applicability domain.
- **Structural alerts:** one alert fires positive (score 0.45, low confidence).
- **`tox_genotoxicity`:**
  - verdict "In vitro genotoxicant", basis `predicted`, confidence Low, resting on that single alert;
  - `conflicts: []`;
  - all four experimental sources are listed under `gaps`.
- **Measured analogues:** the nearest measured analogues in MutagenLou2023 (independent download, local RDKit) are all Ames-negative, among them perfluorodecanoic acid, perfluoroheptane and chlorofluoro carboxylic acids.
- **Consequences for the rules:**
  - predictor disagreement is shown, not averaged (R3);
  - a model declining to predict is a signal (R4);
  - a prediction-based verdict is never presented as a hazard conclusion (R2);
  - "not retrieved" is distinct from "does not exist" (R7).

### N-nitroso-varenicline: prediction only

- **AmesFormer-Pro:** P(Ames+) = 0.951.
- **Registry:** the substance is not in EPA DSSTox, so `tox_genotoxicity` returns 422.
- **Measured structural neighbours:** the closest measured compound in MutagenLou2023 has Tanimoto similarity 0.32 (Morgan radius 2), so there is no close measured analogue.
- **Regulatory status:** EMA lists the substance with **CPCA category 3** and an **acceptable intake of 400 ng/day** (EMA/CHMP/219920/2026 Rev. 14). Verified against the EMA file.

## ToxIndex chat agent vs structured tool output (2026-10-21)

**The question:** "Is PFOA mutagenic in the Ames test?", asked in the ToxIndex web chat.

**What the agent did:**
- resolved two forms (free acid DTXSID8031865, anion DTXSID40892486);
- found no curated Ames data for PFOA;
- performed a read-across to Ames-negative perfluorinated analogues;
- identified the structural-alert positive as an "alkyl halide (SN2)" rule misfiring on C–F bonds;
- noted that `tox_genotoxicity` builds a "genotoxic carcinogen" statement on that alert alone.
- Its conclusion was "unresolved from curated data, more consistent with Ames-negative".

**How that compares with the structured tool output:** the chat agent reasons well, but in free text. The structured output that pipelines consume reports "In vitro genotoxicant" with no conflicts.

**ToxiTrace's design follows from this:** the same checks are encoded as deterministic rules with unit tests. An LLM only narrates a verdict that the code has already computed.

**PFOA's IARC classification:**
- The chat agent cited PFOA as **IARC Group 2B**.
- IARC Monographs Vol. 135 (Working Group, Lyon, 7–14 November 2023) classified PFOA as **Group 1**, carcinogenic to humans. The basis was sufficient evidence in experimental animals and strong mechanistic evidence, with limited evidence in humans (testicular and renal cell cancer).
- PFOS was classified as Group 2B.
- Verified: [IARC announcement](https://www.iarc.who.int/news-events/iarc-monographs-evaluate-the-carcinogenicity-of-perfluorooctanoic-acid-pfoa-and-perfluorooctanesulfonic-acid-pfos/), [Vol. 135](https://publications.iarc.who.int/Book-And-Report-Series/Iarc-Monographs-On-The-Identification-Of-Carcinogenic-Hazards-To-Humans/Perfluorooctanoic-Acid-PFOA-And-Perfluorooctanesulfonic-Acid-PFOS--2025).
- PFOA's Group 1 classification is not based on genotoxicity, which illustrates why Ames-negative ≠ non-carcinogenic.

## Toxicokinetic context: PFOA (httk 2.7.4, verified locally)

Measured half-lives from httk's `pfas.clearance` table (CRAN httk 2.7.4):

| Species | Female | Male |
|---|---|---|
| Human | 20,150 h (~2.3 years) | 22,340 h (~2.5 years) |
| Monkey | 782 h | 492 h |
| Rat | 2.8 h | 236 h |
| Mouse | 374 h | 521 h |

**What the table shows:**
- **Spread:** half-lives span about four orders of magnitude across species, and about 80× between female and male rats.
  - *Background (unverified):* the rat sex difference is attributed to hormone-regulated renal organic anion transporters that reabsorb PFOA in males.
- **Why httk has a separate PFAS table:** httk lists human Clint = 0 (Crizer 2024) and fraction unbound in plasma ≈ 0.002 (Smeltz 2023) for PFOA. Elimination is therefore dominated by renal handling that the generic in vitro-to-in vivo route does not capture, which is why httk ships the dedicated table.
- **For ToxiTrace:** toxicokinetic models have applicability domains too. Rule R9 shows TK context where data exists and states plainly when it does not.

**Why PBK is not coupled to Ames directly:**
- Ames is qualitative, so it provides no in vitro effect concentration for in vitro-to-in vivo extrapolation (IVIVE).
- httk models the parent compound, not reactive metabolites.
- A meaningful coupling would need:
  - a metabolite-aware PBK model;
  - target-tissue dosimetry;
  - a quantitative genotoxicity endpoint, e.g. in vitro micronucleus benchmark doses.
- This is future work.

## Regulatory background: nitrosamines

**Verified (EMA Appendix 1, Rev. 14):**
- NDMA has an acceptable intake of 96 ng/day, derived from the harmonic mean TD50 in the Carcinogenic Potency Database.
- N-nitroso-varenicline is in CPCA category 3, at 400 ng/day.

**Background (unverified; check against FDA/EMA guidance before relying on it):**
- **ICH M7 cohort of concern:** ICH M7 designates N-nitroso compounds a "cohort of concern", to which the default threshold of toxicological concern does not apply.
- **2018 and 2021 recalls:** NDMA contamination led to sartan recalls in 2018, and N-nitroso-varenicline led to varenicline recalls in 2021. The latter is an NDSRI: a nitrosamine drug substance-related impurity.
- **CPCA:** in 2023 FDA and EMA introduced the Carcinogenic Potency Categorization Approach, which assigns potency categories from structural features.
- **Enhanced Ames test:** FDA and EMA recommend an enhanced Ames protocol for nitrosamines (higher S9 concentration, hamster S9, pre-incubation), because the standard protocol can under-detect them.

## Background: PFOA mechanism

*Background (unverified):*
- **Mechanism:** PFOA is generally regarded as non-genotoxic. Proposed carcinogenic mechanisms include receptor-mediated effects (e.g. PPARα), immunosuppression and epigenetic changes.
- **Applicability domain:** highly fluorinated chemicals are likely underrepresented in Ames training data. That is consistent with VEGA declining to predict, but not verified for AmesFormer.
