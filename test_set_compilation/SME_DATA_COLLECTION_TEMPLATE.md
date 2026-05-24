# SME Data Collection Instructions

> **Audience:** Patent search Subject Matter Experts (SMEs) collecting ground truth data for agent evaluation.
>
> **What we need from you:** Submit invention cases from your own real or past novelty assessments. For each case, you provide (1) the invention disclosure and (2) your ground truth assessment (features, references, verdict, search strategy). We will run our AI agent on your disclosures and compare its output to yours.
>
> **How to use this document:** Read this guide to understand the process, standards, and expectations. For each case you submit, copy the blank form from **[SME_GROUND_TRUTH_FORM.md](SME_GROUND_TRUTH_FORM.md)** and fill it in. This document explains *how* to fill it in; the form is *what* you fill in.

---

## Part A: Quick Reference Card

### What You Submit Per Case

| Deliverable | Format | When |
|-------------|--------|------|
| **Combined form** (disclosure + ground truth) | Copy of [SME_GROUND_TRUTH_FORM.md](SME_GROUND_TRUTH_FORM.md) — Part A (disclosure) + Part B (ground truth) | Initial submission |
| **Mode 2 review** _(optional)_ | Copy of [SME_MODE2_REVIEW_FORM.md](SME_MODE2_REVIEW_FORM.md) | After we send you the agent's output — see [Mode 2 instructions](SME_MODE2_REVIEW_INSTRUCTIONS.md) |

### Time Expectations (Mode 1)

| Difficulty Band | Expected Time |
|----------------|--------------|
| Easy | 2–3 hours |
| Medium | 4–6 hours |
| Hard | 6–10 hours |

### Checklist Before Submission

**Part A — Invention Disclosure (in the form):**
- [ ] All disclosure fields filled in (title, technical field, background, proposed solution, key aspects)
- [ ] Disclosure is 200–800 words
- [ ] Disclosure does NOT contain patent numbers, search strategies, or novelty conclusions
- [ ] Client information redacted (if from a real engagement)

**Part B — Ground Truth (in the form):**
- [ ] Sections 1–6 completed
- [ ] Every search query recorded with result counts
- [ ] Every A-level and B-level reference has feature coverage (Y/Y1/N) for ALL features
- [ ] Every A-level reference has pin-cites (claim numbers, paragraphs, or figures)
- [ ] Final verdict includes per-feature risk assessment
- [ ] Time tracking filled in
- [ ] Perceived difficulty rating provided

---

## Part B: Disclosure Guidance

When filling in Part A of the form, follow these guidelines. The disclosure describes the invention and is what gets fed to the agent. Select a case from your own real or past novelty assessments. If the case is from a client engagement, redact any client-identifying information.

```markdown
---
case_id: "TST-{SUBDOMAIN}-{SEQ:03d}"
domain: "Gear Systems | Actuators & Mechanisms | Structural & Packaging | Fluid & Pneumatic | Thermal Management | MEMS & Micro-Mechanisms | Cross-Mechanical"
difficulty: "easy | medium | hard"
source: "synthetic"
created_by: "{your_name}"
created_date: "YYYY-MM-DD"
---

# Invention Disclosure

## Title
[Descriptive title, 10–20 words]

## Technical Field
[1–2 sentences identifying the technical area]

## Background / Problem Statement
[2–4 sentences: what problem exists, what current solutions look like,
why they fall short]

## Proposed Solution
[3–6 sentences: describe the invention with enough detail for 3–7
searchable features. Be specific about components, materials,
mechanisms, or algorithms.]

## Key Technical Aspects
1. [Most novel aspect]
2. [Second aspect]
3. [Third aspect]
... (up to 7)
```

**Rules for the disclosure:**
- 200–800 words total
- Do NOT include patent numbers, IPC codes, or search strategies — the agent must discover these on its own
- Do NOT embed novelty conclusions (no "this is novel because...")
- Write as if you are an inventor describing your idea to a patent searcher for the first time
- If from a real client case, redact client name and any confidential identifiers

### Worked Example: Easy Case

