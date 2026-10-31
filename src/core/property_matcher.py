"""
Property comparator for ChemCheck.

Compares experimentally measured properties against reference ChemicalRecord
data and scores candidate likelihood on a 0–100 scale.
"""

from __future__ import annotations

import re
from typing import Optional

from src.models.chemical_schema import ChemicalRecord, MeasuredProperties, MatchResult


# ── Default tolerances ─────────────────────────────────────────────────────
DEFAULT_TOLERANCES: dict[str, float] = {
    "melting_point": 5.0,   # ±5 % relative error
    "boiling_point": 5.0,   # ±5 % relative error
    "density": 10.0,        # ±10 % relative error
}

# Keywords used for appearance text matching (canonical → variants)
_APPEARANCE_KEYWORDS: dict[str, list[str]] = {
    "white": ["white", "colorless", "colourless", "pale", "off-white", "cream"],
    "clear": ["clear", "colorless", "colourless", "transparent"],
    "yellow": ["yellow", "amber", "golden", "straw"],
    "blue": ["blue", "azure", "cyan"],
    "green": ["green", "teal", "olive"],
    "purple": ["purple", "violet", "magenta"],
    "pink": ["pink", "rose", "fuchsia"],
    "red": ["red", "scarlet", "crimson"],
    "brown": ["brown", "tan", "ochre"],
    "black": ["black", "dark", "charcoal"],
    "crystalline": ["crystalline", "crystal", "crystals"],
    "powder": ["powder", "powdered", "granular", "granules", "fine"],
    "solid": ["solid"],
    "liquid": ["liquid", "viscous", "oily", "syrupy"],
    "gas": ["gas", "gaseous", "vapour", "vapor"],
    "fuming": ["fuming", "fumes"],
    "lustrous": ["lustrous", "shiny", "metallic"],
    "odorless": ["odorless", "odourless", "no odor"],
    "odor": ["odor", "odour", "smell", "fragrant", "pungent", "characteristic"],
}


def _tokenize(text: str) -> set[str]:
    """Extract lower-case word tokens from a text string."""
    return set(re.findall(r"[a-z]+", text.lower()))


def _appearance_score(reference: str, observed: str) -> float:
    """
    Return a 0–1 similarity score for two appearance strings.

    Matching strategy:
    1. Exact canonical keywords that appear in both strings score points.
    2. The score is the fraction of reference keyword groups hit by the
       observed text, capped at 1.0.
    """
    ref_tokens = _tokenize(reference)
    obs_tokens = _tokenize(observed)

    # Expand tokens through keyword synonyms
    def expand(tokens: set[str]) -> set[str]:
        groups: set[str] = set()
        for canonical, variants in _APPEARANCE_KEYWORDS.items():
            if tokens & set(variants):
                groups.add(canonical)
        return groups

    ref_groups = expand(ref_tokens)
    obs_groups = expand(obs_tokens)

    if not ref_groups:
        # No structured keywords – fall back to direct token overlap
        if not ref_tokens:
            return 0.0
        overlap = len(ref_tokens & obs_tokens)
        return min(overlap / len(ref_tokens), 1.0)

    matches = len(ref_groups & obs_groups)
    return matches / len(ref_groups)


def _state_match(reference: str, observed: str) -> bool:
    """Return True if both states map to the same canonical category."""
    _MAP = {
        "solid": "solid",
        "powder": "solid",
        "crystal": "solid",
        "liquid": "liquid",
        "solution": "liquid",
        "fluid": "liquid",
        "gas": "gas",
        "gaseous": "gas",
        "vapour": "gas",
        "vapor": "gas",
    }
    ref_canonical = _MAP.get(reference.strip().lower(), reference.strip().lower())
    obs_canonical = _MAP.get(observed.strip().lower(), observed.strip().lower())
    return ref_canonical == obs_canonical


def _property_detail(
    prop_name: str,
    reference: Optional[float],
    measured: Optional[float],
    tolerance_pct: float,
) -> dict:
    """
    Build a detail dict for a single numeric property comparison.

    Returns a dict with:
        - reference_value
        - measured_value
        - relative_error_pct
        - within_tolerance
        - score_contribution   (0.0 – 1.0)
        - tolerance_pct
    """
    if measured is None or reference is None:
        return {
            "reference_value": reference,
            "measured_value": measured,
            "relative_error_pct": None,
            "within_tolerance": None,
            "score_contribution": None,
            "tolerance_pct": tolerance_pct,
            "note": "Skipped (value not provided)",
        }

    if reference == 0.0:
        rel_error = abs(measured) * 100.0  # special case
    else:
        rel_error = abs(measured - reference) / abs(reference) * 100.0

    within = rel_error <= tolerance_pct

    # Score decays linearly from 1.0 (perfect match) to 0.0 at 3× tolerance
    if within:
        score = 1.0 - (rel_error / tolerance_pct) * 0.2  # up to 20% penalty inside tolerance
    else:
        excess = rel_error - tolerance_pct
        penalty = excess / (tolerance_pct * 2)
        score = max(0.0, 0.8 - penalty)

    return {
        "reference_value": reference,
        "measured_value": measured,
        "relative_error_pct": round(rel_error, 3),
        "within_tolerance": within,
        "score_contribution": round(score, 4),
        "tolerance_pct": tolerance_pct,
    }


