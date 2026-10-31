"""
ChemCheck – Laboratory Chemical Identification & Verification Dashboard
Streamlit web application.
"""

from __future__ import annotations

import streamlit as st

# ── Page config (must be first Streamlit call) ─────────────────────────────
st.set_page_config(
    page_title="ChemCheck – Chemical Identification System",
    page_icon="⚗️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

import sys
import os

# Ensure project root is on the path when running via `streamlit run app.py`
sys.path.insert(0, os.path.dirname(__file__))

from src.database.db_manager import get_database
from src.database.pubchem_fallback import search as pubchem_search
from src.core.formula_parser import parse_formula, calculate_molar_mass, FormulaParseError
from src.core.property_matcher import compare_measurements, rank_candidates
from src.core.safety_advisor import (
    render_safety_summary,
    expand_h_statements,
    expand_p_statements,
    expand_pictograms,
    assess_hazard_level,
)
from src.models.chemical_schema import MeasuredProperties, ChemicalRecord

# ── CSS ────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* Global font */
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* Disclaimer banner */
    .disclaimer-banner {
        background: linear-gradient(90deg, #1a1a2e 0%, #16213e 100%);
        color: #f0f0f0;
        border-left: 5px solid #e94560;
        border-radius: 6px;
        padding: 12px 18px;
        margin-bottom: 16px;
        font-size: 0.88rem;
    }
    .disclaimer-banner b { color: #e94560; }

    /* KPI metric cards */
    .kpi-card {
        background: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 10px;
        padding: 16px 12px;
        text-align: center;
        box-shadow: 0 2px 6px rgba(0,0,0,0.06);
    }
    .kpi-label {
        font-size: 0.75rem;
        color: #6c757d;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 4px;
    }
    .kpi-value {
        font-size: 1.6rem;
        font-weight: 700;
        color: #0d6efd;
    }
    .kpi-unit {
        font-size: 0.8rem;
        color: #6c757d;
    }

    /* Chemical identity card */
    .chem-card {
        background: #ffffff;
        border: 1px solid #dee2e6;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        margin-bottom: 16px;
    }
    .chem-name { font-size: 1.5rem; font-weight: 700; color: #212529; }
    .chem-formula {
        font-size: 1.1rem;
        color: #0d6efd;
        font-family: monospace;
        font-weight: 600;
    }
    .chem-meta { color: #6c757d; font-size: 0.85rem; margin-top: 4px; }

    /* GHS pictogram badge */
    .ghs-badge {
        display: inline-block;
        background: #fff3cd;
        border: 1px solid #ffc107;
        border-radius: 6px;
        padding: 4px 10px;
        font-size: 0.78rem;
        font-weight: 600;
        color: #664d03;
        margin: 3px;
    }
    .ghs-danger {
        background: #f8d7da;
        border-color: #dc3545;
        color: #842029;
    }

    /* Confidence gauge */
    .conf-bar-wrap {
        background: #e9ecef;
        border-radius: 20px;
        height: 22px;
        margin: 8px 0;
        overflow: hidden;
    }
    .conf-bar-fill {
        height: 100%;
        border-radius: 20px;
        transition: width 0.4s ease;
        display: flex;
        align-items: center;
        justify-content: flex-end;
        padding-right: 8px;
        font-size: 0.78rem;
        font-weight: 700;
        color: white;
    }

    /* Tolerance table status cells */
    .status-ok { color: #198754; font-weight: 600; }
    .status-warn { color: #dc3545; font-weight: 600; }

    /* Section header */
    .section-hdr {
        font-size: 1rem;
        font-weight: 600;
        color: #495057;
        border-bottom: 2px solid #0d6efd;
        padding-bottom: 4px;
        margin: 18px 0 10px 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Helpers ────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def load_db():
    return get_database()


def _kpi(label: str, value, unit: str = ""):
    value_str = f"{value}" if value is not None else "—"
    return (
        f'<div class="kpi-card">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value_str}</div>'
        f'<div class="kpi-unit">{unit}</div>'
        f'</div>'
    )


def _conf_color(score: float) -> str:
    if score >= 80:
        return "#198754"
    if score >= 50:
        return "#fd7e14"
    return "#dc3545"


def _conf_bar(score: float) -> str:
    color = _conf_color(score)
    return (
        f'<div class="conf-bar-wrap">'
        f'<div class="conf-bar-fill" style="width:{score:.0f}%;background:{color};">'
        f'{score:.1f}%</div></div>'
    )


def _ghs_badge(code: str, signal: str) -> str:
    cls = "ghs-danger" if signal == "Danger" else ""
    return f'<span class="ghs-badge {cls}">{code}</span>'


def _render_chemical_card(record: ChemicalRecord):
    """Render identity header card."""
    st.markdown(
        f'<div class="chem-card">'
        f'<div class="chem-name">⚗️ {record.name}</div>'
        f'<div class="chem-formula">{record.formula}</div>'
        f'<div class="chem-meta">IUPAC: {record.iupac_name} &nbsp;|&nbsp; '
        f'CAS: {record.cas_number} &nbsp;|&nbsp; '
        f'SMILES: <code>{record.smiles or "—"}</code></div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_kpis(record: ChemicalRecord):
    p = record.properties
    cols = st.columns(4)
    kpis = [
        ("Molar Mass", f"{p.molar_mass:.2f}", "g/mol"),
        ("Melting Point", f"{p.melting_point_c:.1f}" if p.melting_point_c is not None else "—", "°C"),
        ("Boiling Point", f"{p.boiling_point_c:.1f}" if p.boiling_point_c is not None else "—", "°C"),
        ("Density", f"{p.density_g_cm3:.3f}" if p.density_g_cm3 is not None else "—", "g/cm³"),
    ]
    for col, (label, val, unit) in zip(cols, kpis):
        with col:
            st.markdown(_kpi(label, val, unit), unsafe_allow_html=True)


def _render_safety(record: ChemicalRecord):
    safety = record.safety
    hazard_level = assess_hazard_level(safety)
    level_color = {"Low": "🟢", "Moderate": "🟡", "High": "🟠", "Extreme": "🔴"}.get(hazard_level, "⚪")

    st.markdown(
        f'<div class="section-hdr">🛡️ Safety Information</div>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns([1, 2])
    with c1:
        st.markdown(f"**GHS Signal Word:** `{safety.ghs_signal_word or 'Not classified'}`")
        st.markdown(f"**Hazard Level:** {level_color} {hazard_level}")
        nfpa = safety.nfpa_704
        st.markdown(
            f"**NFPA 704:** Health `{nfpa.get('health',0)}` | "
            f"Flammability `{nfpa.get('flammability',0)}` | "
            f"Instability `{nfpa.get('instability',0)}`"
        )
    with c2:
        if safety.ghs_pictograms:
            badges = "".join(_ghs_badge(p, safety.ghs_signal_word) for p in safety.ghs_pictograms)
            st.markdown(f"**GHS Pictograms:** {badges}", unsafe_allow_html=True)
        st.markdown(f"**SDS Summary:** {safety.sds_summary}")

    with st.expander("📋 Full H-Statements & P-Statements"):
        if safety.h_statements:
            st.markdown("**Hazard Statements:**")
            for stmt in expand_h_statements(safety.h_statements):
                st.markdown(f"- {stmt}")
        else:
            st.markdown("*No H-statements listed.*")

        if safety.p_statements:
            st.markdown("**Precautionary Statements:**")
            for stmt in expand_p_statements(safety.p_statements):
                st.markdown(f"- {stmt}")


# ── App Shell ──────────────────────────────────────────────────────────────

# Header
st.markdown(
    """
    <h1 style='text-align:center;color:#0d6efd;font-size:2.2rem;margin-bottom:0;'>
    ⚗️ ChemCheck
    </h1>
    <p style='text-align:center;color:#6c757d;font-size:1rem;margin-top:4px;'>
    Intelligent Laboratory Chemical Identification & Verification System
    </p>
    """,
    unsafe_allow_html=True,
)

# Disclaimer
st.markdown(
    """
    <div class="disclaimer-banner">
    <b>⚠ CRITICAL DISCLAIMER:</b> ChemCheck is an informational reference and screening assistant only.
    Unknown substances <b>require definitive analytical validation</b> (FTIR, NMR, GC-MS) before handling.
    Do not rely solely on physical property matching for identification or safety decisions.
    </div>
    """,
    unsafe_allow_html=True,
)

db = load_db()

tab1, tab2, tab3 = st.tabs(
    ["🔍 Direct Lookup", "🧪 Unknown Verification", "⚠️ Safety & Compatibility"]
)

# ══════════════════════════════════════════════════════════════════
# TAB 1 – Direct Lookup
# ══════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("### Search by Name, Formula, or CAS Number")
    col_input, col_btn = st.columns([5, 1])
    with col_input:
        query = st.text_input(
            "Enter chemical name, formula, or CAS",
            placeholder="e.g. NaCl  |  Sodium chloride  |  7647-14-5",
            label_visibility="collapsed",
        )
    with col_btn:
        search_btn = st.button("Search", use_container_width=True, type="primary")

    if query or search_btn:
        with st.spinner("Searching local database…"):
            results = db.search(query, limit=5)

        if not results:
            with st.spinner("No local match — querying PubChem…"):
                try:
                    pc_result = pubchem_search(query)
                    if pc_result:
                        results = [pc_result]
                        st.info("ℹ️ Result fetched from PubChem (limited property data available).")
                except Exception:
                    pass

        if not results:
            st.warning(f"No results found for **{query}**. Try a different name, formula, or CAS number.")
        else:
            if len(results) > 1:
                names = [f"{r.name} ({r.formula})" for r in results]
                chosen_idx = st.selectbox("Multiple matches found – select one:", range(len(names)), format_func=lambda i: names[i])
                record = results[chosen_idx]
            else:
                record = results[0]

            _render_chemical_card(record)
            _render_kpis(record)

            st.markdown('<div class="section-hdr">🔬 Physical Properties</div>', unsafe_allow_html=True)
            p = record.properties
            prop_c1, prop_c2 = st.columns(2)
            with prop_c1:
                st.markdown(f"**Appearance:** {p.appearance}")
                st.markdown(f"**State at RT:** {p.state.capitalize()}")
            with prop_c2:
                st.markdown(f"**Water Solubility:** {p.water_solubility}")
                if record.common_uses:
                    st.markdown(f"**Common Uses:** {', '.join(record.common_uses[:3])}")

            _render_safety(record)

            with st.expander("📊 Formula Analysis"):
                try:
                    comp = parse_formula(record.formula)
                    calc_mass = calculate_molar_mass(record.formula)
                    st.markdown(f"**Elemental Composition:** {comp}")
                    st.markdown(
                        f"**Calculated Molar Mass:** `{calc_mass:.4f} g/mol` "
                        f"(Reference: `{record.properties.molar_mass} g/mol`)"
                    )
                    rel_err = abs(calc_mass - record.properties.molar_mass) / record.properties.molar_mass * 100
                    st.markdown(f"**Formula Validation:** {'✅ Consistent' if rel_err < 1.0 else f'⚠️ Deviation {rel_err:.2f}%'}")
                except FormulaParseError as e:
                    st.warning(f"Could not parse formula: {e}")

# ══════════════════════════════════════════════════════════════════
# TAB 2 – Unknown Verification
# ══════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("### Match Measured Properties to Reference Data")
    st.caption("Enter your experimentally measured values and observed characteristics below.")

    all_chemicals = db.all_chemicals()
    chem_names = ["(search & select)"] + [f"{c.name} ({c.formula})" for c in all_chemicals]

    t2_c1, t2_c2 = st.columns([2, 3])

    with t2_c1:
        st.markdown("**Observed Characteristics**")
        obs_state = st.selectbox("Observed State", ["", "solid", "liquid", "gas"], index=0)
        obs_appearance = st.text_input("Observed Appearance", placeholder="e.g. white crystalline solid")

        st.markdown("**Measured Properties**")
        use_celsius = st.toggle("Use °C for temperatures", value=True)
        temp_unit_label = "°C" if use_celsius else "K"

        mp_enabled = st.checkbox("Melting Point")
        measured_mp = None
        if mp_enabled:
            raw_mp = st.number_input(f"Melting Point ({temp_unit_label})", value=0.0, format="%.2f")
            measured_mp = raw_mp if use_celsius else raw_mp - 273.15

        bp_enabled = st.checkbox("Boiling Point")
        measured_bp = None
        if bp_enabled:
            raw_bp = st.number_input(f"Boiling Point ({temp_unit_label})", value=100.0, format="%.2f")
            measured_bp = raw_bp if use_celsius else raw_bp - 273.15

        den_enabled = st.checkbox("Density")
        measured_den = None
        if den_enabled:
            measured_den = st.number_input("Density (g/cm³)", value=1.0, format="%.4f", min_value=0.0001)

        st.markdown("**Candidate Chemical(s)**")
        candidate_mode = st.radio("Candidate selection", ["Compare all", "Select specific"], horizontal=True)
        selected_candidates: list[ChemicalRecord] = []

        if candidate_mode == "Select specific":
            selected_name = st.selectbox("Select candidate", chem_names)
            if selected_name != "(search & select)":
                idx = chem_names.index(selected_name) - 1
                selected_candidates = [all_chemicals[idx]]
        else:
            selected_candidates = all_chemicals

        run_match = st.button("▶ Run Verification", type="primary", use_container_width=True)

    with t2_c2:
        if run_match:
            if not any([mp_enabled, bp_enabled, den_enabled, obs_state, obs_appearance]):
                st.warning("Please enter at least one measurement or observation.")
            else:
                measurements = MeasuredProperties(
                    measured_melting_point=measured_mp if mp_enabled else None,
                    measured_boiling_point=measured_bp if bp_enabled else None,
                    measured_density=measured_den if den_enabled else None,
                    observed_appearance=obs_appearance if obs_appearance else None,
                    observed_state=obs_state if obs_state else None,
                )

                with st.spinner("Comparing against reference data…"):
                    top_results = rank_candidates(selected_candidates, measurements, top_n=5)

                st.markdown("#### Top Matches")
                for rank_i, match in enumerate(top_results, 1):
                    score = match.confidence_score
                    cand = match.candidate
                    color = _conf_color(score)

                    with st.expander(
                        f"#{rank_i}  {cand.name} ({cand.formula})  —  Score: {score:.1f}%",
                        expanded=(rank_i == 1),
                    ):
                        st.markdown(
                            f"**Match Confidence:** {score:.1f}%",
                        )
                        st.markdown(_conf_bar(score), unsafe_allow_html=True)

                        # Property comparison table
                        table_rows = []
                        details = match.property_match_details

                        prop_map = [
                            ("melting_point", "Melting Point (°C)"),
                            ("boiling_point", "Boiling Point (°C)"),
                            ("density", "Density (g/cm³)"),
                        ]
                        for key, label in prop_map:
                            if key in details and details[key].get("measured_value") is not None:
                                d = details[key]
                                ref = d["reference_value"]
                                meas = d["measured_value"]
                                err = d["relative_error_pct"]
                                ok = d["within_tolerance"]
                                status = "✅ Within Tolerance" if ok else "❌ Discrepancy"
                                table_rows.append({
                                    "Property": label,
                                    "Reference": f"{ref:.2f}" if ref is not None else "—",
                                    "Measured": f"{meas:.2f}",
                                    "Error %": f"{err:.2f}%",
                                    "Status": status,
                                })

                        if details.get("appearance") and details["appearance"].get("measured_value"):
                            d = details["appearance"]
                            sim = d.get("similarity_score", 0) * 100
                            table_rows.append({
                                "Property": "Appearance",
                                "Reference": d["reference_value"],
                                "Measured": d["measured_value"],
                                "Error %": f"{100-sim:.1f}% dissim.",
                                "Status": "✅ Match" if sim >= 50 else "⚠️ Partial",
                            })

                        if details.get("state") and details["state"].get("measured_value"):
                            d = details["state"]
                            table_rows.append({
                                "Property": "State",
                                "Reference": d["reference_value"],
                                "Measured": d["measured_value"],
                                "Error %": "—",
                                "Status": "✅ Match" if d["match"] else "❌ Mismatch",
                            })

                        if table_rows:
                            import pandas as pd
                            st.dataframe(
                                pd.DataFrame(table_rows),
                                hide_index=True,
                                use_container_width=True,
                            )
                        else:
                            st.info("No numeric property comparisons available.")

        else:
            st.markdown(
                """
                <div style="color:#6c757d;padding:40px;text-align:center;border:2px dashed #dee2e6;border-radius:10px;">
                Enter measurements on the left and click <b>Run Verification</b> to compare against
                reference data for all or selected chemicals.
                </div>
                """,
                unsafe_allow_html=True,
            )

# ══════════════════════════════════════════════════════════════════
# TAB 3 – Safety & Compatibility
# ══════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("### Batch Chemical Safety & Compatibility Check")
    st.caption("Select two or more chemicals to check for obvious reactivity hazards.")

    all_chem_names = [f"{c.name} ({c.formula})" for c in all_chemicals]

    selected_names = st.multiselect(
        "Select chemicals to compare",
        options=all_chem_names,
        default=all_chem_names[:2] if len(all_chem_names) >= 2 else [],
        max_selections=6,
    )

    # Reactivity rule engine
    _OXIDIZERS = {"KMnO4", "HNO3", "H2O2"}
    _STRONG_ACIDS = {"HCl", "H2SO4", "HNO3"}
    _STRONG_BASES = {"NaOH", "KOH"}
    _FLAMMABLES = {"C2H5OH", "CH3OH", "C3H8O", "C3H6O", "C6H14", "C7H8", "C6H6", "CHCl3", "CH2Cl2", "C4H10O", "C4H8O2"}

    def _get_hazards(chemicals: list[ChemicalRecord]) -> list[dict]:
        hazards = []
        formulas = {c.formula for c in chemicals}
        names_lower = {c.name.lower() for c in chemicals}

        acid_present = any(f in _STRONG_ACIDS for f in formulas)
        base_present = any(f in _STRONG_BASES for f in formulas)
        oxidizer_present = any(f in _OXIDIZERS for f in formulas)
        flammable_present = any(f in _FLAMMABLES for f in formulas)

        if acid_present and base_present:
            hazards.append({
                "severity": "🔴 DANGER",
                "title": "Strong Acid + Strong Base",
                "detail": "Highly exothermic neutralisation reaction. Risk of spattering, heat generation, and pressure buildup. Never mix concentrated acids and bases directly.",
            })
        if oxidizer_present and flammable_present:
            hazards.append({
                "severity": "🔴 DANGER",
                "title": "Oxidizer + Flammable Solvent",
                "detail": "Strong oxidizers (KMnO₄, HNO₃, H₂O₂) in contact with flammable organic solvents can cause spontaneous ignition or explosion. Keep strictly separated.",
            })
        if oxidizer_present and base_present:
            hazards.append({
                "severity": "🟠 WARNING",
                "title": "Oxidizer + Strong Base",
                "detail": "Some oxidizers react vigorously with strong bases generating heat and hazardous by-products. Use with caution.",
            })
        if "NH3" in formulas and acid_present:
            hazards.append({
                "severity": "🟠 WARNING",
                "title": "Ammonia + Acid",
                "detail": "Ammonia reacts with acids to form ammonium salts, generating heat and fumes. Toxic ammonia vapors may be released.",
            })
        if "CH3OH" in formulas and ("HCl" in formulas or "H2SO4" in formulas):
            hazards.append({
                "severity": "🟠 WARNING",
                "title": "Methanol + Strong Acid",
                "detail": "Methanol and strong acids can react to form methyl esters. Both reagents are highly toxic/corrosive.",
            })
        if "I2" in formulas and "NH3" in formulas:
            hazards.append({
                "severity": "🔴 DANGER",
                "title": "Iodine + Ammonia",
                "detail": "Forms nitrogen triiodide (NI₃), an extremely sensitive contact explosive. This combination must be avoided in the laboratory.",
            })
        if "H2O2" in formulas and "CH3OH" in formulas:
            hazards.append({
                "severity": "🔴 DANGER",
                "title": "Hydrogen Peroxide + Methanol",
                "detail": "H₂O₂ and methanol can form methyl hydroperoxide, a shock-sensitive explosive. Do not mix.",
            })
        if "KMnO4" in formulas and ("C2H5OH" in formulas or "CH3OH" in formulas or "C3H6O" in formulas):
            hazards.append({
                "severity": "🔴 DANGER",
                "title": "Potassium Permanganate + Organic Solvent",
                "detail": "KMnO₄ can react violently with ethanol, methanol, and acetone, causing fires or explosions.",
            })

        return hazards

    if len(selected_names) >= 2:
        chosen = []
        for sn in selected_names:
            for c in all_chemicals:
                if f"{c.name} ({c.formula})" == sn:
                    chosen.append(c)
                    break

        # Summary table
        st.markdown("#### Selected Chemicals")
        import pandas as pd

        rows = []
        for c in chosen:
            rows.append({
                "Chemical": c.name,
                "Formula": c.formula,
                "State": c.properties.state.capitalize(),
                "Signal Word": c.safety.ghs_signal_word or "—",
                "Hazard Level": assess_hazard_level(c.safety),
                "NFPA Health": c.safety.nfpa_704.get("health", 0),
                "NFPA Flamm.": c.safety.nfpa_704.get("flammability", 0),
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

        # Hazard analysis
        st.markdown("#### ⚠️ Reactivity & Compatibility Analysis")
        hazards = _get_hazards(chosen)

        if hazards:
            for h in hazards:
                color = "#f8d7da" if "DANGER" in h["severity"] else "#fff3cd"
                border = "#dc3545" if "DANGER" in h["severity"] else "#ffc107"
                st.markdown(
                    f"""<div style="background:{color};border-left:5px solid {border};
                    border-radius:6px;padding:12px 16px;margin-bottom:10px;">
                    <b>{h['severity']}: {h['title']}</b><br>
                    <span style="font-size:0.9rem;">{h['detail']}</span>
                    </div>""",
                    unsafe_allow_html=True,
                )
        else:
            st.success("✅ No obvious major reactivity hazards detected between the selected chemicals. Always consult individual SDS sheets.")

        st.markdown("#### 📋 Individual Safety Summaries")
        for c in chosen:
            with st.expander(f"{c.name} ({c.formula}) – Safety Details"):
                s = c.safety
                st.markdown(f"**Signal Word:** `{s.ghs_signal_word}`")
                if s.ghs_pictograms:
                    st.markdown("**Pictograms:** " + " | ".join(s.ghs_pictograms))
                if s.h_statements:
                    st.markdown("**Hazards:**")
                    for stmt in expand_h_statements(s.h_statements):
                        st.markdown(f"- {stmt}")
                if s.p_statements:
                    st.markdown("**Precautions:**")
                    for stmt in expand_p_statements(s.p_statements[:5]):
                        st.markdown(f"- {stmt}")
                st.markdown(f"**SDS Summary:** {s.sds_summary}")

    elif len(selected_names) == 1:
        st.info("Select at least one more chemical to run a compatibility analysis.")
    else:
        st.info("Select two or more chemicals from the dropdown above.")

# ── Footer ─────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    """
    <div style="text-align:center;color:#adb5bd;font-size:0.78rem;">
    ChemCheck v1.0.0 &nbsp;|&nbsp; For research and educational use only &nbsp;|&nbsp;
    Always consult official SDS documents and perform analytical verification before handling unknown substances.
    </div>
    """,
    unsafe_allow_html=True,
)
