"""Local cheminformatics with RDKit: input classification and structure identity."""

import re

from rdkit import Chem, RDLogger

from app.schemas import InputType

RDLogger.DisableLog("rdApp.*")

CAS_PATTERN = re.compile(r"^(\d{2,7})-(\d{2})-(\d)$")
DTXSID_PATTERN = re.compile(r"^DTXSID\d+$", re.IGNORECASE)


def is_valid_cas(text: str) -> bool:
    """CAS numbers carry a check digit: weighted sum of the other digits, mod 10."""
    match = CAS_PATTERN.match(text)
    if not match:
        return False
    digits = (match.group(1) + match.group(2))[::-1]
    checksum = sum(i * int(d) for i, d in enumerate(digits, start=1)) % 10
    return checksum == int(match.group(3))


def parse_smiles(text: str) -> Chem.Mol | None:
    if not text or any(c.isspace() for c in text):
        return None
    return Chem.MolFromSmiles(text)


def classify_input(text: str) -> InputType:
    """CAS and DTXSID have strict formats; anything RDKit parses is SMILES; the rest is a name.

    A few short names are also valid SMILES (e.g. "CO"); treating them as structures is the
    safer reading, because the structure is then shown back to the user.
    """
    text = text.strip()
    if CAS_PATTERN.match(text):
        return "cas"
    if DTXSID_PATTERN.match(text):
        return "dtxsid"
    if parse_smiles(text) is not None:
        return "smiles"
    return "name"


def inchikey(smiles: str) -> str | None:
    mol = parse_smiles(smiles)
    return Chem.MolToInchiKey(mol) if mol is not None else None


def connectivity_block(key: str) -> str:
    """First InChIKey block: the molecular skeleton, ignoring stereo, isotopes and protonation."""
    return key.split("-")[0]
