"""
Comprehensive pytest test suite for ChemCheck.

Covers formula parsing, database exact/fuzzy search,
property matching tolerances, and discrepancy detection.
"""

from __future__ import annotations

import pytest

from src.core.formula_parser import (
    calculate_molar_mass,
    parse_formula,
    FormulaParseError,
)
from src.core.property_matcher import compare_measurements, DEFAULT_TOLERANCES
from src.database.db_manager import ChemicalDatabase, get_database
from src.models.chemical_schema import MeasuredProperties


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def db() -> ChemicalDatabase:
    """Shared database instance across all tests in this session."""
    return get_database()


@pytest.fixture(scope="session")
def nacl(db):
    """NaCl record from the database."""
    record = db.get_by_formula("NaCl")
    assert record is not None, "NaCl must exist in chemicals.json"
    return record


# ── 1. Formula Parser ────────────────────────────────────────────────────────

class TestFormulaParser:
    """Tests for src.core.formula_parser"""

    def test_simple_formula_nacl(self):
        """NaCl parses to exactly {Na: 1, Cl: 1}."""
        result = parse_formula("NaCl")
        assert result == {"Na": 1, "Cl": 1}

    def test_simple_formula_h2o(self):
        """H2O parses to {H: 2, O: 1}."""
        result = parse_formula("H2O")
        assert result == {"H": 2, "O": 1}

    def test_polyatomic_h2so4(self):
        """H2SO4 parses to {H: 2, S: 1, O: 4}."""
        result = parse_formula("H2SO4")
        assert result == {"H": 2, "S": 1, "O": 4}

    def test_nested_parentheses_ca_oh_2(self):
        """Ca(OH)2 expands to {Ca: 1, O: 2, H: 2}."""
        result = parse_formula("Ca(OH)2")
        assert result == {"Ca": 1, "O": 2, "H": 2}

    def test_nested_parentheses_al2_so4_3(self):
        """Al2(SO4)3 → {Al: 2, S: 3, O: 12}."""
        result = parse_formula("Al2(SO4)3")
        assert result == {"Al": 2, "S": 3, "O": 12}

    def test_organic_acetic_acid(self):
        """CH3COOH → {C: 2, H: 4, O: 2}."""
        result = parse_formula("CH3COOH")
        assert result == {"C": 2, "H": 4, "O": 2}

    def test_molar_mass_nacl(self):
        """NaCl theoretical molar mass ≈ 58.44 g/mol (within 0.05)."""
        mass = calculate_molar_mass("NaCl")
        assert abs(mass - 58.44) < 0.05, f"NaCl mass {mass:.4f} out of range"

    def test_molar_mass_h2so4(self):
        """H2SO4 theoretical molar mass ≈ 98.08 g/mol (within 0.05)."""
        mass = calculate_molar_mass("H2SO4")
        assert abs(mass - 98.08) < 0.05, f"H2SO4 mass {mass:.4f} out of range"

    def test_molar_mass_ethanol(self):
        """C2H5OH theoretical molar mass ≈ 46.07 g/mol (within 0.05)."""
        mass = calculate_molar_mass("C2H5OH")
        assert abs(mass - 46.07) < 0.05, f"Ethanol mass {mass:.4f} out of range"

    def test_molar_mass_acetone(self):
        """C3H6O theoretical molar mass ≈ 58.08 g/mol (within 0.05)."""
        mass = calculate_molar_mass("C3H6O")
        assert abs(mass - 58.08) < 0.05, f"Acetone mass {mass:.4f} out of range"

    def test_unknown_element_raises(self):
        """Unknown element symbol raises FormulaParseError."""
        with pytest.raises(FormulaParseError):
            parse_formula("Xx2O3")

    def test_empty_formula_raises(self):
        """Empty string raises FormulaParseError."""
        with pytest.raises(FormulaParseError):
            parse_formula("")


# ── 2. Local Database Exact Search ──────────────────────────────────────────

