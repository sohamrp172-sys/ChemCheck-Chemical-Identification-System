"""
PubChem PUG-REST fallback for ChemCheck.

When a local database search yields no results, this module queries the
PubChem PUG-REST API to fetch compound data, caches results locally,
and returns ChemicalRecord objects compatible with the rest of the system.
"""

from __future__ import annotations

import json
import os
import time
from typing import Optional
from urllib.parse import quote

import requests

from src.models.chemical_schema import (
    ChemicalRecord,
    PhysicalProperties,
    SafetyInfo,
)


# ── Constants ──────────────────────────────────────────────────────────────

PUBCHEM_BASE_URL = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound"
REQUEST_TIMEOUT = 10  # seconds
CACHE_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "pubchem_cache.json")

# PubChem property identifiers we request in a single call
_PROPERTIES = ",".join([
    "Title",
    "IUPACName",
    "MolecularFormula",
    "MolecularWeight",
    "CanonicalSMILES",
    "IsomericSMILES",
    "InChIKey",
    "XLogP",
    "MonoisotopicMass",
    "HBondDonorCount",
    "HBondAcceptorCount",
    "RotatableBondCount",
    "ExactMass",
    "TPSA",
    "Complexity",
    "Charge",
    "CID",
])


# ── In-memory and file cache ───────────────────────────────────────────────

class _Cache:
    """Simple in-memory + JSON file cache for PubChem records."""

    def __init__(self, cache_path: str = CACHE_FILE) -> None:
        self._path = cache_path
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if os.path.exists(self._path):
            try:
                with open(self._path, encoding="utf-8") as fh:
                    self._data = json.load(fh)
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def _save(self) -> None:
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, ensure_ascii=False)
        except OSError:
            pass  # Cache write failure is non-fatal

    def get(self, key: str) -> Optional[dict]:
        return self._data.get(key.lower())

    def set(self, key: str, value: dict) -> None:
        self._data[key.lower()] = value
        self._save()

    def __contains__(self, key: str) -> bool:
        return key.lower() in self._data


_cache = _Cache()


# ── PubChem API helpers ────────────────────────────────────────────────────

def _get_cid_by_name(name: str) -> Optional[int]:
    """Resolve a compound name to its PubChem CID."""
    url = f"{PUBCHEM_BASE_URL}/name/{quote(name)}/cids/JSON"
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        cids = data.get("IdentifierList", {}).get("CID", [])
        return cids[0] if cids else None
    except requests.Timeout:
        print(f"[pubchem] Timeout resolving name: {name!r}")
    except requests.RequestException as exc:
        print(f"[pubchem] Request error for name {name!r}: {exc}")
    return None


def _get_cid_by_formula(formula: str) -> Optional[int]:
    """Resolve a molecular formula to its most-common PubChem CID."""
    url = f"{PUBCHEM_BASE_URL}/formula/{quote(formula)}/cids/JSON?MaxRecords=1"
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        cids = data.get("IdentifierList", {}).get("CID", [])
        return cids[0] if cids else None
    except requests.Timeout:
        print(f"[pubchem] Timeout resolving formula: {formula!r}")
    except requests.RequestException as exc:
        print(f"[pubchem] Request error for formula {formula!r}: {exc}")
    return None


def _fetch_properties_by_cid(cid: int) -> Optional[dict]:
    """Fetch a property table for the given PubChem CID."""
    url = f"{PUBCHEM_BASE_URL}/cid/{cid}/property/{_PROPERTIES}/JSON"
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        props_list = data.get("PropertyTable", {}).get("Properties", [])
        return props_list[0] if props_list else None
    except requests.Timeout:
        print(f"[pubchem] Timeout fetching properties for CID {cid}")
    except requests.RequestException as exc:
        print(f"[pubchem] Request error fetching CID {cid}: {exc}")
    return None


def _fetch_synonyms_by_cid(cid: int, limit: int = 5) -> list[str]:
    """Fetch synonym list for a CID (first N entries)."""
    url = f"{PUBCHEM_BASE_URL}/cid/{cid}/synonyms/JSON"
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        syns = data.get("InformationList", {}).get("Information", [{}])[0].get("Synonym", [])
        return syns[:limit]
    except (requests.RequestException, IndexError, KeyError):
        return []


