# ⚗️ ChemCheck — Chemical Identification System

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Streamlit-1.35+-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white" alt="Streamlit">
  <img src="https://img.shields.io/badge/Pydantic-v2-E92063?style=for-the-badge&logo=pydantic&logoColor=white" alt="Pydantic">
  <img src="https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/Build-Passing-22c55e?style=for-the-badge" alt="Build">
</p>

<p align="center">
  <b>An intelligent laboratory chemical identification and verification system.</b><br>
  Identify chemicals by name, formula, or CAS number · Match experimental measurements to reference data · Review GHS safety information
</p>

---

> ⚠️ **CRITICAL DISCLAIMER:** ChemCheck is an informational reference and screening assistant **only**.
> Unknown substances require **definitive analytical validation** (FTIR, NMR, GC-MS) before handling.
> Do not rely solely on physical property matching for safety or regulatory decisions.

---

## Table of Contents

- [System Overview](#system-overview)
- [Architecture](#architecture)
- [Features](#features)
- [Example Walkthrough](#example-walkthrough)
- [Measurement Matching Algorithm](#measurement-matching-algorithm)
- [Quickstart](#quickstart)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Analytical Limitations & Safety Disclaimer](#analytical-limitations--safety-disclaimer)

---

## System Overview

ChemCheck is a dual-layer chemical identification pipeline designed for laboratory environments. It allows personnel to:

- **Search** a curated local database of 27+ chemicals by name, Hill formula, or CAS registry number
- **Fall back** to PubChem PUG-REST API when the local database yields no result
- **Verify** experimentally measured properties (melting point, boiling point, density, appearance) against reference constants with configurable percentage tolerances
- **Review** GHS hazard classifications, NFPA 704 ratings, H-statements, and P-statements
- **Screen** chemical combinations for obvious reactivity hazards (acid/base, oxidizer/flammable)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     ChemCheck System Pipeline                       │
└─────────────────────────────────────────────────────────────────────┘

  User Input (Name / Formula / CAS / Measurements)
          │
          ▼
  ┌───────────────────┐
  │   app.py          │  ◄── Streamlit Dashboard (3 tabs)
  │   (Frontend)      │
  └────────┬──────────┘
           │
    ┌──────┴──────────────────────────────────┐
    │                                         │
    ▼                                         ▼
┌──────────────────────┐          ┌────────────────────────┐
│  db_manager.py       │          │  pubchem_fallback.py   │
│  Local Database      │   MISS   │  PubChem PUG-REST API  │
│  ──────────────────  │ ──────►  │  ──────────────────    │
│  • Exact: formula    │          │  • By name / formula   │
│  • Exact: name/IUPAC │          │  • Caches to JSON      │
│  • Exact: CAS        │          │  • Timeout handling    │
│  • Fuzzy: thefuzz    │          └────────────────────────┘
└──────────┬───────────┘
           │  ChemicalRecord
           ▼
  ┌───────────────────────────────────────────┐
  │            Core Analytics                 │
  │                                           │
  │  formula_parser.py                        │
  │  ├── parse_formula("Ca(OH)2")             │
  │  │     → {Ca:1, O:2, H:2}                │
  │  └── calculate_molar_mass("NaCl")         │
  │        → 58.44 g/mol                      │
  │                                           │
  │  property_matcher.py                      │
  │  ├── compare_measurements(record, meas)   │
  │  │     → MatchResult (score 0–100)        │
  │  └── rank_candidates(candidates, meas)    │
  │        → sorted MatchResult list          │
  │                                           │
  │  safety_advisor.py                        │
  │  ├── render_safety_summary(record)        │
  │  ├── expand_h_statements(codes)           │
  │  └── generate_disclaimer()               │
  └───────────────────────────────────────────┘
           │
           ▼
  ┌───────────────────┐
  │  Pydantic Models  │
  │  chemical_schema  │
  │  ─────────────── │
  │  ChemicalRecord   │
  │  PhysicalProps    │
  │  SafetyInfo       │
  │  MeasuredProps    │
  │  MatchResult      │
  └───────────────────┘
```

---

## Features

| Feature | Description |
|---|---|
| 🔍 **Direct Lookup** | Search by name, IUPAC name, Hill formula, or CAS number |
| 🧪 **Measurement Matching** | Compare measured properties to reference data with tolerance scoring |
| ⚠️ **Safety Review** | Full GHS H/P statements, NFPA 704, signal word, SDS summary |
| 🌐 **PubChem Fallback** | Automatic API query when local database has no match |
| 🔬 **Formula Analysis** | Parse formulas, calculate molar mass, validate against reference |
| 🧯 **Compatibility Check** | Screen mixtures for acid/base, oxidizer/flammable, and other hazards |
| 💾 **Caching** | PubChem results cached to `data/pubchem_cache.json` |
| 🧩 **Fuzzy Search** | Typo-tolerant name matching via `thefuzz` |

---

## Example Walkthrough

### Input: `NaCl`

**Tab 1 – Direct Lookup**

| Field | Value |
|---|---|
| Chemical Name | Sodium chloride |
| IUPAC Name | Sodium chloride |
| Formula | `NaCl` |
| CAS Number | 7647-14-5 |
| SMILES | `[Na+].[Cl-]` |
| **Molar Mass** | **58.44 g/mol** |
| **Melting Point** | **801.0 °C** |
| **Boiling Point** | **1413.0 °C** |
| **Density** | **2.165 g/cm³** |
| Appearance | White crystalline solid |
| State | Solid |
| Water Solubility | Highly soluble (360 g/L at 20 °C) |

**GHS Safety**

| Field | Value |
|---|---|
| Signal Word | Warning |
| H-Statements | H319 – Causes serious eye irritation |
| P-Statements | P264, P305+P351+P338 |
| NFPA 704 | Health: 1 \| Flammability: 0 \| Instability: 0 |

---

### Tab 2 – Measurement Verification

**Scenario:** You measure an unknown white solid with density 2.14 g/cm³ and melting point ~820 °C.

| Property | Reference (NaCl) | Measured | Error % | Status |
|---|---|---|---|---|
| Melting Point (°C) | 801.0 | 820.0 | 2.37% | ✅ Within Tolerance (±5%) |
| Density (g/cm³) | 2.165 | 2.140 | 1.15% | ✅ Within Tolerance (±10%) |
| State | solid | solid | — | ✅ Match |

**Match Confidence Score: ~95%**

---

## Measurement Matching Algorithm

The property comparator computes a confidence score (0–100) for each candidate.

### Relative Error

For each numeric property:

$$\text{Error\%} = \frac{|\text{measured} - \text{reference}|}{|\text{reference}|} \times 100$$

### Default Tolerances

| Property | Default Tolerance |
|---|---|
| Melting Point | ±5% |
| Boiling Point | ±5% |
| Density | ±10% |

### Scoring

Each property contributes a score contribution in [0, 1]:

- **Within tolerance:** `score = 1.0 − (error% / tolerance%) × 0.2` (max 20% penalty inside tolerance)
- **Outside tolerance:** `score = max(0, 0.8 − excess_error / (2 × tolerance%))`

The final confidence score is the **weighted average** of all property contributions × 100:

$$\text{Confidence} = \frac{\sum_{i} w_i \cdot s_i}{\sum_{i} w_i} \times 100$$

Numeric properties (melting point, boiling point, density) have weight **1.0**.  
Qualitative properties (appearance, state) have weight **0.5**.

---

## Quickstart

### Prerequisites

- Python 3.11+
- `pip`

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/sohamrp172-sys/ChemCheck-Chemical-Identification-System.git
cd ChemCheck-Chemical-Identification-System

# 2. Install dependencies
pip install -r requirements.txt

# 3. Generate the chemical database
python data/seed_data.py

# 4. Launch the dashboard
streamlit run app.py
```

The app will open at `http://localhost:8501`.

### Run Tests

```bash
pytest tests/ -v
```

---

## Project Structure

```
ChemCheck-Chemical-Identification-System/
│
├── app.py                          # Streamlit dashboard (3-tab UI)
│
├── data/
│   ├── seed_data.py                # Generates chemicals.json (27 chemicals)
│   ├── chemicals.json              # Local chemical database (auto-generated)
│   ├── ghs_reference.json          # GHS H/P codes → descriptions
│   └── pubchem_cache.json          # PubChem API cache (auto-generated)
│
├── src/
│   ├── models/
│   │   └── chemical_schema.py      # Pydantic v2 data models
│   │
│   ├── database/
│   │   ├── db_manager.py           # In-memory DB, indexed + fuzzy search
│   │   └── pubchem_fallback.py     # PubChem PUG-REST API client
│   │
│   └── core/
│       ├── formula_parser.py       # Formula → composition + molar mass
│       ├── property_matcher.py     # Measurement comparison + scoring
│       └── safety_advisor.py       # GHS expansion + disclaimer generator
│
├── tests/
│   └── test_chemcheck.py           # pytest suite (30+ test cases)
│
├── requirements.txt
└── README.md
```

---

## Testing

The test suite (`pytest`) covers:

| Test Class | Coverage |
|---|---|
| `TestFormulaParser` | Simple/complex formula parsing, molar mass calculation, error cases |
| `TestLocalDatabaseExactSearch` | Name, formula, CAS exact lookups; spot-check 25+ chemicals |
| `TestFuzzySearch` | Typo tolerance, threshold filtering, scored result tuples |
| `TestPropertyMatcherTolerances` | Within-tolerance density/MP/BP, perfect match score, neutral baseline |
| `TestDiscrepancyDetection` | Melting point 150°C vs 801°C, wrong density, wrong state, multi-discrepancy |

```bash
pytest tests/ -v --tb=short
```

---

## Analytical Limitations & Safety Disclaimer

Physical property matching (density, melting point, boiling point, appearance) provides **indicative screening only**.

ChemCheck results **must not** be used as the sole basis for:

- Confirming the identity of an unknown chemical substance
- Making safety or regulatory compliance decisions
- Authorising the use of a substance in critical processes

**Definitive identification requires one or more of:**

- Nuclear Magnetic Resonance spectroscopy (NMR)
- Fourier-Transform Infrared spectroscopy (FTIR)
- Gas Chromatography–Mass Spectrometry (GC-MS)
- Liquid Chromatography–Mass Spectrometry (LC-MS)
- X-Ray Diffraction (XRD) for crystalline solids
- Inductively Coupled Plasma (ICP) for elemental composition

Always consult the original container label, Safety Data Sheet (SDS), and your institution's chemical hygiene plan before working with any laboratory chemical.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">Built for laboratory education and research reference purposes.</p>
