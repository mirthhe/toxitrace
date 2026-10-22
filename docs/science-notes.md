# Science notes

My running explainer for the scientific choices in ToxiTrace, kept for interview prep. Claims marked *(own knowledge, verify)* come from background knowledge, not from an API response. Check them against primary sources before presenting them.

## Key concepts

**Ames test (bacterial reverse mutation test, OECD TG 471).**
- **How it works:** Salmonella (and E. coli) strains that can't make the amino acid histidine are exposed to a chemical. If the chemical causes mutations, some bacteria "revert" and can grow again. More colonies than in the control means a positive result, i.e. the chemical is mutagenic.
- **Why it matters:** it's cheap, fast and standard, and it's the first test in almost every genotoxicity assessment (ICH M7 for pharmaceutical impurities).

**S9 (metabolic activation).**
- **What it is:** a liver extract, usually from rats, added to the test. Bacteria lack mammalian metabolism, so S9 supplies the enzymes (mainly CYP450).
- **Why it matters:** many chemicals are only mutagenic **after** metabolism. Nitrosamines are a prime example: CYP2E1 hydroxylates them at the α-carbon, producing a reactive diazonium ion that alkylates DNA.
- **Link to PBK:** metabolic activation is where your PBK background connects. What a body actually produces depends on enzyme kinetics, which an in vitro S9 mix only roughly approximates.

**Ames ≠ genotoxicity ≠ carcinogenicity.**
- **What Ames detects:** gene (point) mutations.
- **What it misses:** chromosome breaks (clastogens) and changes in chromosome number (aneugens). Those need other assays, such as the micronucleus test.
- **Non-genotoxic carcinogens** cause cancer without damaging DNA directly, e.g. via receptor activation or chronic inflammation. They are Ames-negative.

**QSAR / ML prediction.**
- **The idea:** predict a property from chemical structure alone.
- **Limits:**
  - **Training data:** the model is only as good as its training data.
  - **Applicability domain:** it's only reliable for chemicals similar to those it was trained on.
  - **Overlap with evidence:** if a test chemical was in the training set, agreement with lab data is expected and proves little.

## Identity resolution findings (ToxIndex `tox_chemical_identity`, 2026-10-21)

| Query | Result |
|---|---|
| `62-75-9` (CAS) | 1 match: N-Nitrosodimethylamine (NDMA), DTXSID7021029, SMILES `CN(C)N=O` |
| `335-67-1` (CAS) | 1 match: Perfluorooctanoic acid (PFOA), DTXSID8031865 |
| `N-nitroso-varenicline` (name) | 0 matches |
| `O=NN1CC2CC(C1)c1cc3nccnc3cc12` (SMILES) | 0 matches |

- **Where the N-nitroso-varenicline SMILES came from:** varenicline's SMILES with a nitroso group (N=O) added to its secondary amine. Checked locally with RDKit: formula C13H12N4O, InChIKey PTBAEGOZXFWTJH-UHFFFAOYSA-N.
- **What the 0 matches mean:** N-nitroso-varenicline is **not in EPA DSSTox**. That is typical for NDSRIs, which are new impurities with little regulatory data. The app should treat "not in registry" as a meaningful, displayed fact, not as an error.

## What the first real calls showed (2026-10-21)

See `docs/discovery-notes.md` for the raw numbers.

**NDMA: data-rich, and everything agrees. That agreement is circular.**
- **The results:** AmesFormer gives P = 0.998. The curated ISSSTY data is Ames-positive, and the evidence tool literally says NDMA "carries a measured Ames value in the VEGA training set".
- **Why that proves little:** the model has most likely seen this compound during training, so the agreement is expected. It doesn't show the model is accurate.
- **The in vivo result:** the micronucleus test is **Equivocal**, so the overall GHS verdict is "Not classifiable" even though it is clearly Ames-positive. Possible explanation *(own knowledge, verify)*:
  - NDMA is activated mainly in the liver (CYP2E1), with high first-pass extraction;
  - a bone-marrow micronucleus test samples a tissue that may see little of the reactive metabolite;
  - that is a kinetics question, i.e. a PBK question.

**PFOA: evidence exists in the world but was not retrieved, and the predictions disagree.**
- **What's missing:** no experimental Ames data was retrieved. All four experimental sources are listed under `gaps`.
- **The predictions disagree:**
  - AmesFormer says non-mutagenic with P = 0.0006;
  - VEGA: none of its 4 models considered PFOA within its reliable domain;
  - one structural alert fires positive, with low confidence.
- **The tool's verdict:** "In vitro genotoxicant", based on that single low-confidence alert, with `conflicts: []`.
- **The published picture** *(own knowledge, verify)*: PFOA is generally reported as Ames-negative.
- **Lessons for the app:**
  - "not retrieved" must be displayed as different from "doesn't exist";
  - disagreement between predictors must be shown, not averaged away;
  - an aggregate verdict should never be shown without the findings underneath it.

**N-nitroso-varenicline: the real use case for a prediction.**
- **Results:** AmesFormer gives P = 0.951. The chemical is not in DSSTox, so the evidence tool returns 422 and no evidence can be retrieved.
- **Why it matters:** this is the situation where predictions actually matter, because there is nothing else.
- **The app should say so plainly:** single model, structure entered by the user (not taken from a registry), no evidence retrieved, and an applicability domain we can't verify.
- *(own knowledge, verify)*: nitrosamines with this structure are exactly why the 2023 CPCA approach exists.

