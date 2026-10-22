"""Rule R1: establish which substance we are talking about, from two independent registries.

DSSTox (via ToxIndex) is the primary registry because ToxIndex's evidence tools key on it.
PubChem is queried independently and compared by InChIKey. A substance missing from DSSTox
is a finding, not an error: the structure can still come from the user's SMILES or PubChem.
"""

from app import chem
from app.adapters import pubchem, toxindex
from app.schemas import Candidate, Flag, Identity
from app.trace import Tracer


class InvalidInput(Exception):
    """The input can be rejected before any lookup (FR-01)."""


def _candidate(match: dict) -> Candidate:
    return Candidate(
        name=match.get("name"),
        dtxsid=match.get("dtxsid"),
        cas=match.get("cas"),
        inchikey=match.get("inchikey"),
        smiles=match.get("smiles"),
        formula=match.get("formula"),
    )


async def resolve_identity(text: str, tracer: Tracer) -> tuple[Identity, list[Flag]]:
    text = text.strip()
    if not text:
        raise InvalidInput("Enter a chemical name, CAS number, DTXSID or SMILES.")
    input_type = chem.classify_input(text)
    if input_type == "cas" and not chem.is_valid_cas(text):
        raise InvalidInput(f"{text} is not a valid CAS number (its check digit does not match).")

    flags: list[Flag] = []
    identity = Identity(input=text, input_type=input_type, status="not_found")

    # 1. DSSTox via ToxIndex.
    dsstox: Candidate | None = None
    try:
        dsstox_ref, body = await toxindex.chemical_identity(text, tracer)
    except toxindex.ToxIndexError as exc:
        dsstox_ref = exc.ref
        flags.append(Flag(rule_id="R1", severity="caution", refs=[exc.ref],
                          message=f"The EPA DSSTox lookup via ToxIndex failed ({exc}); "
                                  "identity rests on the other sources only."))
    else:
        matches = body.get("matches", [])
        if body.get("total", 0) > 1:
            identity.status = "ambiguous"
            identity.candidates = [_candidate(m) for m in matches]
            flags.append(Flag(rule_id="R1", severity="caution", refs=[dsstox_ref],
                              message=f"'{text}' matches {body['total']} substances in EPA DSSTox. "
                                      "Choose one (e.g. by its DTXSID) before analysing."))
            return identity, flags
        if matches:
            dsstox = _candidate(matches[0])
            identity.in_dsstox = True
        else:
            flags.append(Flag(rule_id="R1", severity="caution", refs=[dsstox_ref],
                              message="Not in the EPA DSSTox registry, so ToxIndex's evidence "
                                      "tools cannot look this substance up."))

    # 2. PubChem, independently: by the user's own input where PubChem can search it,
    #    otherwise by the structure we already have.
    smiles = dsstox.smiles if dsstox else (text if input_type == "smiles" else None)
    if input_type in ("name", "cas"):
        pubchem_ref, pubchem_matches = await pubchem.by_name(text, tracer)
    elif smiles and (key := (dsstox.inchikey if dsstox else chem.inchikey(smiles))):
        pubchem_ref, pubchem_matches = await pubchem.by_inchikey(key, tracer)
    else:
        pubchem_ref, pubchem_matches = None, []

    if smiles is None and pubchem_matches:
        skeletons = {chem.connectivity_block(m.inchikey or "") for m in pubchem_matches}
        if len(skeletons) > 1:
            identity.status = "ambiguous"
            identity.candidates = [Candidate(**m.model_dump(exclude={"cid"}))
                                   for m in pubchem_matches]
            flags.append(Flag(rule_id="R1", severity="caution", refs=[pubchem_ref],
                              message=f"'{text}' matches {len(pubchem_matches)} different "
                                      "structures in PubChem. Enter a SMILES or CAS instead."))
            return identity, flags
        smiles = pubchem_matches[0].smiles
        flags.append(Flag(rule_id="R1", severity="info", refs=[pubchem_ref],
                          message="Structure taken from PubChem, not from a regulatory registry."))

    if smiles is None:
        flags.append(Flag(rule_id="R1", severity="caution",
                          refs=[r for r in (dsstox_ref, pubchem_ref) if r],
                          message=f"No structure found for '{text}' in DSSTox or PubChem. "
                                  "Try a CAS number or SMILES."))
        return identity, flags

    # 3. Local InChIKey of the exact structure every downstream step will use.
    local_key = chem.inchikey(smiles)
    local_ref = tracer.record("local", "rdkit inchikey", "ok" if local_key else "error",
                              {"smiles": smiles}, {"inchikey": local_key},
                              error=None if local_key else "RDKit could not parse the structure")
    if local_key is None:
        flags.append(Flag(rule_id="R1", severity="conflict", refs=[local_ref],
                          message="The structure could not be parsed, so it cannot be analysed."))
        return identity, flags

    # 4. Compare the sources.
    flags += _compare(dsstox, pubchem_matches, pubchem_ref, local_key, local_ref)
    agreeing = next((m for m in pubchem_matches if m.inchikey == local_key), None)
    identity.status = "resolved"
    identity.smiles = smiles
    identity.inchikey = local_key
    identity.name = (dsstox.name if dsstox else None) or (agreeing.name if agreeing else None) \
        or (text if input_type == "name" else None)
    identity.dtxsid = dsstox.dtxsid if dsstox else None
    identity.cas = (dsstox.cas if dsstox else None) or (text if input_type == "cas" else None)
    identity.formula = (dsstox.formula if dsstox else None) or (agreeing.formula if agreeing else None)
    identity.pubchem_cid = agreeing.cid if agreeing else None
    return identity, flags


