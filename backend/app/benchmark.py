"""Small independent benchmark of AmesFormer-Pro (see docs/benchmark.md).

Question: how well does AmesFormer-Pro predict Ames results for compounds outside its stated
training sources? Compounds come from the MutagenLou2023 external validation split; any
compound whose InChIKey skeleton also occurs in the train/test splits (Hansen and ISSSTY,
AmesFormer's stated training sources) is excluded. A stratified sample is drawn with a fixed
seed. Predictions are cached, so a compound is never sent to ToxIndex twice.

    uv run python -m app.benchmark --dry-run     # sample and pool sizes, no API calls
    uv run python -m app.benchmark               # predict missing compounds, then report

A local nearest-neighbour baseline (label of the most similar training compound) is computed
without any API call, to show whether the model adds anything over naive read-across.
"""

import argparse
import asyncio
import json
import math

import pandas as pd
from rdkit import Chem, DataStructs
from rdkit.Chem import Descriptors

from app.adapters import toxindex
from app.chem import connectivity_block
from app.config import REPO_ROOT, settings
from app.reference import fingerprint
from app.trace import Tracer

SEED = 20261022
PER_CLASS = 20
RESULTS = REPO_ROOT / "benchmark" / "amesformer_predictions.json"
REPORT = REPO_ROOT / "benchmark" / "results.md"
DELAY_SECONDS = 1.0  # be gentle with a shared service
ORGANIC = {"C", "H", "N", "O", "S", "P", "F", "Cl", "Br", "I"}
MAX_MW = 500.0


def in_scope(smiles: str) -> bool:
    """Inclusion criteria, applied to both classes alike.

    AmesFormer-Pro accepts "a single connected compound" (its tool description), so salts,
    mixtures and metal complexes are excluded. The MW cap keeps both classes to small
    molecules: the validation split pairs small reactive positives (NIHS) with often large
    drug negatives (DrugBank), and size alone would otherwise separate the classes.
    """
    if "." in smiles:
        return False
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return False
    if any(atom.GetSymbol() not in ORGANIC for atom in mol.GetAtoms()):
        return False
    return Descriptors.MolWt(mol) <= MAX_MW


