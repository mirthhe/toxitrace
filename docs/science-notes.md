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
