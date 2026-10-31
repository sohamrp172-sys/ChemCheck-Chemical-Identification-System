"""
Chemical formula parser for ChemCheck.

Parses molecular formula strings into elemental composition dictionaries
and calculates theoretical molar mass from atomic weights.
"""

from __future__ import annotations

import re
from typing import Optional

# ── Atomic weights (IUPAC 2021 standard) ──────────────────────────────────
ATOMIC_WEIGHTS: dict[str, float] = {
    "H": 1.008,
    "He": 4.002602,
    "Li": 6.94,
    "Be": 9.0121831,
    "B": 10.81,
    "C": 12.011,
    "N": 14.007,
    "O": 15.999,
    "F": 18.998403163,
    "Ne": 20.1797,
    "Na": 22.98976928,
    "Mg": 24.305,
    "Al": 26.9815384,
    "Si": 28.085,
    "P": 30.973761998,
    "S": 32.06,
    "Cl": 35.45,
    "Ar": 39.948,
    "K": 39.0983,
    "Ca": 40.078,
    "Sc": 44.955908,
    "Ti": 47.867,
    "V": 50.9415,
    "Cr": 51.9961,
    "Mn": 54.938043,
    "Fe": 55.845,
    "Co": 58.933194,
    "Ni": 58.6934,
    "Cu": 63.546,
    "Zn": 65.38,
    "Ga": 69.723,
    "Ge": 72.630,
    "As": 74.921595,
    "Se": 78.971,
    "Br": 79.904,
    "Kr": 83.798,
    "Rb": 85.4678,
    "Sr": 87.62,
    "Y": 88.90584,
    "Zr": 91.224,
    "Nb": 92.90637,
    "Mo": 95.95,
    "Ru": 101.07,
    "Rh": 102.90549,
    "Pd": 106.42,
    "Ag": 107.8682,
    "Cd": 112.414,
    "In": 114.818,
    "Sn": 118.710,
    "Sb": 121.760,
    "Te": 127.60,
    "I": 126.90447,
    "Xe": 131.293,
    "Cs": 132.90545196,
    "Ba": 137.327,
    "La": 138.90547,
    "Ce": 140.116,
    "Hg": 200.592,
    "Tl": 204.38,
    "Pb": 207.2,
    "Bi": 208.98040,
    "Ra": 226.0,
    "U": 238.02891,
    "Pt": 195.084,
    "Au": 196.966570,
    "W": 183.84,
    "Re": 186.207,
    "Os": 190.23,
    "Ir": 192.217,
}


class FormulaParseError(ValueError):
    """Raised when a chemical formula cannot be parsed."""


def _parse_segment(formula: str, pos: int) -> tuple[dict[str, int], int]:
    """
    Recursively parse a formula segment, handling nested parentheses.

    Returns (composition_dict, new_position).
    """
    composition: dict[str, int] = {}

    while pos < len(formula):
        char = formula[pos]

        if char == "(":
            # Recurse into parenthesised group
            inner, pos = _parse_segment(formula, pos + 1)
            if pos >= len(formula) or formula[pos] != ")":
                raise FormulaParseError(f"Unmatched '(' in formula: {formula!r}")
            pos += 1  # skip ')'
            # Read multiplier after ')'
            num_start = pos
            while pos < len(formula) and formula[pos].isdigit():
                pos += 1
            multiplier = int(formula[num_start:pos]) if pos > num_start else 1
            for el, cnt in inner.items():
                composition[el] = composition.get(el, 0) + cnt * multiplier

        elif char == ")":
            # End of group – return to caller
            break

        elif char.isupper():
            # Element symbol: one uppercase letter followed by zero or more lowercase
            sym_start = pos
            pos += 1
            while pos < len(formula) and formula[pos].islower():
                pos += 1
            element = formula[sym_start:pos]
            if element not in ATOMIC_WEIGHTS:
                raise FormulaParseError(
                    f"Unknown element symbol {element!r} in formula: {formula!r}"
                )
            # Read atom count
            num_start = pos
            while pos < len(formula) and formula[pos].isdigit():
                pos += 1
            count = int(formula[num_start:pos]) if pos > num_start else 1
            composition[element] = composition.get(element, 0) + count

        elif char.isdigit():
            # Stray digit at top level – skip (handles ionic notation like [Na+])
            pos += 1

        elif char in "[]+-. ":
            # Skip common non-formula characters (charge notation, dots, spaces)
            pos += 1

        else:
            raise FormulaParseError(
                f"Unexpected character {char!r} at position {pos} in formula: {formula!r}"
            )

    return composition, pos


def parse_formula(formula: str) -> dict[str, int]:
    """
    Parse a molecular formula string into an elemental composition dictionary.

    Examples::

        >>> parse_formula("NaCl")
        {'Na': 1, 'Cl': 1}
        >>> parse_formula("H2SO4")
        {'H': 2, 'S': 1, 'O': 4}
        >>> parse_formula("Ca(OH)2")
        {'Ca': 1, 'O': 2, 'H': 2}

    Args:
        formula: Molecular formula string (Hill system recommended).

    Returns:
        Dictionary mapping element symbol → atom count.

    Raises:
        FormulaParseError: If the formula cannot be parsed.
    """
    if not formula or not isinstance(formula, str):
        raise FormulaParseError("Formula must be a non-empty string.")

    # Strip common prefixes/suffixes used in SMILES-adjacent notations
    cleaned = formula.strip()

    composition, _ = _parse_segment(cleaned, 0)

    if not composition:
        raise FormulaParseError(f"No elements found in formula: {formula!r}")

    return composition


def calculate_molar_mass(formula: str) -> float:
    """
    Calculate the theoretical molar mass (g/mol) from a molecular formula.

    Args:
        formula: Molecular formula string.

    Returns:
        Molar mass in g/mol.

    Raises:
        FormulaParseError: If the formula contains unknown elements.
    """
    composition = parse_formula(formula)
    return sum(ATOMIC_WEIGHTS[el] * cnt for el, cnt in composition.items())


def validate_formula_mass(
    formula: str,
    reference_mass: float,
    tolerance_pct: float = 1.0,
) -> tuple[bool, float, float]:
    """
    Validate a formula's theoretical molar mass against a reference value.

    Args:
        formula: Molecular formula string.
        reference_mass: Reference molar mass in g/mol.
        tolerance_pct: Acceptable relative deviation in percent (default 1%).

    Returns:
        Tuple of (is_valid, calculated_mass, relative_error_pct).
    """
    calculated = calculate_molar_mass(formula)
    if reference_mass == 0:
        return False, calculated, float("inf")
    rel_error = abs(calculated - reference_mass) / reference_mass * 100.0
    return rel_error <= tolerance_pct, calculated, rel_error


def to_hill_order(composition: dict[str, int]) -> str:
    """
    Convert an elemental composition dict back to a Hill-order formula string.

    Hill order: C first, H second, then remaining elements alphabetically.

    Args:
        composition: Dictionary of {element: count}.

    Returns:
        Hill-order formula string.
    """
    elements = dict(composition)
    result = ""

    # Carbon first
    if "C" in elements:
        count = elements.pop("C")
        result += "C" if count == 1 else f"C{count}"
    # Hydrogen second (only if carbon present)
    if "C" in composition and "H" in elements:
        count = elements.pop("H")
        result += "H" if count == 1 else f"H{count}"
    elif "H" in elements and "C" not in composition:
        count = elements.pop("H")
        result += "H" if count == 1 else f"H{count}"

    # Remaining elements alphabetically
    for el in sorted(elements.keys()):
        count = elements[el]
        result += el if count == 1 else f"{el}{count}"

    return result
