"""
Safety advisor for ChemCheck.

Parses GHS codes and renders human-readable safety summaries.
Also generates analytical verification disclaimers for laboratory use.
"""

from __future__ import annotations

import json
import os
from typing import Optional

from src.models.chemical_schema import ChemicalRecord, SafetyInfo


# ── Load GHS reference data ────────────────────────────────────────────────
_GHS_REF_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "ghs_reference.json")

_GHS_REF: dict = {}

def _load_ghs_ref() -> dict:
    global _GHS_REF
    if _GHS_REF:
        return _GHS_REF
    try:
        with open(_GHS_REF_PATH, encoding="utf-8") as fh:
            _GHS_REF = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        # Non-fatal: render codes without descriptions if file missing
        _GHS_REF = {"hazard_statements": {}, "precautionary_statements": {}, "pictogram_descriptions": {}}
    return _GHS_REF


# ── Hazard severity mapping ────────────────────────────────────────────────
_SIGNAL_WORD_SEVERITY = {"Danger": 2, "Warning": 1, "": 0}

_NFPA_LABELS = {
    "health": "Health",
    "flammability": "Flammability",
    "instability": "Instability",
    "special": "Special",
}

_NFPA_SEVERITY = {
    0: "Minimal hazard",
    1: "Slight hazard",
    2: "Moderate hazard",
    3: "Serious hazard",
    4: "Severe hazard",
}


def expand_h_statements(h_codes: list[str]) -> list[str]:
    """
    Expand GHS H-statement codes to full text descriptions.

    Args:
        h_codes: List of H-statement codes (e.g., ["H314", "H335"]).

    Returns:
        List of strings in the format "H314: <description>".
    """
    ref = _load_ghs_ref()
    hazards = ref.get("hazard_statements", {})
    result = []
    for code in h_codes:
        # Normalize code – strip supplementary letters like H361d → H361
        base = code[:4] if len(code) >= 4 else code
        description = hazards.get(base, hazards.get(code, "Description not available"))
        result.append(f"{code}: {description}")
    return result


def expand_p_statements(p_codes: list[str]) -> list[str]:
    """
    Expand GHS P-statement codes to full text descriptions.

    Args:
        p_codes: List of P-statement codes (e.g., ["P260", "P280"]).

    Returns:
        List of strings in the format "P260: <description>".
    """
    ref = _load_ghs_ref()
    precautionary = ref.get("precautionary_statements", {})
    result = []
    for code in p_codes:
        description = precautionary.get(code, "Description not available")
        result.append(f"{code}: {description}")
    return result


def expand_pictograms(pictogram_codes: list[str]) -> list[str]:
    """
    Expand GHS pictogram codes to descriptions.

    Args:
        pictogram_codes: List of pictogram codes (e.g., ["GHS02", "GHS05"]).

    Returns:
        List of strings in the format "GHS02: <description>".
    """
    ref = _load_ghs_ref()
    pictograms = ref.get("pictogram_descriptions", {})
    return [f"{code}: {pictograms.get(code, 'Description not available')}" for code in pictogram_codes]


def nfpa_summary(nfpa: dict) -> str:
    """
    Render a human-readable NFPA 704 summary string.

    Args:
        nfpa: Dictionary with keys health, flammability, instability, special.

    Returns:
        Multi-line NFPA 704 summary string.
    """
    lines = ["NFPA 704 Diamond:"]
    for key, label in _NFPA_LABELS.items():
        value = nfpa.get(key, 0)
        if key == "special":
            lines.append(f"  {label}: {value if value else 'None'}")
        else:
            try:
                rating = int(value)
            except (ValueError, TypeError):
                rating = 0
            severity = _NFPA_SEVERITY.get(rating, "Unknown")
            lines.append(f"  {label}: {rating} – {severity}")
    return "\n".join(lines)


