"""Download and prepare the public reference datasets ToxiTrace uses independently of ToxIndex.

Run once after install:  uv run python -m app.reference_data  (add --force to re-download)

Raw downloads are verified against pinned SHA-256 hashes where the publisher offers a fixed
version, converted to plain CSV, and recorded in data/manifest.json so every value shown in
the app can name the exact file it came from. Nothing here is committed: licences vary.
"""

import argparse
import hashlib
import json
import tarfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pandas as pd

from app.chem import inchikey
from app.config import settings

MUTAGENLOU_COMMIT = "a9780a60774eb522b78bd92b83c30d8deae00ff5"
MUTAGENLOU_BASE = (
    f"https://huggingface.co/datasets/maomlab/MutagenLou2023/resolve/{MUTAGENLOU_COMMIT}"
)
HTTK_VERSION = "2.7.4"
EMA_URL = (
    "https://www.ema.europa.eu/en/documents/other/"
    "appendix-1-acceptable-intakes-established-n-nitrosamines_en.xlsx"
)

HTTK_PARAM_COLUMNS = [
    "Compound",
    "CAS",
    "DTXSID",
    "Human.Clint",
    "Human.Clint.Reference",
    "Human.Funbound.plasma",
    "Human.Funbound.plasma.Reference",
]

EMA_COLUMNS = {
    "Name": "name",
    "IUPAC name": "iupac_name",
    "SMILES": "smiles",
    "CAS RN": "cas",
    "Synonym/ Acronym": "synonym",
    "Source": "source_drug",
    "CPCA Category": "cpca_category",
    "AI (ng/day)": "ai_ng_per_day",
    "Note": "note",
    "Publication date": "publication_date",
}


class ChecksumMismatch(Exception):
    """A pinned download no longer matches its expected hash; refuse to use it."""


@dataclass(frozen=True)
class RemoteFile:
    name: str
    urls: tuple[str, ...]  # tried in order; CRAN moves superseded versions to its archive
    sha256: str | None  # None when the publisher updates the file in place (EMA)
    licence: str


SOURCES = [
    RemoteFile(
        f"mutagenlou2023/{split}.csv",
        (f"{MUTAGENLOU_BASE}/{path}",),
        sha256,
        "CC BY 4.0",
    )
    for split, path, sha256 in [
        ("train", "train_test/train.csv",
         "ad0d4e2850afdc07c130c3679cc8ae2ad9f7c80999158325d8de986c39f950e1"),
        ("test", "train_test/test.csv",
         "08786199fbbdb6db614d5f65a5abdfcd26d882f0cc844bbeb4ccfa241127b394"),
        ("validation", "validation/validation.csv",
         "8bb6819cd2470369051b5fe231822805bad1611af5b9a8e49b9a35f20adff840"),
    ]
] + [
    RemoteFile(
        f"httk/httk_{HTTK_VERSION}.tar.gz",
        (
            f"https://cran.r-project.org/src/contrib/httk_{HTTK_VERSION}.tar.gz",
            f"https://cran.r-project.org/src/contrib/Archive/httk/httk_{HTTK_VERSION}.tar.gz",
        ),
        "e186171a90d97fe456e7836ec3096719feb49354afd71860df2d2a5c8c4c51b2",
        "GPL-3 (httk R package)",
    ),
    RemoteFile("ema/ema_nitrosamine_ai.xlsx", (EMA_URL,), None, "EMA legal notice"),
]


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, dest: Path) -> None:
    with httpx.stream("GET", url, follow_redirects=True, timeout=120) as resp:
        resp.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("wb") as f:
            for chunk in resp.iter_bytes():
                f.write(chunk)


def fetch(source: RemoteFile, data_dir: Path, force: bool = False) -> dict:
    """Download one file (unless present), verify its hash, and return its manifest entry."""
    dest = data_dir / "raw" / source.name
    used_url = None
    if force or not dest.exists():
        errors = []
        for url in source.urls:
            try:
                download(url, dest)
                used_url = url
                break
            except httpx.HTTPError as exc:
                errors.append(f"{url}: {exc}")
        else:
            raise RuntimeError(f"could not download {source.name}: {errors}")

    actual = sha256_of(dest)
    if source.sha256 and actual != source.sha256:
        raise ChecksumMismatch(f"{source.name}: expected {source.sha256}, got {actual}")
    return {
        "file": f"raw/{source.name}",
        "url": used_url or source.urls[0],
        "sha256": actual,
        "pinned": source.sha256 is not None,
        "licence": source.licence,
        "retrieved_at": datetime.fromtimestamp(dest.stat().st_mtime, UTC).isoformat(),
    }


