import pandas as pd
import pytest

from app import reference_data
from app.reference_data import ChecksumMismatch, RemoteFile, ema_revision, fetch, parse_ema

EMA_HEADER = ["Structure", "Name", "IUPAC name", "SMILES", "CAS RN", "Synonym/ Acronym",
              "Source", "CPCA Category", "AI (ng/day)", "Note", "Publication date"]


def write_ema_like_xlsx(path):
    """Mimic the EMA layout: free-text preamble, a header row further down, then data."""
    preamble = [["2026-10-01"], ["EMA/CHMP/219920/2026/Rev. 14"], [None], ["Acceptable intakes"]]
    rows = [
        [None, "N-nitroso-varenicline", "iupac", "C1C2CN(CC1C3=CC4=NC=CN=C4C=C23)N=O",
         "2755871-02-2", "NNV", "Varenicline", 3, 400, None, "2021-09-01"],
        [None, "N-nitroso-dimethylamine", "iupac", "CN(C)N=O", "62-75-9", "NDMA", None, None, 96,
         "TD50-based", "2020-06-01"],
        [None] * 11,  # trailing blank row
    ]
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame(preamble + [EMA_HEADER] + rows).to_excel(
            writer, sheet_name="N-nitrosamines", header=False, index=False
        )
        pd.DataFrame([["no table on this sheet"]]).to_excel(
            writer, sheet_name="Notes", header=False, index=False
        )


def test_parse_ema_finds_header_below_preamble(tmp_path):
    xlsx = tmp_path / "ema.xlsx"
    write_ema_like_xlsx(xlsx)

    table = parse_ema(xlsx)

    assert list(table["name"]) == ["N-nitroso-varenicline", "N-nitroso-dimethylamine"]
    nnv = table.iloc[0]
    assert nnv["cas"] == "2755871-02-2"
    assert nnv["cpca_category"] == 3
    assert nnv["ai_ng_per_day"] == 400
    assert nnv["sheet"] == "N-nitrosamines"


def test_ema_revision_read_from_preamble(tmp_path):
    xlsx = tmp_path / "ema.xlsx"
    write_ema_like_xlsx(xlsx)

    assert ema_revision(xlsx) == "EMA/CHMP/219920/2026/Rev. 14"


def test_fetch_rejects_changed_pinned_file(tmp_path, monkeypatch):
    monkeypatch.setattr(reference_data, "download", lambda url, dest: (
        dest.parent.mkdir(parents=True, exist_ok=True), dest.write_bytes(b"tampered")
    ))
    source = RemoteFile("x/file.csv", ("https://example.org/file.csv",), "0" * 64, "test")

    with pytest.raises(ChecksumMismatch):
        fetch(source, tmp_path)


def test_fetch_records_unpinned_file_without_failing(tmp_path, monkeypatch):
    monkeypatch.setattr(reference_data, "download", lambda url, dest: (
        dest.parent.mkdir(parents=True, exist_ok=True), dest.write_bytes(b"content")
    ))
    source = RemoteFile("x/file.xlsx", ("https://example.org/file.xlsx",), None, "test")

    entry = fetch(source, tmp_path)

    assert entry["pinned"] is False
    assert entry["sha256"] == reference_data.sha256_of(tmp_path / "raw/x/file.xlsx")
