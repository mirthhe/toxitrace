"""Local reference data used independently of ToxIndex (prepared by app.reference_data).

Loaded once and cached. If the data has not been installed, `load()` returns None and the
rules that need it say so, instead of silently skipping.
"""

import json
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pandas as pd
from rdkit import DataStructs
from rdkit.Chem import rdFingerprintGenerator

from app.chem import parse_smiles
from app.config import settings
from app.schemas import EmaEntry, Neighbour

FINGERPRINT = "Morgan radius 2, 2048 bits, Tanimoto"
MUTAGEN_DATASET = "MutagenLou2023 (CC BY 4.0)"
_generator = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)


def fingerprint(smiles: str):
    mol = parse_smiles(smiles)
    return _generator.GetFingerprint(mol) if mol is not None else None


@dataclass
class ReferenceData:
    mutagens: pd.DataFrame  # smiles, inchikey, is_mutagen, split
    fingerprints: list
    ema: dict[str, EmaEntry]  # by InChIKey
    ema_revision: str | None

    def exact_match(self, key: str) -> Neighbour | None:
        rows = self.mutagens[self.mutagens["inchikey"] == key]
        if rows.empty:
            return None
        row = rows.iloc[0]
        return self._neighbour(row, similarity=1.0)

    def nearest(self, smiles: str, k: int = 5, exclude_key: str | None = None) -> list[Neighbour]:
        fp = fingerprint(smiles)
        if fp is None:
            return []
        sims = DataStructs.BulkTanimotoSimilarity(fp, self.fingerprints)
        ranked = self.mutagens.assign(similarity=sims).sort_values("similarity", ascending=False)
        if exclude_key:
            ranked = ranked[ranked["inchikey"] != exclude_key]
        return [self._neighbour(row, row["similarity"]) for _, row in ranked.head(k).iterrows()]

    @staticmethod
    def _neighbour(row, similarity: float) -> Neighbour:
        return Neighbour(
            smiles=row["smiles"],
            inchikey=row["inchikey"],
            call="positive" if int(row["is_mutagen"]) == 1 else "negative",
            split=row["split"],
            similarity=round(float(similarity), 3),
        )


def _ema_entries(path: Path, revision: str | None) -> dict[str, EmaEntry]:
    df = pd.read_csv(path, dtype=str).dropna(subset=["inchikey"])
    entries = {}
    for _, row in df.iterrows():
        ai = row.get("ai_ng_per_day")
        try:
            ai_value = float(ai) if isinstance(ai, str) else None
        except ValueError:  # some EMA cells hold text such as "see note"
            ai_value = None
        entries[row["inchikey"]] = EmaEntry(
            name=row["name"],
            cpca_category=row["cpca_category"] if isinstance(row["cpca_category"], str) else None,
            ai_ng_per_day=ai_value,
            publication_date=str(row["publication_date"])[:10] if isinstance(row["publication_date"], str) else None,
            revision=revision,
        )
    return entries


@cache
def load(data_dir: Path | None = None) -> ReferenceData | None:
    data_dir = data_dir or settings.data_dir
    derived = data_dir / "derived"
    index_path = derived / "mutagenlou2023_index.csv"
    ema_path = derived / "ema_nitrosamine_ai.csv"
    if not (index_path.exists() and ema_path.exists()):
        return None

    manifest = json.loads((data_dir / "manifest.json").read_text())
    revision = manifest["sources"].get("ema/ema_nitrosamine_ai.xlsx", {}).get("revision")

    mutagens = pd.read_csv(index_path)
    return ReferenceData(
        mutagens=mutagens,
        fingerprints=[fingerprint(s) for s in mutagens["smiles"]],
        ema=_ema_entries(ema_path, revision),
        ema_revision=revision,
    )