def compare_measurements(
    candidate: ChemicalRecord,
    measurements: MeasuredProperties,
    tolerances: Optional[dict[str, float]] = None,
) -> MatchResult:
    """
    Compare measured experimental properties against a candidate ChemicalRecord.

    Args:
        candidate: Reference ChemicalRecord from the database.
        measurements: Experimentally measured properties.
        tolerances: Optional dict with keys 'melting_point', 'boiling_point',
                    'density' specifying percentage tolerance thresholds.
                    Defaults to DEFAULT_TOLERANCES.

    Returns:
        MatchResult with confidence_score (0–100) and per-property details.
    """
    tol = {**DEFAULT_TOLERANCES, **(tolerances or {})}
    details: dict = {}
    score_parts: list[float] = []
    weight_parts: list[float] = []

    props = candidate.properties

    # ── Melting point ──────────────────────────────────────────────────────
    mp_detail = _property_detail(
        "melting_point",
        props.melting_point_c,
        measurements.measured_melting_point,
        tol["melting_point"],
    )
    details["melting_point"] = mp_detail
    if mp_detail["score_contribution"] is not None:
        score_parts.append(mp_detail["score_contribution"])
        weight_parts.append(1.0)

    # ── Boiling point ──────────────────────────────────────────────────────
    bp_detail = _property_detail(
        "boiling_point",
        props.boiling_point_c,
        measurements.measured_boiling_point,
        tol["boiling_point"],
    )
    details["boiling_point"] = bp_detail
    if bp_detail["score_contribution"] is not None:
        score_parts.append(bp_detail["score_contribution"])
        weight_parts.append(1.0)

    # ── Density ────────────────────────────────────────────────────────────
    den_detail = _property_detail(
        "density",
        props.density_g_cm3,
        measurements.measured_density,
        tol["density"],
    )
    details["density"] = den_detail
    if den_detail["score_contribution"] is not None:
        score_parts.append(den_detail["score_contribution"])
        weight_parts.append(1.0)

    # ── Appearance (text-based) ────────────────────────────────────────────
    if measurements.observed_appearance is not None:
        app_score = _appearance_score(props.appearance, measurements.observed_appearance)
        details["appearance"] = {
            "reference_value": props.appearance,
            "measured_value": measurements.observed_appearance,
            "similarity_score": round(app_score, 4),
            "note": "Text-based keyword similarity",
        }
        score_parts.append(app_score)
        weight_parts.append(0.5)  # lower weight than numeric properties

    # ── State ──────────────────────────────────────────────────────────────
    if measurements.observed_state is not None:
        state_ok = _state_match(props.state, measurements.observed_state)
        state_score = 1.0 if state_ok else 0.0
        details["state"] = {
            "reference_value": props.state,
            "measured_value": measurements.observed_state,
            "match": state_ok,
            "score_contribution": state_score,
        }
        score_parts.append(state_score)
        weight_parts.append(0.5)

    # ── Aggregate score ────────────────────────────────────────────────────
    if not score_parts:
        # No measurements provided – return neutral score
        confidence = 50.0
    else:
        total_weight = sum(weight_parts)
        weighted_sum = sum(s * w for s, w in zip(score_parts, weight_parts))
        # Clamp strictly to [0.0, 100.0] to satisfy Pydantic ge/le constraints
        confidence = max(0.0, min(100.0, round((weighted_sum / total_weight) * 100.0, 2)))

    details["summary"] = {
        "properties_compared": len(score_parts),
        "average_score": round(confidence, 2),
    }

    return MatchResult(
        candidate=candidate,
        confidence_score=confidence,
        property_match_details=details,
    )


def rank_candidates(
    candidates: list[ChemicalRecord],
    measurements: MeasuredProperties,
    tolerances: Optional[dict[str, float]] = None,
    top_n: int = 5,
) -> list[MatchResult]:
    """
    Score and rank multiple candidates against the measured properties.

    Args:
        candidates: List of ChemicalRecord objects to evaluate.
        measurements: Experimentally measured properties.
        tolerances: Optional custom tolerance overrides.
        top_n: Maximum number of results to return (sorted by score descending).

    Returns:
        Sorted list of MatchResult objects (best match first).
    """
    results = [
        compare_measurements(candidate, measurements, tolerances)
        for candidate in candidates
    ]
    results.sort(key=lambda r: r.confidence_score, reverse=True)
    return results[:top_n]