```markdown
---
case_id: "TST-THRM-001"
domain: "Thermal Management"
difficulty: "easy"
source: "synthetic"
created_by: "Jane Smith"
created_date: "2026-03-01"
---

# Invention Disclosure

## Title
Self-Adjusting Bicycle Helmet with Integrated Ventilation Channels

## Technical Field
Protective headwear for cycling, specifically bicycle helmets with
ventilation systems.

## Background / Problem Statement
Conventional bicycle helmets use fixed vent openings that cannot adapt to
riding conditions. In cold weather, open vents cause heat loss. In hot
weather, riders want maximum airflow. Existing solutions use manual sliders
or removable plugs, which are inconvenient to operate while riding.

## Proposed Solution
A bicycle helmet with a network of internal ventilation channels connected
to temperature-responsive shape-memory alloy (SMA) actuators. When the
ambient temperature rises above a threshold (e.g., 25°C), the SMA
actuators expand and open additional vent pathways. Below the threshold,
the actuators contract and close the vents. The system requires no
batteries or manual operation. The SMA actuators are embedded in the
helmet's EPS foam liner and connected to vent louvers on the outer shell.

## Key Technical Aspects
1. Temperature-responsive SMA actuators for automatic vent control
2. Internal ventilation channel network within EPS foam
3. Vent louvers on outer shell linked to SMA elements
4. No-battery, passive actuation system
```

### Worked Example: Hard Case

```markdown
---
case_id: "TST-XMEC-001"
domain: "Cross-Mechanical"
difficulty: "hard"
source: "synthetic"
created_by: "Jane Smith"
created_date: "2026-03-01"
---

# Invention Disclosure

## Title
Shape-Memory Alloy Compliant Gripper with Embedded Strain-Sensing
Lattice for Sub-Millimetre Micro-Assembly

## Technical Field
Micro-manipulation grippers combining compliant mechanism design with
shape-memory alloy actuation and integrated strain sensing.

## Background / Problem Statement
Existing micro-assembly grippers rely on piezoelectric actuators with
rigid flexure hinges, limiting stroke range and making force feedback
difficult. Conventional strain gauges bonded to flexures add mass and
assembly steps, and their wiring is fragile at sub-millimetre scale.
There is no current solution that integrates actuation, compliance, and
force sensing into a single monolithic structure suitable for pick-and-
place of components below 500 µm.

## Proposed Solution
A monolithic compliant gripper fabricated from a nickel-titanium (NiTi)
sheet by laser micro-machining. The gripper arms are shaped as curved
compliant beams that open/close when heated by passing current through
the NiTi structure itself (self-actuating SMA). A lattice pattern cut
into the beam functions as an integrated strain gauge: as the beam
deflects, the lattice geometry changes, altering its electrical
resistance proportionally to grip force. A Wheatstone bridge circuit
reads resistance changes to provide real-time force feedback without
external sensors. The entire gripper is under 3 mm wide and mounts
directly on a micro-positioning stage.

## Key Technical Aspects
1. Monolithic NiTi compliant gripper fabricated by laser micro-machining
2. Self-actuating SMA: resistive heating of the NiTi structure itself
3. Integrated strain-sensing lattice cut into compliant beams
4. Wheatstone bridge readout for real-time force feedback
5. Sub-3 mm form factor for micro-component handling (< 500 µm parts)
6. No external sensors, actuators, or bonded elements — fully monolithic
```

---

## Part C: Blank Form

For each case, copy the blank form from **[SME_GROUND_TRUTH_FORM.md](SME_GROUND_TRUTH_FORM.md)** and save it as `GT-{case_id}.md`. The form contains everything you need to fill in: the invention disclosure (Part A) and the ground truth assessment (Part B). The guidance below (Parts D and E) explains how to fill in Part B correctly.

### What the form covers