def ema_revision(xlsx: Path) -> str | None:
    """The EMA document reference (e.g. 'EMA/CHMP/219920/2026/Rev. 14') from the sheet preamble."""
    preamble = pd.read_excel(xlsx, sheet_name=0, header=None, nrows=20)
    for value in preamble.stack():
        if isinstance(value, str) and "Rev." in value:
            return value.strip()
    return None


def parse_ema(xlsx: Path) -> pd.DataFrame:
    """Flatten both EMA sheets into one table; the header row sits below a free-text preamble."""
    frames = []
    for sheet, raw in pd.read_excel(xlsx, sheet_name=None, header=None).items():
        header_rows = raw.index[raw.apply(lambda r: r.astype(str).eq("SMILES").any(), axis=1)]
        if header_rows.empty:
            continue
        header = header_rows[0]
        table = raw.iloc[header + 1 :].copy()
        table.columns = raw.iloc[header].astype(str).str.strip()
        table = table[[c for c in EMA_COLUMNS if c in table.columns]].rename(columns=EMA_COLUMNS)
        table = table.dropna(subset=["name"])
        table["sheet"] = sheet
        frames.append(table)
    return pd.concat(frames, ignore_index=True)


def build_mutagen_index(raw_dir: Path) -> pd.DataFrame:
    """One row per parseable MutagenLou2023 compound with its InChIKey, label and split.

    InChIKeys make exact identity lookups possible (fingerprint similarity cannot: see
    docs/discovery-notes.md on the PFOA/PFDA collision).
    """
    frames = []
    for split in ("train", "test", "validation"):
        df = pd.read_csv(raw_dir / f"{split}.csv")
        frames.append(pd.DataFrame({
            "smiles": df["SMILES"],
            "is_mutagen": df["Y"].astype(int),
            "split": split,
        }))
    index = pd.concat(frames, ignore_index=True)
    index["inchikey"] = index["smiles"].map(inchikey)
    return index.dropna(subset=["inchikey"])


def extract_httk_tables(tarball: Path) -> dict[str, pd.DataFrame]:
    """Read the two httk tables ToxiTrace needs from the package's Tables.RData."""
    import rdata  # only needed at setup

    with tarfile.open(tarball) as tar:
        member = tar.extractfile("httk/data/Tables.RData")
        if member is None:
            raise RuntimeError("httk/data/Tables.RData missing from tarball")
        tables = rdata.read_rda(member)
    return {
        "httk_chem_params": tables["chem.physical_and_invitro.data"][HTTK_PARAM_COLUMNS],
        "httk_pfas_clearance": tables["pfas.clearance"],
    }


def prepare(data_dir: Path, force: bool = False) -> dict:
    manifest = {"created_at": datetime.now(UTC).isoformat(), "sources": {}, "derived": {}}
    for source in SOURCES:
        manifest["sources"][source.name] = fetch(source, data_dir, force)
        print(f"ok  {source.name}")

    derived = data_dir / "derived"
    derived.mkdir(parents=True, exist_ok=True)

    ema_xlsx = data_dir / "raw" / "ema/ema_nitrosamine_ai.xlsx"
    ema = parse_ema(ema_xlsx)
    ema["inchikey"] = ema["smiles"].map(lambda smi: inchikey(smi) if isinstance(smi, str) else None)
    ema.to_csv(derived / "ema_nitrosamine_ai.csv", index=False)
    manifest["sources"]["ema/ema_nitrosamine_ai.xlsx"]["revision"] = ema_revision(ema_xlsx)

    httk_tarball = data_dir / "raw" / f"httk/httk_{HTTK_VERSION}.tar.gz"
    manifest["sources"][f"httk/httk_{HTTK_VERSION}.tar.gz"]["version"] = HTTK_VERSION
    for name, table in extract_httk_tables(httk_tarball).items():
        table.to_csv(derived / f"{name}.csv", index=False)

    build_mutagen_index(data_dir / "raw" / "mutagenlou2023").to_csv(
        derived / "mutagenlou2023_index.csv", index=False
    )

    for path in sorted(derived.glob("*.csv")):
        manifest["derived"][path.name] = {"sha256": sha256_of(path), "rows": len(pd.read_csv(path))}
        print(f"ok  derived/{path.name}")

    (data_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--force", action="store_true", help="re-download even if files exist")
    parser.add_argument("--data-dir", type=Path, default=settings.data_dir)
    args = parser.parse_args()
    prepare(args.data_dir, args.force)
    print(f"manifest written to {args.data_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()
