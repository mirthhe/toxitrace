import pytest

from app.chem import classify_input, connectivity_block, inchikey, is_valid_cas


@pytest.mark.parametrize("text, expected", [
    ("62-75-9", "cas"),
    ("DTXSID7021029", "dtxsid"),
    ("CN(C)N=O", "smiles"),
    ("O=NN1CC2CC(C1)c1cc3nccnc3cc12", "smiles"),
    ("N-nitroso-varenicline", "name"),
    ("perfluorooctanoic acid", "name"),
])
def test_classify_input(text, expected):
    assert classify_input(text) == expected


@pytest.mark.parametrize("cas, valid", [
    ("62-75-9", True),        # NDMA
    ("335-67-1", True),       # PFOA
    ("2755871-02-2", True),   # N-nitroso-varenicline
    ("62-75-8", False),       # wrong check digit
])
def test_cas_check_digit(cas, valid):
    assert is_valid_cas(cas) is valid


def test_inchikey_matches_registry_value():
    assert inchikey("CN(C)N=O") == "UMFJAHHVKNCGLG-UHFFFAOYSA-N"  # DSSTox and PubChem agree


def test_unparseable_smiles_has_no_inchikey():
    assert inchikey("C1CC") is None


def test_pfda_and_pfoa_differ_by_inchikey_despite_similar_fingerprints():
    """Morgan r2 gives these Tanimoto 1.0 (docs/discovery-notes.md); identity must not."""
    pfoa = inchikey("OC(=O)" + "C(F)(F)" * 6 + "C(F)(F)F")
    pfda = inchikey("OC(=O)" + "C(F)(F)" * 8 + "C(F)(F)F")
    assert connectivity_block(pfoa) != connectivity_block(pfda)
