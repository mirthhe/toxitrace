# Independent benchmark: AmesFormer-Pro

**Question:** how well does AmesFormer-Pro predict Ames results for compounds outside its stated training sources?

**Results:** [benchmark/results.md](../benchmark/results.md) (generated, 2026-10-22).
**Code:** [backend/app/benchmark.py](../backend/app/benchmark.py).
**Reproduce:** `uv run python -m app.benchmark` in `backend/`. Predictions are cached in `benchmark/amesformer_predictions.json`, so a re-run makes no ToxIndex calls.

## Method

1. **Source:** the MutagenLou2023 external validation split, 1,469 compounds (CC BY 4.0, [HuggingFace](https://huggingface.co/datasets/maomlab/MutagenLou2023)). Per the dataset description, it holds 805 approved drugs from DrugBank and 664 strong Ames positives from DGM/NIHS, none of them in the dataset's own training set.
2. **Independence from AmesFormer's training data:** AmesFormer-Pro's stated training sources are Hansen, ISSSTY and EURL. Compounds whose InChIKey skeleton (first block) also occurs in the MutagenLou2023 train/test splits were removed (42 compounds), since those splits are built from Hansen and ISSSTY.
3. **Inclusion criteria, applied to both classes:** 245 compounds were removed by these.
   - a single connected molecule (AmesFormer accepts "a single connected compound");
   - common organic elements only;
   - molecular weight ≤ 500.

   The MW cap matters: without it, the split pairs small reactive positives with often large drug negatives, and molecular size alone would separate the classes.
4. **Sample:** 20 positives and 20 negatives drawn from the remaining 1,162 compounds, stratified, with a fixed seed.
5. **Predictions:** `toxjobs_predict` with `amesformer`; one call per compound, 1 s apart, labelled "ToxiTrace (benchmark)". A call is "positive" when P ≥ 0.5, the model's own threshold.
6. **Baseline:** nearest-neighbour read-across, i.e. the label of the most similar train/test compound (Morgan r2, Tanimoto). It is computed locally with no API calls, and asks whether the model adds anything over naive read-across.
7. **Statistics:** sensitivity and specificity with 95% Wilson intervals, which suit small samples, plus balanced accuracy.

## Results

| Method | Sensitivity | Specificity | Balanced accuracy |
|---|---|---|---|
| AmesFormer-Pro | 0.95 (0.76–0.99) | 0.90 (0.70–0.97) | 0.93 |
| Nearest-neighbour read-across | 0.70 (0.48–0.85) | 0.90 (0.70–0.97) | 0.80 |

### AmesFormer-Pro's errors (3 of 40)

| Compound | Measured | P | Note |
|---|---|---|---|
| `COC(=O)Cc1ccc(CCl)cc1` | positive | 0.36 | A benzylic chloride, a classic alkylating structure. A close analogue in the same sample (`CC(C)Oc1ccc(CCl)cc1`) was called positive (P = 0.80). |
| `Cc1cccc(Nc2ccccc2C(=O)O)c1C` (mefenamic acid) | negative | 0.75 | Diphenylamine skeleton; aromatic-amine-like features may drive the call. 🔎 |
| `C#CCN(C)Cc1ccccc1` (pargyline) | negative | 0.79 | Propargylamine; reason unknown. |

### The baseline's errors

Read-across missed 6 of 20 positives. Most of them have a nearest training compound with similarity around 0.29: without a close analogue, read-across has little to go on. That is the situation rule R6 flags.

## Interpretation

- **On this sample, AmesFormer-Pro performs well on compounds outside its stated training sources.** It beats naive read-across, mainly on sensitivity.
- **The difference in sensitivity is suggestive, not conclusive:** the intervals overlap at n = 40. The two methods do not differ on specificity in this sample.
- **This supports, but does not prove, that AmesFormer's probability carries information beyond memorised training data.** That matters for cases like N-nitroso-varenicline, where the prediction is the only signal.

## Caveats (read before quoting the numbers)

- **Small sample:** n = 40, so the intervals are wide.
- **Easier positives:** the positives are *strong* Ames positives from NIHS, by the dataset's own description. Borderline and weak mutagens, which are the hard cases in practice, are under-represented, so real-world sensitivity is likely lower.
- **Two different populations:** the negatives are approved drugs, which differ systematically from the positives (industrial and reactive chemicals) even after the MW cap.
- **EURL not checked:** overlap with AmesFormer's third training source, EURL, could not be tested. Some compounds may not be fully independent.
- **Nitrosamines are not covered.** The independent pool contains almost none, so these numbers say **nothing** about the class used in two of the three demo cases.
- **Single run:** single run, single threshold (0.5), no calibration analysis.