def _compare(
    dsstox: Candidate | None,
    pubchem_matches: list[pubchem.PubChemMatch],
    pubchem_ref: str | None,
    local_key: str,
    local_ref: str,
) -> list[Flag]:
    flags = []
    refs = [r for r in (pubchem_ref, local_ref) if r]

    if dsstox and dsstox.inchikey and dsstox.inchikey != local_key:
        # DSSTox SMILES are "QSAR-ready" (desalted, neutralised), so a different key can be legitimate.
        same_skeleton = chem.connectivity_block(dsstox.inchikey) == chem.connectivity_block(local_key)
        flags.append(Flag(
            rule_id="R1", severity="caution" if same_skeleton else "conflict", refs=refs,
            message=f"DSSTox lists InChIKey {dsstox.inchikey} but its QSAR-ready structure gives "
                    f"{local_key}"
                    + (" (same skeleton; likely a salt or charge form)." if same_skeleton else "."),
        ))

    if not pubchem_matches:
        flags.append(Flag(rule_id="R1", severity="caution", refs=refs,
                          message="Independent identity check unavailable: PubChem returned "
                                  "no match."))
        return flags

    pubchem_keys = [m.inchikey for m in pubchem_matches]
    if local_key in pubchem_keys:
        other = len(pubchem_matches) - 1
        flags.append(Flag(rule_id="R1", severity="info", refs=refs,
                          message=f"Identity confirmed independently: PubChem gives the same "
                                  f"InChIKey ({local_key})."
                                  + (f" PubChem also lists {other} stereo/charge variant(s)."
                                     if other else "")))
    elif chem.connectivity_block(local_key) in {chem.connectivity_block(k or "") for k in pubchem_keys}:
        flags.append(Flag(rule_id="R1", severity="caution", refs=refs,
                          message="PubChem has the same molecular skeleton but a different "
                                  "stereo, isotope or charge form."))
    else:
        flags.append(Flag(rule_id="R1", severity="conflict", refs=refs,
                          message="PubChem resolves this input to a different substance than "
                                  "the structure used here. Check the input before relying on "
                                  "any result."))
    return flags
