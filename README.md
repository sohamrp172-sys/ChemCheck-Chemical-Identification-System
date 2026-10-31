# ⚗️ ChemCheck — Chemical Identification System

![ChemCheck](https://img.shields.io/badge/ChemCheck-Chemical%20Identification%20System-0d6efd?style=for-the-badge&logo=flask)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.35+-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-v2-E92063?style=flat-square)
![Pytest](https://img.shields.io/badge/Tests-40%20Passing-22c55e?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-22c55e?style=flat-square)

### 🌐 Live Dashboard → [https://chemcheck-chemical-identification-system-n3gymdkq8ec3k4w8pzhdw.streamlit.app](https://chemcheck-chemical-identification-system-n3gymdkq8ec3k4w8pzhdw.streamlit.app)

> **An intelligent laboratory chemical identification and verification system. Identify chemicals by name, formula, or CAS number — match experimental measurements to reference data — review GHS safety information.**

ChemCheck is a dual-layer chemical identification pipeline built for laboratory environments. Enter a chemical name, Hill formula, or CAS number and instantly retrieve verified physical constants, GHS hazard classifications, NFPA 704 ratings, H/P-statements, and SDS summaries. Enter your own experimental measurements and the system scores how closely your sample matches any chemical in the database — flagging discrepancies outside tolerance thresholds. When the local database has no match, ChemCheck falls back automatically to the PubChem PUG-REST API.

---

> ⚠️ **CRITICAL DISCLAIMER:** ChemCheck is an informational reference and screening assistant **only**.  
> Unknown substances **require definitive analytical validation** (FTIR, NMR, GC-MS) before handling.  
> Do not rely solely on physical property matching for identification or safety decisions.

---

## 📲 QR Code

Scan to open ChemCheck instantly on any phone or tablet — no typing needed.

[![ChemCheck QR Code](https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=https://chemcheck-chemical-identification-system-n3gymdkq8ec3k4w8pzhdw.streamlit.app)](https://chemcheck-chemical-identification-system-n3gymdkq8ec3k4w8pzhdw.streamlit.app)

**🌐 Live link:** [https://chemcheck-chemical-identification-system-n3gymdkq8ec3k4w8pzhdw.streamlit.app](https://chemcheck-chemical-identification-system-n3gymdkq8ec3k4w8pzhdw.streamlit.app)

> Point your phone camera at the QR code above to open the dashboard directly. Great for lab demonstrations — display it on screen or print it alongside your setup.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🔍 **Direct Lookup** | Search by common name, IUPAC name, Hill formula, or CAS registry number |
| 🧪 **Measurement Matching** | Enter measured melting point, boiling point, density and appearance — get a 0–100% confidence score |
| ⚠️ **GHS Safety Review** | Full H-statements, P-statements, pictograms, NFPA 704 diamond, signal word, SDS summary |
| 🌐 **PubChem Fallback** | Auto-queries PubChem PUG-REST API when local DB has no match |
| 🔬 **Formula Analysis** | Parses any formula (including nested parentheses), calculates theoretical molar mass |
| 🧯 **Compatibility Checker** | Screens chemical mixtures for acid/base, oxidizer/flammable, and other reactivity hazards |
| 💾 **API Caching** | PubChem results cached locally to `data/pubchem_cache.json` — no redundant calls |
| 🧩 **Fuzzy Search** | Typo-tolerant name matching via `thefuzz` — `"sodum chlorid"` still finds Sodium chloride |
| 📊 **Comparison Table** | Per-property breakdown of Reference vs Measured vs Error% vs Tolerance status |
| 🏗️ **Pydantic v2 Models** | Strictly typed data models throughout — validation at every layer |

---

## 🔬 How It Works — Dual-Layer Identification Pipeline

ChemCheck queries a curated local database first, then falls back to PubChem if needed, then runs the property comparator to score candidates.

### System Architecture

```
  User Input (Name / Formula / CAS / Measurements)
          │
          ▼
  ┌───────────────────┐
  │      app.py       │  ◄── Streamlit Dashboard (3 tabs)
  └────────┬──────────┘
           │
    ┌──────┴──────────────────────────────────┐
    │                                         │
    ▼                                         ▼
┌──────────────────────┐          ┌────────────────────────┐
│   db_manager.py      │          │  pubchem_fallback.py   │
│   Local Database     │  NO HIT  │  PubChem PUG-REST API  │
│  ─────────────────   │ ───────► │  ──────────────────    │
│  • Exact: formula    │          │  • Resolve by name     │
│  • Exact: name/IUPAC │          │  • Resolve by formula  │
│  • Exact: CAS        │          │  • Cache to JSON       │
│  • Fuzzy: thefuzz    │          │  • Timeout handling    │
└──────────┬───────────┘          └────────────────────────┘
           │  ChemicalRecord
           ▼
  ┌──────────────────────────────────────────────┐
  │               Core Analytics                 │
  │                                              │
  │  formula_parser.py                           │
  │  ├── parse_formula("Ca(OH)2")                │
  │  │     → {Ca:1, O:2, H:2}                   │
  │  └── calculate_molar_mass("NaCl")            │
  │        → 58.44 g/mol                         │
  │                                              │
  │  property_matcher.py                         │
  │  ├── compare_measurements(record, measured)  │
  │  │     → MatchResult (confidence 0–100)      │
  │  └── rank_candidates(all_chemicals, meas)    │
  │        → top-N sorted MatchResult list       │
  │                                              │
  │  safety_advisor.py                           │
  │  ├── expand_h_statements(["H314", "H335"])   │
  │  ├── render_safety_summary(record)           │
  │  └── generate_disclaimer()                   │
  └──────────────────────────────────────────────┘
           │
           ▼
  ┌───────────────────┐
  │  Pydantic Models  │
  │  ───────────────  │
  │  ChemicalRecord   │
  │  PhysicalProps    │
  │  SafetyInfo       │
  │  MeasuredProps    │
  │  MatchResult      │
  └───────────────────┘
```

### Identification Pipeline Steps

```
Enter query (name / formula / CAS)
       ↓
Step 1 — Exact CAS lookup (normalised, hyphens stripped)
       ↓
Step 2 — Exact name / IUPAC name lookup (case-insensitive)
       ↓
Step 3 — Exact Hill formula lookup (case-insensitive)
       ↓
Step 4 — Fuzzy name search (thefuzz token_sort_ratio, threshold 65)
       ↓
Step 5 — PubChem PUG-REST fallback (if no local hits)
       ↓
ChemicalRecord returned
       ↓
Display: identity card → KPI metrics → physical properties
         → GHS safety → formula validation
```

---

## 📊 Measurement Matching Algorithm

The property comparator scores each candidate chemical from 0 to 100% based on how closely your measurements match the reference constants.

### Relative Error Formula

$$\text{Error\%} = \frac{|\text{measured} - \text{reference}|}{|\text{reference}|} \times 100$$

### Default Tolerance Thresholds

| Property | Default Tolerance | Weight |
|---|---|---|
| Melting Point | ±5% | 1.0 |
| Boiling Point | ±5% | 1.0 |
| Density | ±10% | 1.0 |
| Appearance | Text similarity | 0.5 |
| State (solid/liquid/gas) | Exact category match | 0.5 |

### Score Contribution Per Property

| Condition | Score Formula |
|---|---|
| Within tolerance | `score = 1.0 − (error% ÷ tolerance%) × 0.2` |
| Outside tolerance | `score = max(0, 0.8 − excess_error ÷ (2 × tolerance%))` |

### Final Confidence Score

$$\text{Confidence} = \frac{\sum_{i} w_i \cdot s_i}{\sum_{i} w_i} \times 100$$

### Example — NaCl Verification

| Property | Reference | Measured | Error % | Status |
|---|---|---|---|---|
| Melting Point (°C) | 801.0 | 820.0 | 2.37% | ✅ Within ±5% |
| Density (g/cm³) | 2.165 | 2.140 | 1.15% | ✅ Within ±10% |
| State | solid | solid | — | ✅ Match |

**Match Confidence Score: ~95%**

---

## 🧪 Example Walkthrough

### Input: `NaCl`

**Tab 1 – Direct Lookup**

| Field | Value |
|---|---|
| Chemical Name | Sodium chloride |
| IUPAC Name | Sodium chloride |
| Formula | `NaCl` |
| CAS Number | `7647-14-5` |
| SMILES | `[Na+].[Cl-]` |
| **Molar Mass** | **58.44 g/mol** |
| **Melting Point** | **801.0 °C** |
| **Boiling Point** | **1413.0 °C** |
| **Density** | **2.165 g/cm³** |
| Appearance | White crystalline solid |
| State | Solid |
| Water Solubility | Highly soluble (360 g/L at 20 °C) |

**GHS Safety Data**

| Field | Value |
|---|---|
| Signal Word | Warning |
| Pictograms | — |
| H-Statements | H319 – Causes serious eye irritation |
| P-Statements | P264, P305+P351+P338 |
| NFPA 704 | Health: 1 · Flammability: 0 · Instability: 0 |
| Hazard Level | 🟢 Low |

---

## 🧯 Safety & Compatibility Checker

The compatibility tab screens any combination of selected chemicals for known reactivity hazards:

| Hazard Rule | Example | Severity |
|---|---|---|
| Strong acid + strong base | HCl + NaOH | 🔴 DANGER |
| Oxidizer + flammable solvent | KMnO₄ + Acetone | 🔴 DANGER |
| Iodine + ammonia → NI₃ | I₂ + NH₃ | 🔴 DANGER |
| H₂O₂ + methanol | H₂O₂ + CH₃OH | 🔴 DANGER |
| KMnO₄ + organic solvent | KMnO₄ + Ethanol | 🔴 DANGER |
| Oxidizer + strong base | HNO₃ + KOH | 🟠 WARNING |
| Ammonia + acid | NH₃ + HCl | 🟠 WARNING |

---

## 📋 Chemical Database

27 verified laboratory chemicals across 5 families, each with accurate empirical constants and GHS data.

| Family | Chemicals |
|---|---|
| 🧂 **Inorganic Salts** | NaCl, KCl, CuSO₄, NaHCO₃, CaCO₃ |
| 🧪 **Acids** | HCl, H₂SO₄, HNO₃, CH₃COOH |
| 🧫 **Bases** | NaOH, KOH, NH₃ |
| 🧴 **Solvents** | Ethanol, Methanol, Acetone, Isopropanol, DCM, Hexane, Toluene, Benzene, Ethyl acetate, Diethyl ether, Chloroform |
| 🔬 **Indicators & Reagents** | Phenolphthalein, Iodine, KMnO₄, H₂O₂ |

---

## 🚀 Quickstart

### Prerequisites

- Python 3.11+
- pip

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

The app opens at `http://localhost:8501`.

### Run Tests

```bash
pytest tests/ -v
```

---

## 📖 Usage

### Tab 1 — Direct Lookup

1. Type a chemical name (`Sodium chloride`), formula (`NaCl`), or CAS number (`7647-14-5`) in the search bar
2. Click **Search**
3. View the identity card, KPI metric cards (molar mass, MP, BP, density), physical properties, and GHS safety panel
4. Expand **Formula Analysis** to see elemental composition and molar mass validation

### Tab 2 — Unknown Verification

1. Select observed state (solid / liquid / gas) and type an appearance description
2. Check the properties you measured and enter values (supports °C or K toggle)
3. Choose **Compare all** to rank all database chemicals, or **Select specific** for a single candidate
4. Click **▶ Run Verification**
5. Review the ranked match list — each entry shows a confidence score bar and a per-property comparison table

### Tab 3 — Safety & Compatibility

1. Select 2–6 chemicals from the multiselect dropdown
2. The system displays a summary table and runs the reactivity rule engine
3. Hazard alerts are shown with severity colour coding (red = danger, amber = warning)
4. Expand individual chemical panels for full H/P-statement details

---

## 🛠️ Technologies Used

| Technology | Purpose |
|---|---|
| **Python 3.11** | Core language |
| **Streamlit 1.35+** | Interactive web dashboard |
| **Pydantic v2** | Strictly typed data models and validation |
| **thefuzz + python-Levenshtein** | Fuzzy string matching for typo-tolerant search |
| **requests** | PubChem PUG-REST API client |
| **pandas** | Property comparison DataFrames in the UI |
| **pytest** | 40-test automated test suite |
| **difflib** | Fallback fuzzy matching when thefuzz unavailable |

---

## 📁 Project Structure

```
ChemCheck-Chemical-Identification-System/
│
├── app.py                          ← Streamlit dashboard (3 tabs)
│
├── data/
│   ├── seed_data.py                ← Generates chemicals.json (27 chemicals)
│   ├── chemicals.json              ← Local chemical database (auto-generated)
│   ├── ghs_reference.json          ← GHS H/P codes → full descriptions
│   └── pubchem_cache.json          ← PubChem API cache (auto-generated)
│
├── src/
│   ├── models/
│   │   └── chemical_schema.py      ← Pydantic v2 models (5 models)
│   │
│   ├── database/
│   │   ├── db_manager.py           ← In-memory DB, indexed + fuzzy search
│   │   └── pubchem_fallback.py     ← PubChem PUG-REST client + cache
│   │
│   └── core/
│       ├── formula_parser.py       ← Formula parser + molar mass calculator
│       ├── property_matcher.py     ← Measurement comparison + 0–100 scoring
│       └── safety_advisor.py       ← GHS expansion + disclaimer generator
│
├── tests/
│   └── test_chemcheck.py           ← pytest suite — 40 tests, 5 test classes
│
├── requirements.txt
└── README.md
```

---

## 🧪 Test Suite

40 automated tests across 5 classes — all passing.

| Test Class | Tests | What It Covers |
|---|---|---|
| `TestFormulaParser` | 12 | Simple/complex parsing, nested parentheses, molar mass, error cases |
| `TestLocalDatabaseExactSearch` | 10 | Name, formula, CAS lookups; case-insensitivity; 25+ chemical spot-checks |
| `TestFuzzySearch` | 6 | Typo variants, threshold filtering, scored tuple format |
| `TestPropertyMatcherTolerances` | 7 | Within-tolerance density/MP/BP, perfect match score, neutral baseline |
| `TestDiscrepancyDetection` | 5 | 150°C vs 801°C MP, wrong density, wrong state, multi-discrepancy |

```bash
pytest tests/ -v --tb=short

# Expected output:
# 40 passed in 0.40s
```

---

## ⚠️ Analytical Limitations & Safety Disclaimer

Physical property matching provides **indicative screening only**.

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

## 📱 Dashboard Preview

| Tab | What You See |
|---|---|
| 🔍 **Direct Lookup** | Identity card · 4 KPI metric cards · Physical properties · GHS safety panel · Formula analysis |
| 🧪 **Unknown Verification** | Measurement inputs · Candidate selector · Confidence score bar · Per-property comparison table |
| ⚠️ **Safety & Compatibility** | Chemical summary table · Reactivity hazard alerts · Individual SDS expandable panels |

---

*Built with ⚗️ for laboratory education and chemical safety awareness · ChemCheck · Identify · Verify · Stay Safe*