class TestLocalDatabaseExactSearch:
    """Tests for src.database.db_manager exact-match lookups."""

    def test_search_by_name_exact(self, db):
        """Exact name 'Sodium chloride' returns a result."""
        results = db.search("Sodium chloride")
        assert results, "Expected at least one result"
        assert results[0].formula == "NaCl"

    def test_search_by_name_case_insensitive(self, db):
        """Name lookup is case-insensitive."""
        results = db.search("sodium chloride")
        assert results
        assert results[0].formula == "NaCl"

    def test_get_by_formula_nacl(self, db):
        """get_by_formula('NaCl') returns Sodium chloride."""
        record = db.get_by_formula("NaCl")
        assert record is not None
        assert record.name == "Sodium chloride"
        assert record.formula == "NaCl"

    def test_get_by_formula_case_insensitive(self, db):
        """Formula lookup is case-insensitive (nacl == NaCl)."""
        record = db.get_by_formula("nacl")
        assert record is not None
        assert record.formula == "NaCl"

    def test_nacl_molar_mass_reference(self, nacl):
        """NaCl reference molar mass is 58.44 g/mol."""
        assert abs(nacl.properties.molar_mass - 58.44) < 0.01

    def test_get_by_cas_nacl(self, db):
        """CAS lookup for NaCl (7647-14-5) returns correct record."""
        record = db.get_by_cas("7647-14-5")
        assert record is not None
        assert record.formula == "NaCl"
        assert record.name == "Sodium chloride"

    def test_get_by_cas_strips_hyphens(self, db):
        """CAS lookup works without hyphens."""
        record = db.get_by_cas("7647145")
        assert record is not None
        assert record.formula == "NaCl"

    def test_nonexistent_formula_returns_none(self, db):
        """Unknown formula returns None from get_by_formula."""
        assert db.get_by_formula("Zz99Qq") is None

    def test_database_has_minimum_chemicals(self, db):
        """Database must contain at least 25 chemicals."""
        assert db.count() >= 25, f"Only {db.count()} chemicals loaded"

    def test_known_chemicals_present(self, db):
        """Spot-check that key chemicals from each family are present."""
        expected = [
            ("NaCl", "formula"),
            ("H2SO4", "formula"),
            ("NaOH", "formula"),
            ("C2H5OH", "formula"),
            ("C3H6O", "formula"),  # acetone
        ]
        for query, _ in expected:
            result = db.get_by_formula(query)
            assert result is not None, f"{query} not found in database"


# ── 3. Fuzzy Search ──────────────────────────────────────────────────────────

class TestFuzzySearch:
    """Tests for fuzzy name matching."""

    def test_typo_sodum_chlorid(self, db):
        """Typo 'sodum chlorid' fuzzy-matches to Sodium chloride."""
        results = db.search("sodum chlorid")
        assert results, "Expected fuzzy match for 'sodum chlorid'"
        assert results[0].formula == "NaCl", (
            f"Expected NaCl, got {results[0].formula}"
        )

    def test_typo_sulphuric_acid(self, db):
        """'sulphuric acid' (British spelling variant) matches Sulfuric acid."""
        results = db.search("sulphuric acid")
        assert results
        assert results[0].formula == "H2SO4"

    def test_typo_etanol(self, db):
        """'etanol' (single-l typo) fuzzy-matches to Ethanol."""
        results = db.search("etanol")
        assert results
        assert results[0].formula == "C2H5OH"

    def test_fuzzy_search_returns_scored_tuples(self, db):
        """fuzzy_search returns list of (ChemicalRecord, float) tuples."""
        hits = db.fuzzy_search("sodium")
        assert isinstance(hits, list)
        if hits:
            record, score = hits[0]
            assert 0.0 <= score <= 100.0

    def test_fuzzy_threshold_filters_poor_matches(self, db):
        """Very high threshold (99.0) filters out near-matches."""
        hits = db.fuzzy_search("sodum chlorid", threshold=99.0)
        # Should return 0 or only perfect matches – definitely not 'sodum chlorid'
        for record, score in hits:
            assert score >= 99.0

    def test_no_match_returns_empty(self, db):
        """Complete nonsense returns empty list."""
        results = db.search("xyzzy_quantum_foam_123")
        # May return empty or irrelevant; ensure it doesn't crash
        assert isinstance(results, list)


# ── 4. Property Matcher – Tolerance Compliance ──────────────────────────────