def independent_pool(index: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Validation compounds whose skeleton does not occur in the train/test splits."""
    index = index.assign(skeleton=index["inchikey"].map(connectivity_block))
    trained = set(index.loc[index["split"].isin(["train", "test"]), "skeleton"])
    validation = index[index["split"] == "validation"].drop_duplicates("skeleton")
    independent = validation[~validation["skeleton"].isin(trained)]
    pool = independent[independent["smiles"].map(in_scope)]
    stats = {
        "validation_compounds": int((index["split"] == "validation").sum()),
        "unique_skeletons": len(validation),
        "removed_overlap_with_train_test": len(validation) - len(independent),
        "removed_out_of_scope": len(independent) - len(pool),
        "independent_pool": len(pool),
        "pool_positive": int(pool["is_mutagen"].sum()),
        "pool_negative": int((pool["is_mutagen"] == 0).sum()),
    }
    return pool, stats


def stratified_sample(pool: pd.DataFrame, per_class: int = PER_CLASS) -> pd.DataFrame:
    parts = [pool[pool["is_mutagen"] == label].sample(n=per_class, random_state=SEED) for label in (1, 0)]
    return pd.concat(parts).reset_index(drop=True)


def nearest_neighbour_baseline(sample: pd.DataFrame, index: pd.DataFrame) -> list[dict]:
    """Label of the most similar train/test compound: naive read-across, no API calls."""
    reference = index[index["split"].isin(["train", "test"])].reset_index(drop=True)
    fps = [fingerprint(s) for s in reference["smiles"]]
    out = []
    for smiles in sample["smiles"]:
        sims = DataStructs.BulkTanimotoSimilarity(fingerprint(smiles), fps)
        best = max(range(len(sims)), key=sims.__getitem__)
        out.append({"call": int(reference.loc[best, "is_mutagen"]), "similarity": round(sims[best], 3)})
    return out


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval: honest for small n."""
    if n == 0:
        return (math.nan, math.nan)
    p = successes / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (max(0.0, centre - half), min(1.0, centre + half))


def metrics(truth: list[int], predicted: list[int]) -> dict:
    tp = sum(t == 1 and p == 1 for t, p in zip(truth, predicted))
    tn = sum(t == 0 and p == 0 for t, p in zip(truth, predicted))
    pos, neg = sum(truth), len(truth) - sum(truth)
    sens, spec = tp / pos, tn / neg
    return {
        "n": len(truth),
        "sensitivity": (sens, wilson(tp, pos)),
        "specificity": (spec, wilson(tn, neg)),
        "balanced_accuracy": (sens + spec) / 2,
        "confusion": {"TP": tp, "FN": pos - tp, "TN": tn, "FP": neg - tn},
    }


async def predict_missing(sample: pd.DataFrame, cache: dict) -> dict:
    toxindex.AGENT_HEADERS["X-ToxIndex-Agent-Name"] = "ToxiTrace (benchmark)"
    tracer = Tracer()
    for smiles in sample["smiles"]:
        if smiles in cache:
            continue
        try:
            _, body = await toxindex.predict_ames(smiles, tracer)
            cache[smiles] = body["output"]
        except toxindex.ToxIndexError as exc:
            cache[smiles] = {"error": str(exc), "status": exc.status}
        RESULTS.write_text(json.dumps(cache, indent=1))  # persist after every call
        print(f"  {len(cache):>3}/{len(sample)}  {smiles[:60]}")
        await asyncio.sleep(DELAY_SECONDS)
    return cache


def _fmt(value: tuple[float, tuple[float, float]]) -> str:
    point, (low, high) = value
    return f"{point:.2f} (95% CI {low:.2f}–{high:.2f})"


def report(sample: pd.DataFrame, stats: dict, cache: dict, baseline: list[dict]) -> str:
    rows = sample.assign(baseline=[b["call"] for b in baseline], nn_similarity=[b["similarity"] for b in baseline])
    rows["probability"] = rows["smiles"].map(lambda s: cache.get(s, {}).get("probability"))
    rows["amesformer"] = rows["smiles"].map(lambda s: cache.get(s, {}).get("mutagenic"))
    scored = rows.dropna(subset=["amesformer"])
    truth = scored["is_mutagen"].astype(int).tolist()
    model = metrics(truth, scored["amesformer"].astype(int).tolist())
    naive = metrics(truth, scored["baseline"].astype(int).tolist())
    failed = len(rows) - len(scored)

    lines = [
        "# AmesFormer-Pro on independent compounds: results",
        "",
        (f"Generated by `uv run python -m app.benchmark` (seed {SEED}). Method and caveats: "
         "[docs/benchmark.md](../docs/benchmark.md)."),
        "",
        "## Pool",
        "",
        "| Step | Compounds |",
        "|---|---|",
        f"| MutagenLou2023 external validation split | {stats['validation_compounds']} |",
        f"| Unique skeletons (InChIKey first block) | {stats['unique_skeletons']} |",
        f"| Removed: skeleton also in train/test (Hansen, ISSSTY) | {stats['removed_overlap_with_train_test']} |",
        (f"| Removed: out of scope (salt/mixture, non-organic element, MW > {MAX_MW:.0f}) | "
         f"{stats['removed_out_of_scope']} |"),
        (f"| Independent pool | {stats['independent_pool']} ({stats['pool_positive']} positive, "
         f"{stats['pool_negative']} negative) |"),
        f"| Stratified sample | {len(rows)} ({PER_CLASS} positive, {PER_CLASS} negative) |",
        f"| Scored (prediction obtained) | {len(scored)}{f'; {failed} failed' if failed else ''} |",
        "",
        "## Results",
        "",
        "| Method | Sensitivity | Specificity | Balanced accuracy | TP / FN / TN / FP |",
        "|---|---|---|---|---|",
    ]
    for name, m in [("AmesFormer-Pro (P ≥ 0.5)", model), ("Nearest-neighbour read-across (local baseline)", naive)]:
        c = m["confusion"]
        lines.append(f"| {name} | {_fmt(m['sensitivity'])} | {_fmt(m['specificity'])} | "
                     f"{m['balanced_accuracy']:.2f} | {c['TP']} / {c['FN']} / {c['TN']} / {c['FP']} |")
    lines += [
        "",
        f"Median similarity of the nearest train/test compound: {rows['nn_similarity'].median():.2f}.",
        "",
        "## Per compound",
        "",
        "| SMILES | Measured | AmesFormer P | AmesFormer | Read-across | NN similarity |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows.itertuples():
        prob = f"{r.probability:.3f}" if pd.notna(r.probability) else "—"
        model_call = {True: "+", False: "−"}.get(r.amesformer, "failed")
        lines.append(f"| `{r.smiles}` | {'+' if r.is_mutagen else '−'} | {prob} | {model_call} | "
                     f"{'+' if r.baseline else '−'} | {r.nn_similarity:.2f} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Independent AmesFormer-Pro benchmark")
    parser.add_argument("--dry-run", action="store_true", help="show the sample; no API calls")
    args = parser.parse_args()

    index_path = settings.data_dir / "derived" / "mutagenlou2023_index.csv"
    if not index_path.exists():
        raise SystemExit("Reference data missing: run `uv run python -m app.reference_data` first.")
    index = pd.read_csv(index_path)
    pool, stats = independent_pool(index)
    sample = stratified_sample(pool)
    cache = json.loads(RESULTS.read_text()) if RESULTS.exists() else {}
    missing = [s for s in sample["smiles"] if s not in cache]

    print(json.dumps(stats, indent=1))
    print(f"sample: {len(sample)} compounds; cached: {len(sample) - len(missing)}; "
          f"ToxIndex calls needed: {len(missing)}")
    if args.dry_run:
        print(sample[["smiles", "is_mutagen"]].to_string(index=False))
        return

    RESULTS.parent.mkdir(exist_ok=True)
    cache = asyncio.run(predict_missing(sample, cache))
    baseline = nearest_neighbour_baseline(sample, index)
    REPORT.write_text(report(sample, stats, cache, baseline))
    print(f"report written to {REPORT}")


if __name__ == "__main__":
    main()