| Form Section | What to Fill In |
|-------------|----------------|
| **Part A: Invention Disclosure** | Case metadata, title, technical field, background, proposed solution, key technical aspects |
| **Part B, Section 1: Case Metadata** | Your name, date, time tracking |
| **Part B, Section 2: Perceived Difficulty** | Assigned band, your 1–5 rating, notes |
| **Part B, Section 3: Expected Key Features** | 3–7 features with name, description, core flag, keywords, type |
| **Part B, Section 4: Blocking Prior Art** | Reference summary table + detail block per A/B ref (pin-cites, feature coverage, notes) |
| **Part B, Section 5: Search Strategy** | Databases, queries, vocabulary discovered, narrative |
| **Part B, Section 6: Final Verdict** | Overall verdict, per-feature risk, claim guidance |
| _(Mode 2 review is a separate form — see [SME_MODE2_REVIEW_FORM.md](SME_MODE2_REVIEW_FORM.md))_ | |

### Minimum expected reference counts by difficulty

| Difficulty | A-refs | B-refs | C-refs | Total |
|-----------|--------|--------|--------|-------|
| Easy | 2–5 | 3–8 | 2–5 | 7–18 |
| Medium | 1–4 | 4–10 | 3–8 | 8–22 |
| Hard | 0–2 | 2–6 | 3–10 | 5–18 |

---

## Part D: Triage & Coverage Standards

### D.1 Triage Label Definitions (A/B/C)

Use these definitions consistently across all cases.

#### A — High Relevance

