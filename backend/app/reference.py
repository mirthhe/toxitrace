"""Local reference data used independently of ToxIndex (prepared by app.reference_data).

Loaded once and cached. If the data has not been installed, `load()` returns None and the
rules that need it say so, instead of silently skipping.
"""

import json
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path

import pandas as pd
from rdkit import DataStructs
from rdkit.Chem import rdFingerprintGenerator

from app.chem import parse_smiles
from app.config import settings
from app.schemas import EmaEntry, HalfLife, Neighbour

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
    httk_params: dict[str, dict] = field(default_factory=dict)  # by DTXSID
    httk_half_lives: dict[str, list[HalfLife]] = field(default_factory=dict)  # by DTXSID
    httk_version: str | None = None

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


def _median(value) -> float | None:
    """httk stores some parameters as "median,lower,upper[,p-value]" strings."""
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return float(value.split(",")[0])
    except ValueError:
        return None


def _httk(derived: Path) -> tuple[dict[str, dict], dict[str, list[HalfLife]]]:
    params = {}
    for _, row in pd.read_csv(derived / "httk_chem_params.csv", dtype=str).iterrows():
        if isinstance(row["DTXSID"], str):
            params[row["DTXSID"]] = {
                "compound": row["Compound"],
                "clint_median": _median(row["Human.Clint"]),
                "clint_reference": row["Human.Clint.Reference"] if isinstance(row["Human.Clint.Reference"], str) else None,
                "fup_median": _median(row["Human.Funbound.plasma"]),
                "fup_reference": (row["Human.Funbound.plasma.Reference"]
                                  if isinstance(row["Human.Funbound.plasma.Reference"], str) else None),
            }
    half_lives: dict[str, list[HalfLife]] = {}
    for _, row in pd.read_csv(derived / "httk_pfas_clearance.csv").iterrows():
        if pd.notna(row["HalfLifeHours"]):
            half_lives.setdefault(row["DTXSID"], []).append(HalfLife(
                species=row["Species"], sex=row["Sex"], hours=float(row["HalfLifeHours"]),
                reference=row["HlReference"] if isinstance(row["HlReference"], str) else None,
            ))
    return params, half_lives


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
    if not (data_dir / "manifest.json").exists() and settings.fetch_reference_data_on_demand:
        # Serverless deploys: the filesystem is read-only except /tmp. Same pinned, checksummed
        # downloads as `python -m app.reference_data`, done once per instance.
        import tempfile

        from app.reference_data import prepare
        data_dir = Path(tempfile.gettempdir()) / "toxitrace-data"
        if not (data_dir / "manifest.json").exists():
            prepare(data_dir)
    derived = data_dir / "derived"
    index_path = derived / "mutagenlou2023_index.csv"
    ema_path = derived / "ema_nitrosamine_ai.csv"
    if not (index_path.exists() and ema_path.exists()):
        return None

    manifest = json.loads((data_dir / "manifest.json").read_text())
    revision = manifest["sources"].get("ema/ema_nitrosamine_ai.xlsx", {}).get("revision")

    httk_source = next((k for k in manifest["sources"] if k.startswith("httk/")), None)
    params, half_lives = _httk(derived) if (derived / "httk_chem_params.csv").exists() else ({}, {})

    mutagens = pd.read_csv(index_path)
    return ReferenceData(
        mutagens=mutagens,
        fingerprints=[fingerprint(s) for s in mutagens["smiles"]],
        ema=_ema_entries(ema_path, revision),
        ema_revision=revision,
        httk_params=params,
        httk_half_lives=half_lives,
        httk_version=manifest["sources"][httk_source].get("version") if httk_source else None,
    )