## Comparison with ToxIndex's own chat agent (2026-10-21)

**The question:** "Is PFOA mutagenic in the Ames test?", asked in the ToxIndex web app.

**What the agent did, and did well:**
- It resolved PFOA to two forms: the free acid, DTXSID8031865, and the anion, DTXSID40892486.
- It found no experimental Ames data in ISSSTY, Hansen, MutagenLou2023 or EFSA.
- It did a read-across: four perfluorinated analogues, including C10 PFDA, are Ames-negative.
- It noticed that the predictions conflict.
- It explained that the positive structural alert ("alkyl halide, SN2 alkylating agent") misfires on C–F bonds, which are not SN2 electrophiles.
- It noted that `tox_genotoxicity` promotes that single alert to "bacterial reverse mutation: Positive" and then to "genotoxic carcinogen", and said this chain should not be trusted.
- Conclusion: "unresolved from curated data, more consistent with Ames-negative".

**What this means for ToxiTrace's positioning:**
- The *chat agent* already does this weight-of-evidence reasoning, and does it well. The *structured tool output* (`tox_genotoxicity`, which pipelines and API users consume) does not: verdict "In vitro genotoxicant", `conflicts: []`.
- The agent's reasoning is LLM prose. It caught the problem this time, but nothing guarantees it will every time, and it can't be tested.
- **ToxiTrace's angle:** turn that reasoning into **deterministic, testable rules in code** that produce a structured result. The LLM only explains a verdict that the code has already computed.
- **How to put it in the interview:** "your agent caught it in prose; your structured output didn't; ToxiTrace makes catching it a guaranteed, testable check."

**Verified discrepancy:** the agent cited PFOA as **IARC Group 2B**. IARC Monographs Vol. 135 (Working Group, Lyon, 7–14 Nov 2023) classified PFOA as **Group 1**, carcinogenic to humans. The basis was sufficient evidence in experimental animals plus strong mechanistic evidence, with limited evidence in humans (testis and kidney cancer). PFOS was classified as 2B. The platform's carcinogenicity data appears stale, or it mixed up PFOA and PFOS. Sources: [IARC news](https://www.iarc.who.int/news-events/iarc-monographs-evaluate-the-carcinogenicity-of-perfluorooctanoic-acid-pfoa-and-perfluorooctanesulfonic-acid-pfos/), [Vol. 135](https://publications.iarc.who.int/Book-And-Report-Series/Iarc-Monographs-On-The-Identification-Of-Carcinogenic-Hazards-To-Humans/Perfluorooctanoic-Acid-PFOA-And-Perfluorooctanesulfonic-Acid-PFOS--2025).

## Toxicokinetics: PFOA in httk (CRAN httk 2.7.4, verified locally)

The `pfas.clearance` table gives measured PFOA half-lives:

| Species | Female | Male |
|---|---|---|
| Human | 20,150 h (~2.3 years) | 22,340 h (~2.5 years) |
| Monkey | 782 h | 492 h |
| Rat | **2.8 h** | **236 h** |
| Mouse | 374 h | 521 h |

**Why this table matters:**
- **Across species, half-lives differ by four orders of magnitude.** Female vs male rats alone differ by a factor of about 80. *(Own knowledge, verify:)* this is attributed to sex-hormone-regulated renal transporters (OATs) that reabsorb PFOA in male rats.
- **Animal data doesn't transfer directly to humans.** A rat study cannot be extrapolated to humans without a TK model that includes this mechanism.
- **The same lesson as for the Ames models:** every model, including a TK model, has an applicability domain.
- **httk handles PFAS separately.** In the in vitro table, human Clint = 0 (no hepatic metabolism) and fup ≈ 0.002 (over 99.8% bound to plasma protein). The generic IVIVE route would predict elimination from these parameters, which is why httk ships a dedicated PFAS clearance table.

## Candidate case: nitrosamines

*(own knowledge, verify)*
- **2018, valsartan:** recalled because of NDMA contamination.
- **2021, Chantix (varenicline):** recalled because of N-nitroso-varenicline. This was an NDSRI (nitrosamine drug substance-related impurity), formed from the drug molecule itself.
- **ICH M7:** names N-nitroso compounds a "cohort of concern", meaning they are so potent that the default acceptable intake limits do not apply.
- **2023, FDA and EMA:**
  - introduced the Carcinogenic Potency Categorization Approach (CPCA), which puts a nitrosamine into a potency category based on its structural features;
  - recommended an "enhanced Ames test" (more S9, hamster S9, pre-incubation), because the standard Ames test can miss some nitrosamines.

## Candidate case: PFOA

*(own knowledge, verify)*
- **Who and where:** a PFAS chemical, relevant in NL (Chemours Dordrecht).
- **Classification:** IARC classified PFOA as carcinogenic to humans (Group 1) in 2023.
- **Mechanism:** generally regarded as non-genotoxic. Typically Ames-negative; the proposed mechanisms include receptor-mediated effects (e.g. PPARα), immune effects and epigenetic effects.
- **Why it's interesting for ToxiTrace:** "Ames-negative" here does **not** mean "safe". Also, highly fluorinated chemicals are probably underrepresented in Ames training data, so it's an applicability domain question.
