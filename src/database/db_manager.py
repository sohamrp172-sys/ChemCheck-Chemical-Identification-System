"""
In-memory chemical database manager for ChemCheck.

Loads chemicals.json on startup, builds indices for fast exact lookup,
and provides fuzzy string search using difflib (or thefuzz if available).
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Optional

from src.models.chemical_schema import ChemicalRecord

try:
    from thefuzz import fuzz as _fuzz  # type: ignore
    _HAS_THEFUZZ = True
except ImportError:
    _HAS_THEFUZZ = False


# ── Path resolution ────────────────────────────────────────────────────────
_DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "chemicals.json"
)


# ── Normalisation helpers ──────────────────────────────────────────────────

def _normalize_name(name: str) -> str:
    """Lowercase, strip accents, collapse whitespace."""
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_str.lower().strip())


def _normalize_formula(formula: str) -> str:
    """Lowercase formula for case-insensitive matching."""
    return formula.strip().lower()


def _normalize_cas(cas: str) -> str:
    """Remove hyphens and strip whitespace from CAS numbers."""
    return re.sub(r"[-\s]", "", cas.strip())


def _similarity_score(a: str, b: str) -> float:
    """
    Return a 0–100 fuzzy similarity score between two strings.

    Uses thefuzz.fuzz.token_sort_ratio if available, otherwise
    falls back to difflib.SequenceMatcher.
    """
    if _HAS_THEFUZZ:
        return float(_fuzz.token_sort_ratio(a, b))
    ratio = SequenceMatcher(None, a, b).ratio()
    return ratio * 100.0


# ── Database Manager ───────────────────────────────────────────────────────

class ChemicalDatabase:
    """
    In-memory chemical database with indexed lookups and fuzzy search.

    Attributes:
        chemicals: List of all loaded ChemicalRecord objects.
        similarity_threshold: Minimum similarity score (0–100) for fuzzy hits.
    """

    def __init__(
        self,
        db_path: str = _DEFAULT_DB_PATH,
        similarity_threshold: float = 65.0,
    ) -> None:
        self.db_path = db_path
        self.similarity_threshold = similarity_threshold
        self.chemicals: list[ChemicalRecord] = []

        # Indices
        self._by_formula: dict[str, ChemicalRecord] = {}
        self._by_name: dict[str, ChemicalRecord] = {}
        self._by_cas: dict[str, ChemicalRecord] = {}

        self._load()

    # ── Loading ────────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Load chemicals from JSON file and build all indices."""
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(
                f"Chemical database not found at {self.db_path}. "
                "Run data/seed_data.py to generate it."
            )

        with open(self.db_path, encoding="utf-8") as fh:
            raw: list[dict] = json.load(fh)

        self.chemicals = [ChemicalRecord(**record) for record in raw]
        self._build_indices()
        print(f"[db_manager] Loaded {len(self.chemicals)} chemicals from {self.db_path}")

    def _build_indices(self) -> None:
        """Build exact-match indices for fast lookup."""
        self._by_formula.clear()
        self._by_name.clear()
        self._by_cas.clear()

        for record in self.chemicals:
            # Formula index (normalised Hill order, case-insensitive)
            norm_formula = _normalize_formula(record.formula)
            self._by_formula[norm_formula] = record

            # Name index
            self._by_name[_normalize_name(record.name)] = record

            # IUPAC name index
            self._by_name[_normalize_name(record.iupac_name)] = record

            # CAS index
            self._by_cas[_normalize_cas(record.cas_number)] = record

    def reload(self) -> None:
        """Reload the database from disk (e.g., after adding new records)."""
        self._load()

    # ── Exact lookups ──────────────────────────────────────────────────────

    def get_by_formula(self, formula: str) -> Optional[ChemicalRecord]:
        """Exact formula lookup (case-insensitive)."""
        return self._by_formula.get(_normalize_formula(formula))

    def get_by_name(self, name: str) -> Optional[ChemicalRecord]:
        """Exact name or IUPAC name lookup (case-insensitive)."""
        return self._by_name.get(_normalize_name(name))

    def get_by_cas(self, cas: str) -> Optional[ChemicalRecord]:
        """Exact CAS number lookup (hyphens and spaces ignored)."""
        return self._by_cas.get(_normalize_cas(cas))

    def get_by_id(self, chemical_id: str) -> Optional[ChemicalRecord]:
        """Lookup by internal ID string."""
        for record in self.chemicals:
            if record.id == chemical_id:
                return record
        return None

    # ── Fuzzy search ───────────────────────────────────────────────────────

    def fuzzy_search(
        self,
        query: str,
        threshold: Optional[float] = None,
        limit: int = 10,
    ) -> list[tuple[ChemicalRecord, float]]:
        """
        Fuzzy search across chemical names and IUPAC names.

        Args:
            query: Search string.
            threshold: Minimum similarity score override (0–100).
            limit: Maximum number of results to return.

        Returns:
            List of (ChemicalRecord, score) tuples sorted by score descending.
        """
        min_score = threshold if threshold is not None else self.similarity_threshold
        norm_query = _normalize_name(query)

        scored: list[tuple[ChemicalRecord, float]] = []
        seen_ids: set[str] = set()

        for record in self.chemicals:
            if record.id in seen_ids:
                continue

            best = max(
                _similarity_score(norm_query, _normalize_name(record.name)),
                _similarity_score(norm_query, _normalize_name(record.iupac_name)),
                _similarity_score(norm_query, _normalize_formula(record.formula)),
            )

            if best >= min_score:
                scored.append((record, best))
                seen_ids.add(record.id)

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    # ── Unified search ─────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        threshold: Optional[float] = None,
        limit: int = 10,
    ) -> list[ChemicalRecord]:
        """
        Unified search: tries exact matches first, then falls back to fuzzy.

        Priority order:
        1. Exact CAS number match
        2. Exact name / IUPAC name match
        3. Exact formula match
        4. Fuzzy name/formula match

        Args:
            query: Search string (name, formula, or CAS number).
            threshold: Fuzzy similarity threshold override.
            limit: Maximum fuzzy results.

        Returns:
            List of matching ChemicalRecord objects (may be empty).
        """
        # 1. Exact CAS
        if re.match(r"^\d{1,7}-\d{2}-\d$", query.strip()):
            record = self.get_by_cas(query)
            if record:
                return [record]

        # 2. Exact name
        record = self.get_by_name(query)
        if record:
            return [record]

        # 3. Exact formula
        record = self.get_by_formula(query)
        if record:
            return [record]

        # 4. Fuzzy search
        fuzzy_hits = self.fuzzy_search(query, threshold=threshold, limit=limit)
        return [r for r, _score in fuzzy_hits]

    # ── Convenience ────────────────────────────────────────────────────────

    def all_chemicals(self) -> list[ChemicalRecord]:
        """Return all loaded ChemicalRecord objects."""
        return list(self.chemicals)

    def count(self) -> int:
        """Return the number of loaded chemicals."""
        return len(self.chemicals)

    def add_record(self, record: ChemicalRecord) -> None:
        """
        Add a single ChemicalRecord to the in-memory database and update indices.

        Note: Does not persist to disk; use for runtime additions such as
        PubChem cache entries.
        """
        self.chemicals.append(record)

        norm_formula = _normalize_formula(record.formula)
        self._by_formula[norm_formula] = record
        self._by_name[_normalize_name(record.name)] = record
        self._by_name[_normalize_name(record.iupac_name)] = record
        self._by_cas[_normalize_cas(record.cas_number)] = record


# ── Module-level singleton ─────────────────────────────────────────────────

_db_instance: Optional[ChemicalDatabase] = None


def get_database(
    db_path: str = _DEFAULT_DB_PATH,
    similarity_threshold: float = 65.0,
) -> ChemicalDatabase:
    """
    Return the module-level ChemicalDatabase singleton.

    Creates and initialises the instance on first call.
    """
    global _db_instance
    if _db_instance is None:
        _db_instance = ChemicalDatabase(
            db_path=db_path,
            similarity_threshold=similarity_threshold,
        )
    return _db_instance