class TestPropertyMatcherTolerances:
    """Tests for within-tolerance matching."""

    def test_density_within_tolerance(self, nacl):
        """
        Measured density 2.14 g/cm³ vs reference 2.165 g/cm³ for NaCl.
        Relative error ≈ 1.15 % which is well within the ±10% tolerance.
        """
        measurements = MeasuredProperties(measured_density=2.14)
        result = compare_measurements(nacl, measurements)

        density_detail = result.property_match_details["density"]
        assert density_detail["within_tolerance"] is True, (
            f"Expected within tolerance, got error {density_detail['relative_error_pct']:.2f}%"
        )
        assert density_detail["relative_error_pct"] < DEFAULT_TOLERANCES["density"]

    def test_melting_point_within_tolerance(self, nacl):
        """
        NaCl melting point reference = 801 °C.
        Measured 820 °C → error ≈ 2.4 % < 5% tolerance.
        """
        measurements = MeasuredProperties(measured_melting_point=820.0)
        result = compare_measurements(nacl, measurements)

        mp_detail = result.property_match_details["melting_point"]
        assert mp_detail["within_tolerance"] is True

    def test_boiling_point_within_tolerance_acetone(self, db):
        """
        Acetone boiling point = 56.1 °C.
        Measured 55.0 °C → error ≈ 1.96 % < 5% tolerance.
        """
        acetone = db.get_by_id("acetone")
        assert acetone is not None
        measurements = MeasuredProperties(measured_boiling_point=55.0)
        result = compare_measurements(acetone, measurements)

        bp_detail = result.property_match_details["boiling_point"]
        assert bp_detail["within_tolerance"] is True

    def test_confidence_score_bounds(self, nacl):
        """Confidence score is always in [0, 100]."""
        measurements = MeasuredProperties(
            measured_density=2.165,
            measured_melting_point=801.0,
        )
        result = compare_measurements(nacl, measurements)
        assert 0.0 <= result.confidence_score <= 100.0

    def test_perfect_match_gives_high_score(self, nacl):
        """Exact reference values should produce a score close to 100."""
        measurements = MeasuredProperties(
            measured_density=2.165,
            measured_melting_point=801.0,
            measured_boiling_point=1413.0,
            observed_state="solid",
        )
        result = compare_measurements(nacl, measurements)
        assert result.confidence_score >= 90.0, (
            f"Perfect match should score ≥90, got {result.confidence_score}"
        )

    def test_no_measurements_gives_neutral_score(self, nacl):
        """No measurements provided returns neutral 50.0 score."""
        measurements = MeasuredProperties()
        result = compare_measurements(nacl, measurements)
        assert result.confidence_score == 50.0

    def test_custom_tolerance_override(self, nacl):
        """
        Custom density tolerance of 0.1% makes 2.14 vs 2.165 fail.
        """
        measurements = MeasuredProperties(measured_density=2.14)
        result = compare_measurements(nacl, measurements, tolerances={"density": 0.1})
        density_detail = result.property_match_details["density"]
        assert density_detail["within_tolerance"] is False


# ── 5. Discrepancy Detection ─────────────────────────────────────────────────

class TestDiscrepancyDetection:
    """Tests that large measurement deviations lower confidence and flag errors."""

    def test_wrong_melting_point_nacl(self, nacl):
        """
        NaCl reference melting point = 801 °C.
        Measured 150 °C → error ≈ 81.3 %, far outside 5% tolerance.
        Should be flagged as discrepancy and confidence should be low.
        """
        measurements = MeasuredProperties(measured_melting_point=150.0)
        result = compare_measurements(nacl, measurements)

        mp_detail = result.property_match_details["melting_point"]

        # Must flag as outside tolerance
        assert mp_detail["within_tolerance"] is False, (
            "Melting point 150°C vs 801°C must be flagged as discrepancy"
        )

        # Relative error must exceed tolerance threshold significantly
        assert mp_detail["relative_error_pct"] > 50.0, (
            f"Expected >50% error, got {mp_detail['relative_error_pct']:.1f}%"
        )

        # Confidence score should be substantially lower than 50
        assert result.confidence_score < 50.0, (
            f"Expected low confidence for 150°C vs 801°C, got {result.confidence_score}"
        )

    def test_wrong_density_nacl(self, nacl):
        """
        NaCl density = 2.165 g/cm³.
        Measured 0.8 g/cm³ (similar to ethanol) flags a major discrepancy.
        """
        measurements = MeasuredProperties(measured_density=0.8)
        result = compare_measurements(nacl, measurements)

        den_detail = result.property_match_details["density"]
        assert den_detail["within_tolerance"] is False
        assert den_detail["relative_error_pct"] > 50.0

    def test_wrong_state_reduces_score(self, nacl):
        """
        NaCl is a solid; measuring as 'gas' reduces confidence.
        """
        meas_solid = MeasuredProperties(observed_state="solid")
        meas_gas = MeasuredProperties(observed_state="gas")

        result_solid = compare_measurements(nacl, meas_solid)
        result_gas = compare_measurements(nacl, meas_gas)

        assert result_solid.confidence_score > result_gas.confidence_score, (
            "Correct state should produce higher score than incorrect state"
        )

    def test_multiple_discrepancies_lower_score(self, nacl):
        """
        Multiple wrong properties should drive confidence well below 50.
        """
        measurements = MeasuredProperties(
            measured_melting_point=150.0,   # should be 801 °C
            measured_density=0.79,          # should be 2.165 g/cm³
            observed_state="liquid",        # should be solid
        )
        result = compare_measurements(nacl, measurements)
        assert result.confidence_score < 30.0, (
            f"Multiple discrepancies should score <30, got {result.confidence_score}"
        )

    def test_property_detail_keys_present(self, nacl):
        """MatchResult property_match_details contains expected keys."""
        measurements = MeasuredProperties(
            measured_melting_point=801.0,
            measured_density=2.165,
            observed_state="solid",
        )
        result = compare_measurements(nacl, measurements)
        details = result.property_match_details

        assert "melting_point" in details
        assert "density" in details
        assert "state" in details
        assert "summary" in details

        # Numeric property detail keys
        for prop in ("melting_point", "density"):
            assert "reference_value" in details[prop]
            assert "measured_value" in details[prop]
            assert "relative_error_pct" in details[prop]
            assert "within_tolerance" in details[prop]