def render_safety_summary(chemical: ChemicalRecord) -> str:
    """
    Render a complete human-readable safety summary for a chemical.

    Args:
        chemical: ChemicalRecord containing safety information.

    Returns:
        Formatted multi-line safety summary string.
    """
    safety = chemical.safety
    sections: list[str] = []

    # Header
    sections.append(f"{'=' * 60}")
    sections.append(f"SAFETY SUMMARY: {chemical.name.upper()}")
    sections.append(f"Formula: {chemical.formula}  |  CAS: {chemical.cas_number}")
    sections.append(f"{'=' * 60}")

    # Signal word
    sections.append(f"\n⚠  GHS Signal Word: {safety.ghs_signal_word or 'Not classified'}")

    # SDS summary
    sections.append(f"\nSDS Summary:\n  {safety.sds_summary}")

    # Pictograms
    if safety.ghs_pictograms:
        sections.append("\nGHS Pictograms:")
        for pic in expand_pictograms(safety.ghs_pictograms):
            sections.append(f"  • {pic}")

    # Hazard statements
    if safety.h_statements:
        sections.append("\nHazard Statements:")
        for stmt in expand_h_statements(safety.h_statements):
            sections.append(f"  • {stmt}")

    # Precautionary statements
    if safety.p_statements:
        sections.append("\nPrecautionary Statements:")
        for stmt in expand_p_statements(safety.p_statements):
            sections.append(f"  • {stmt}")

    # NFPA 704
    if safety.nfpa_704:
        sections.append(f"\n{nfpa_summary(safety.nfpa_704)}")

    # Disclaimer
    sections.append(generate_disclaimer(chemical))

    return "\n".join(sections)


def generate_disclaimer(chemical: Optional[ChemicalRecord] = None) -> str:
    """
    Generate a critical laboratory disclaimer emphasising that physical
    property lookups cannot replace spectroscopic or chromatographic
    analytical verification.

    Args:
        chemical: Optional ChemicalRecord for context-specific messaging.

    Returns:
        Formatted disclaimer string.
    """
    name_ref = f" for {chemical.name}" if chemical else ""

    disclaimer = f"""
{'─' * 60}
⚠  CRITICAL LABORATORY DISCLAIMER{name_ref}
{'─' * 60}
Physical property matching (density, melting point, boiling
point, appearance) provides INDICATIVE IDENTIFICATION ONLY.

ChemCheck results MUST NOT be used as the sole basis for:
  • Confirming the identity of an unknown chemical substance
  • Making safety or regulatory compliance decisions
  • Authorising the use of a substance in critical processes

DEFINITIVE IDENTIFICATION requires one or more of:
  • Nuclear Magnetic Resonance spectroscopy (NMR)
  • Fourier-Transform Infrared spectroscopy (FTIR)
  • Gas Chromatography–Mass Spectrometry (GC-MS)
  • Liquid Chromatography–Mass Spectrometry (LC-MS)
  • X-Ray Diffraction (XRD) for solid crystalline materials
  • Inductively Coupled Plasma (ICP) for elemental analysis

Always consult the original container label, Safety Data
Sheet (SDS), and your institution's chemical hygiene plan
before working with any laboratory chemical.
{'─' * 60}"""
    return disclaimer


def assess_hazard_level(safety: SafetyInfo) -> str:
    """
    Assess the overall hazard level from safety information.

    Returns a string: 'Low', 'Moderate', 'High', or 'Extreme'.
    """
    severity = _SIGNAL_WORD_SEVERITY.get(safety.ghs_signal_word, 0)
    nfpa_max = max(
        (
            int(v)
            for k, v in safety.nfpa_704.items()
            if k != "special" and str(v).lstrip("-").isdigit()
        ),
        default=0,
    )

    combined = max(severity * 2, nfpa_max)

    if combined <= 1:
        return "Low"
    elif combined <= 2:
        return "Moderate"
    elif combined <= 3:
        return "High"
    else:
        return "Extreme"