- **Directly impacts novelty** — would be cited by a patent examiner in a rejection
- Describes substantially the same invention, technique, or core combination of features
- Discloses one or more **core features** explicitly
- **Action required:** Full feature mapping with pin-cites (claim #, paragraph #, figure #)

**Example:** A patent that discloses "two worm stages in series coupled by an intermediate gear" when the invention is a dual-worm gearbox with adapter gear.

#### B — Medium Relevance

- Related technology with **partial overlap**
- Discloses some features but **not the core combination**
- Different application of similar principles
- Would be cited as background art, not as a novelty-destroying reference
- **Action required:** Feature mapping (Y/Y1/N per feature), brief notes

**Example:** A patent for a compact worm gearbox used in camera modules (relevant to the packaging feature, but does not disclose dual-worm stages).

#### C — Low Relevance (Peripheral)

- Background information only
- Same technical field but different approach or problem
- Does not impact the novelty assessment
- **Action required:** Record title and ref ID only, no feature mapping needed

**Example:** A general review paper on micro-actuator technologies that mentions worm gears among many other types.

### D.2 Feature Coverage Labels (Y / Y1 / N)

| Label | Meaning | When to Use |
|-------|---------|-------------|
| **Y** (Yes) | Feature is **explicitly disclosed** in the reference | The reference clearly describes this feature. A reader would recognize it without interpretation. |
| **Y1** (Partial) | Feature is **partially or implicitly disclosed** | The reference describes something close but not identical, or the feature can be inferred but is not explicitly stated. The reference uses different terminology for a functionally similar concept. |
| **N** (No) | Feature is **not disclosed** in the reference | The reference does not describe this feature or anything reasonably similar. |

**Examples for a "dual-worm gear with adapter gear" invention:**

| Scenario | Label | Reasoning |
|----------|-------|-----------|
| Reference explicitly shows "two worm stages coupled by a spur gear" | Y for F1 (dual worm) and F2 (adapter gear) | Exact match |
| Reference shows "two worm wheels on a common shaft with pinions" | Y1 for F1 | Functionally similar staged reduction, but different coupling topology |
| Reference shows "single worm gear in a camera module" | N for F1, Y for F3 (compact packaging) | No dual-worm, but relevant to packaging |

### D.3 When to Mark a Feature as Core

A feature is **Core** if:
1. It represents the **inventive step** — the thing that makes this invention different from what came before
2. Removing this feature would make the remaining invention **clearly anticipated** by prior art
3. It would appear in **independent claim 1** of a patent application

A feature is **Non-Core** if:
1. It provides useful context but is itself a **known/standard technique**
2. It would appear in **dependent claims** or the description, not in claim 1
3. Its absence would NOT destroy novelty of the overall invention

**Rule of thumb:** A case should have 1–3 core features and 2–4 non-core features.

### D.4 Pin-Cite Format

When providing pin-cites for A and B references, use this format:

```
Claims 1, 5, 12; Para [0023]-[0025]; Fig. 2, 4A
```

- **Claims:** List specific claim numbers that are relevant
- **Paragraphs:** Use paragraph numbers in brackets [0023] as they appear in the patent
- **Figures:** Reference specific figure numbers
- **For NPL:** Use page numbers and section headers instead: `pp. 234-236, Section 3.2, Fig. 5`

Pin-cites are **required** for all A-level references and **recommended** for B-level references.

---

## Part E: Alignment Before You Start

### Before Submitting Cases

1. **Read this entire document** — especially Part D (Triage & Coverage Standards)
2. **Attend the alignment session** where all SMEs review the standards together
3. **Discuss and align on:**
   - Where is the A vs B threshold? What makes a reference "directly impacting novelty" vs "background"?
   - How do we apply Y1 vs Y? What counts as "partial" disclosure?
   - What makes a feature "core"? Would it appear in independent claim 1?
4. **Optionally, one SME submits a pilot case early** — the group reviews the submission to calibrate expectations
5. **Document any team agreements** that clarify or refine the definitions in Part D

### Tips for Selecting Cases to Submit

- Choose cases where you have **thorough knowledge** of the prior art landscape
- Include a **mix of difficulties** — don't only submit easy or only hard cases
- Aim for **sub-domain diversity within mechanical engineering** — e.g., don't submit 10 gear cases; mix in actuators, thermal, structural, etc.
- Cases where the novelty answer is **ambiguous** (partial) are especially valuable
- Older cases are fine — the agent will search current databases, so differences from when you originally searched are expected and informative

---

## Appendix: Ground Truth JSON Format

For engineering integration, your filled template will be converted to this JSON structure. You do NOT need to produce the JSON yourself — the engineering team will convert your template responses. This appendix is provided for reference.

```json
{
  "case_id": "TST-GEAR-001",
  "collection_mode": "independent",
  "sme_id": "SME-JS",
  "collection_date": "2026-03-15",
  "total_time_minutes": 300,
  "time_breakdown": {
    "scoping_minutes": 30,
    "feature_definition_minutes": 45,
    "search_execution_minutes": 150,
    "triage_and_mapping_minutes": 45,
    "report_synthesis_minutes": 30
  },
  "perceived_difficulty": {
    "assigned_band": "medium",
    "sme_perceived": 3,
    "difficulty_notes": "Multi-database search needed, some non-standard vocab"
  },
  "features": [
    {
      "id": "F1",
      "name": "Dual-worm reduction architecture",
      "description": "Two worm stages in one transmission for high reduction",
      "is_core": true,
      "keywords": ["dual worm", "two-stage worm", "compound worm"],
      "type": "Structural"
    }
  ],
  "references": [
    {
      "ref_id": "WO2011003643A1",
      "ref_type": "patent",
      "title": "Force transmission assembly",
      "source_database": "innography",
      "discovery_method": "keyword",
      "triage_label": "A",
      "feature_coverage": {"F1": "Y1", "F2": "Y1", "F3": "Y1"},
      "pin_cites": "Claims 1, 5; Para [0023]; Fig. 2",
      "priority_date": "2009-07-06",
      "blocking_potential": "high",
      "sme_notes": "Two worm wheels + pinions, functionally close"
    }
  ],
  "search_strategy": {
    "databases_used": ["innography", "wos", "ngsp"],
    "total_queries_executed": 15,
    "queries": [
      {
        "database": "innography",
        "query_text": "@(dwpi_title,dwpi_abstract) (worm NEAR/5 gear)",
        "result_count": 47,
        "refs_kept": ["WO2011003643A1", "EP0465292A1"],
        "rationale": "Initial broad search for F1"
      }
    ],
    "vocabulary_discovered": ["worm-on-worm", "tandem worm"],
    "strategy_notes": "Started with DWPI title/abstract search..."
  },
  "verdict": {
    "overall": "partial",
    "confidence": "medium",
    "per_feature_risk": {
      "F1": {"risk": "high", "closest_ref": "WO2011003643A1", "gap_description": "..."},
      "F2": {"risk": "medium", "closest_ref": "CN202527804U", "gap_description": "..."}
    },
    "novelty_resides_in": "Specific coupling topology Worm1→adapter→Worm2 in thin package",
    "claim_drafting_guidance": "Focus claims on the serial coupling arrangement..."
  }
}
```