def _build_record_from_pubchem(props: dict, synonyms: list[str]) -> ChemicalRecord:
    """
    Construct a ChemicalRecord from a PubChem property dict.

    Fields that PubChem does not supply are filled with sensible defaults so
    that the record is valid and usable by the rest of the system.
    """
    cid = props.get("CID", 0)
    title = props.get("Title", "Unknown")
    iupac = props.get("IUPACName", title)
    formula = props.get("MolecularFormula", "")
    mw = float(props.get("MolecularWeight", 0.0) or 0.0)
    smiles = props.get("IsomericSMILES") or props.get("CanonicalSMILES", "")

    common_uses = synonyms[:3] if synonyms else []

    physical = PhysicalProperties(
        molar_mass=mw,
        melting_point_c=None,
        boiling_point_c=None,
        density_g_cm3=None,
        appearance="Not available from PubChem",
        state="unknown",
        water_solubility="Not available from PubChem",
    )

    safety = SafetyInfo(
        ghs_signal_word="",
        ghs_pictograms=[],
        h_statements=[],
        p_statements=[],
        nfpa_704={"health": 0, "flammability": 0, "instability": 0, "special": ""},
        sds_summary=(
            "Safety data was not retrieved from PubChem. "
            "Consult the official SDS before handling this compound."
        ),
    )

    return ChemicalRecord(
        id=f"pubchem_{cid}",
        name=title,
        iupac_name=iupac,
        formula=formula,
        cas_number="",
        smiles=smiles,
        common_uses=common_uses,
        properties=physical,
        safety=safety,
    )


# ── Public API ─────────────────────────────────────────────────────────────

def lookup_by_name(name: str) -> Optional[ChemicalRecord]:
    """
    Look up a compound by name via PubChem, with caching.

    Args:
        name: Common or IUPAC name to search.

    Returns:
        ChemicalRecord if found, None otherwise.
    """
    cache_key = f"name:{name.lower()}"
    if cache_key in _cache:
        print(f"[pubchem] Cache hit for {name!r}")
        return ChemicalRecord(**_cache.get(cache_key))  # type: ignore[arg-type]

    cid = _get_cid_by_name(name)
    if cid is None:
        return None

    return _fetch_and_cache(cid, cache_key)


def lookup_by_formula(formula: str) -> Optional[ChemicalRecord]:
    """
    Look up a compound by molecular formula via PubChem, with caching.

    Args:
        formula: Molecular formula string (e.g., "C6H12O6").

    Returns:
        ChemicalRecord if found, None otherwise.
    """
    cache_key = f"formula:{formula.lower()}"
    if cache_key in _cache:
        print(f"[pubchem] Cache hit for formula {formula!r}")
        return ChemicalRecord(**_cache.get(cache_key))  # type: ignore[arg-type]

    cid = _get_cid_by_formula(formula)
    if cid is None:
        return None

    return _fetch_and_cache(cid, cache_key)


def lookup_by_cid(cid: int) -> Optional[ChemicalRecord]:
    """
    Fetch a compound directly by PubChem CID, with caching.

    Args:
        cid: PubChem Compound ID integer.

    Returns:
        ChemicalRecord if found, None otherwise.
    """
    cache_key = f"cid:{cid}"
    if cache_key in _cache:
        print(f"[pubchem] Cache hit for CID {cid}")
        return ChemicalRecord(**_cache.get(cache_key))  # type: ignore[arg-type]

    return _fetch_and_cache(cid, cache_key)


def _fetch_and_cache(cid: int, cache_key: str) -> Optional[ChemicalRecord]:
    """Fetch properties + synonyms for cid, build record, and cache it."""
    props = _fetch_properties_by_cid(cid)
    if props is None:
        return None

    synonyms = _fetch_synonyms_by_cid(cid)
    record = _build_record_from_pubchem(props, synonyms)

    # Cache as raw dict for serialisation
    _cache.set(cache_key, record.model_dump())
    print(f"[pubchem] Fetched and cached: {record.name} (CID {cid})")
    return record


def search(query: str) -> Optional[ChemicalRecord]:
    """
    General-purpose PubChem search.

    Tries name lookup first, falls back to formula lookup if the query
    looks like a molecular formula (starts with an uppercase element symbol
    followed by digits or another element).

    Args:
        query: Free-text name or formula string.

    Returns:
        ChemicalRecord if found, None otherwise.
    """
    import re

    # Heuristic: if it looks like a formula (H2O, NaCl, C6H12O6 …)
    if re.match(r"^[A-Z][a-z]?\d*([A-Z(]|$)", query.strip()):
        result = lookup_by_formula(query)
        if result:
            return result

    return lookup_by_name(query)


def clear_cache() -> None:
    """Remove all cached PubChem entries (in-memory and file)."""
    _cache._data.clear()
    _cache._save()
    print("[pubchem] Cache cleared.")
