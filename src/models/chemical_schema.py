"""
Pydantic v2 data models for ChemCheck chemical identification system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class PhysicalProperties(BaseModel):
    """Physical and chemical properties of a substance."""

    molar_mass: float = Field(..., description="Molar mass in g/mol")
    melting_point_c: Optional[float] = Field(None, description="Melting point in °C")
    boiling_point_c: Optional[float] = Field(None, description="Boiling point in °C")
    density_g_cm3: Optional[float] = Field(None, description="Density in g/cm³")
    appearance: str = Field(..., description="Physical appearance description")
    state: str = Field(..., description="State of matter at room temperature (solid/liquid/gas)")
    water_solubility: str = Field(..., description="Solubility in water description")


class SafetyInfo(BaseModel):
    """GHS safety information for a chemical."""

    ghs_signal_word: str = Field(..., description="GHS signal word: Danger or Warning")
    ghs_pictograms: list[str] = Field(default_factory=list, description="List of GHS pictogram codes")
    h_statements: list[str] = Field(default_factory=list, description="GHS hazard statement codes")
    p_statements: list[str] = Field(default_factory=list, description="GHS precautionary statement codes")
    nfpa_704: dict = Field(
        default_factory=lambda: {"health": 0, "flammability": 0, "instability": 0, "special": ""},
        description="NFPA 704 diamond ratings",
    )
    sds_summary: str = Field(..., description="Safety Data Sheet summary")


class ChemicalRecord(BaseModel):
    """Complete chemical record with identification, properties, and safety data."""

    # Allow passing already-constructed ChemicalRecord instances without
    # re-validation — prevents Streamlit module-reload identity mismatches.
    model_config = ConfigDict(arbitrary_types_allowed=True, revalidate_instances="never")

    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Common name")
    iupac_name: str = Field(..., description="IUPAC systematic name")
    formula: str = Field(..., description="Molecular formula")
    cas_number: str = Field(..., description="CAS registry number")
    smiles: str = Field(..., description="SMILES string")
    common_uses: list[str] = Field(default_factory=list, description="Common laboratory uses")
    properties: PhysicalProperties
    safety: SafetyInfo


class MeasuredProperties(BaseModel):
    """Experimentally measured properties for comparison against reference data."""

    measured_melting_point: Optional[float] = Field(None, description="Measured melting point in °C")
    measured_boiling_point: Optional[float] = Field(None, description="Measured boiling point in °C")
    measured_density: Optional[float] = Field(None, description="Measured density in g/cm³")
    observed_appearance: Optional[str] = Field(None, description="Observed physical appearance")
    observed_state: Optional[str] = Field(None, description="Observed state of matter")


@dataclass
class MatchResult:
    """
    Result of comparing measured properties against a candidate ChemicalRecord.

    Using a plain dataclass instead of a Pydantic model avoids Pydantic
    re-validating the nested ChemicalRecord against a potentially different
    class identity after Streamlit module reloads.
    """

    candidate: ChemicalRecord
    confidence_score: float
    property_match_details: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Clamp score to valid range regardless of floating-point drift
        self.confidence_score = max(0.0, min(100.0, float(self.confidence_score)))
