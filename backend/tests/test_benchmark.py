import pandas as pd
import pytest

from app.benchmark import in_scope, independent_pool, metrics, wilson
from app.chem import inchikey


@pytest.mark.parametrize("smiles, expected", [
    ("COC(=O)Cc1ccc(CCl)cc1", True),
    ("CC(=O)O.[Na+]", False),            # salt / mixture
    ("S=[Se]=S", False),                 # non-organic element
    ("C" * 40, False),                   # MW > 500
])
def test_in_scope(smiles, expected):
    assert in_scope(smiles) is expected


def test_independent_pool_removes_training_skeletons():
    rows = [("CN(C)N=O", 1, "train"), ("CN(C)N=O", 1, "validation"),
            ("CCN(CC)N=O", 1, "validation"), ("c1ccccc1O", 0, "validation")]
    index = pd.DataFrame(rows, columns=["smiles", "is_mutagen", "split"])
    index["inchikey"] = index["smiles"].map(inchikey)

    pool, stats = independent_pool(index)

    assert set(pool["smiles"]) == {"CCN(CC)N=O", "c1ccccc1O"}
    assert stats["removed_overlap_with_train_test"] == 1


def test_metrics_and_wilson_interval():
    m = metrics(truth=[1, 1, 1, 1, 0, 0, 0, 0], predicted=[1, 1, 1, 0, 0, 0, 0, 1])
    assert m["confusion"] == {"TP": 3, "FN": 1, "TN": 3, "FP": 1}
    assert m["sensitivity"][0] == 0.75
    assert m["balanced_accuracy"] == 0.75
    low, high = wilson(19, 20)
    assert 0.75 < low < 0.77 and 0.98 < high < 1.0  # matches the reported 0.76-0.99
