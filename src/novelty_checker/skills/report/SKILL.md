---
name: report
description: Final novelty report template with citation consolidation and synthesis guidelines
triggers:
  - report
  - synthesis
  - final
  - output
  - consolidate citations
---

# Report Skill

This skill guides you through Stage 5: Final Novelty Report Generation.

---

## Role in the Research Workflow

Report generation happens **AFTER**:
1. ✅ Iterative Research Loop completed (coverage targets met or max rounds)
2. ✅ Screening/Triaging completed (all A/B refs mapped)
3. ✅ Citations consolidated (unified numbering assigned)

Your job now is to synthesize all findings into a professional 11-section report.

---

## ⭐ Citation Consolidation (Pre-Report Step)

Before writing the report, ensure all citations are consolidated:

### Unified Citation Numbering

```markdown
## Citation Index (Use Throughout Report)

| Cite # | Publication Number | Type | Relevance | Short Title |
|--------|-------------------|------|-----------|-------------|
| [1] | US10234567B2 | Patent | A | UV-fluorescence polymer detection |
| [2] | JP2007171504A | Patent | A | Camera module with worm gears |
| [3] | WOS:000299510600010 | NPL | B | Compact Rotary SEA |
| [4] | CN106054342A | Patent | B | Dual worm pairs lens |
| [5] | EP3456789A1 | Patent | B | Inline quality monitoring |
```

### Citation Usage in Report

Use consolidated citation numbers throughout:
- **Inline citations**: "The closest prior art [1] shows UV detection but lacks inline monitoring [2]."
- **Feature Matrix**: Each row has both `Cite #` and `Publication Number`
- **Sources section**: List all citations with full bibliographic details

---

## Complete Report Structure (11 Sections)

Prepend a status banner:
```
**Status:** Stage 5 of 5 — Report Synthesis, Record View & QA
```

---

### Report Title (MANDATORY — first line of the report)

The very first line of the report MUST be a level-1 Markdown heading (`# ...`) that concisely names the invention. Derive the title from the confirmed scope and feature plan — it should read like a patent title: a short noun phrase (5–12 words, no articles, no verbs) capturing the inventive subject matter.

**Examples:**
- `# Modular Photovoltaic Panel Connector System`
- `# Sunscreen Emulsion with Silicone Emulsifier Blend`
- `# Dual Worm-Gear Cascade Transmission for Miniature Camera Actuation`
- `# Modular Floating Photovoltaic Platform with Cross-Support Pontoon Structure`

The title goes BEFORE the status banner and Section 1. Format:
```markdown
# <Invention Title Derived from Scope and Features>

## 1. Key Finding / Executive Summary
...
```

---

### 1. Key Finding / Executive Summary

This section provides the **novelty assessment snapshot** with Types of Solutions, Gap Analysis, and Risk Assessment.

Use consolidated citations inline: "Closest prior art [1] shows... [2] addresses... but lacks..."

```markdown
## 1. Key Finding / Executive Summary

### Key Finding: [Strong/Moderate/Weak] Novelty Indication

Your [invention description] demonstrates [strong/moderate/weak] novelty across [X] of [Y] core features. [No/Some/Significant] prior art was identified containing the complete combination of:

- **[F1 Name]** — [Brief description]
- **[F2 Name]** — [Brief description]
- **[F3 Name]** — [Brief description]
- **[F4 Name]** — [Brief description]
- **[F5 Name]** — [Brief description]

### Types of Solutions Identified

**[Category 1] (e.g., Current Market Technology):**
- Dominant technologies: [List dominant approaches] [1], [3]
- Alternative solutions: [Finding on alternatives] [4]
- Finding: [Gap identified in this category]

**[Category 2] (e.g., Industrial/Automotive Applications):**
- [Description of existing solutions] [2], [5]
- Finding: [Gap or overlap identified]

**[Category 3] (e.g., Multi-Stage Systems):**
- [Description of existing solutions]
- Gap: [What's missing]

### Key Features Covered vs. Missing (Gap Analysis Table)

| Feature | Coverage in Prior Art | Gap Analysis |
|---------|----------------------|--------------|
| F1: [Name] | Closest: [1] mentions [aspect] but [limitation] | [Gap finding] |
| F2: [Name] | [2], [4] show [aspect] | Partial gap — [limitation] |
| F3: [Name] | No prior art shows [aspect] | Complete gap — zero examples |
| F4: [Name] | Some systems [3] exist but [limitation] | No [specific architecture] |
| F5: [Name] | [5] achieves [goal] via [other methods] | No [method]-based systems |

### Main Technology/Competitor Trends

**[Market Segment 1]:**
- [Trend 1]: [Description with percentage if available]
- [Trend 2]: [Description]
- [Trend 3]: [Description]

**[Market Segment 2]:**
- [Trend 1]: [Description]
- [Trend 2]: [Description]
- No [specific aspect] trend: [Finding]

### Risk Assessment

**Novelty Risk:** [LOW/MEDIUM/HIGH]
- No X-category patent (containing all core features) found
- Closest prior art [1] lacks [N] of [M] core features
- The specific architectural innovation ([description]) is unprecedented

**Freedom to Operate Risk:** [LOW/MEDIUM/HIGH]
- [No/Some] active blocking patents in [domain]
- Existing patents [2], [4] are [limitation - e.g., "limited scope"]
- [Alternative technology] patents use [different principles]

**Market Opportunity:**
- [Blue ocean / Red ocean assessment]: [Finding]
- Technical gap: [Identified need description]
- Challenges: [Key challenges]
```

---

### 2. Scope

Present scope in **table format** with all elements:

```markdown
## 2. Scope

| Element | Details |
|---------|---------|
| **Objective** | Assess novelty and prior-art risk for [invention description] |
| **In-Scope** | • [Item 1]<br>• [Item 2]<br>• [Item 3]<br>• [Item 4]<br>• [Item 5] |
| **Out-of-Scope** | • [Item 1] (reference only for comparison)<br>• [Item 2] (unless directly comparable)<br>• [Item 3] |
| **Authorities** | All major patent offices (USPTO, EPO, CNIPA, JPO, KIPO, WIPO) + DWPI editorial coverage |
| **Languages** | English primary; CN/JP/KR transliterations evaluated where relevant |
| **Known Constraints** | [Technical constraints - e.g., size, ratio, performance requirements] |
| **Open Questions** | • [Question 1]<br>• [Question 2]<br>• [Question 3] |
| **Assumptions** | • [Assumption 1]<br>• [Assumption 2]<br>• [Assumption 3] |
| **Feature Confirmation** | Confirmed by user on [DATE]. Features F1-FN locked as defined; [Core features list] marked Core; all marked Desirable. |
```

---

### 3. Feature Plan (Confirmed)

Present the confirmed feature definitions:

```markdown
## 3. Feature Plan (Confirmed)

| Feature ID | Name | Description | Expected Variations | Core? (Y/N) | Desirable? | Notes |
|------------|------|-------------|---------------------|-------------|------------|-------|
| F1 | [Name] | [Full description] | • [Variation 1]<br>• [Variation 2]<br>• [Variation 3] | Y | Y | [The defining architectural element] |
| F2 | [Name] | [Full description] | • [Variation 1]<br>• [Variation 2]<br>• [Variation 3] | Y | Y | [Critical enabler note] |
| F3 | [Name] | [Full description] | • [Variation 1]<br>• [Variation 2]<br>• [Variation 3] | Y | Y | [Quantitative performance metric] |
| F4 | [Name] | [Full description] | • [Variation 1]<br>• [Variation 2]<br>• [Variation 3] | N | Y | [Why marked non-core] |
| F5 | [Name] | [Full description] | • [Variation 1]<br>• [Variation 2]<br>• [Variation 3] | Y | Y | [Application-critical constraint] |
```

---

### 4. Feature Matrix (Core Analytical Deliverable)

⚠️ **CRITICAL**: This is the **core analytical deliverable**. EVERY A-level and B-level reference MUST appear as a row with its publication number and feature coverage.

### ❌ ANTI-PATTERN: Query IDs in Feature Matrix

```
❌ WRONG — Query IDs are NOT valid row identifiers:
| Query | F1 | F2 | Comments |
| K1.1 | Y | N | ... |
| NQP-1.2 | N | Y1 | ... |
| S1.1 | Y1 | N | ... |

✅ CORRECT — Publication Numbers ARE valid row identifiers:
| Publication Number | Ref Type | F1 | F2 | Comments |
| US10234567B2 | Patent | Y | N | Claims 1, 5; Fig. 2 |
| WOS:000299510600010 | Research Paper | N | Y1 | Section 3.2, p.45 |
| JP2007171504A | Patent | Y1 | N | Abstract; Claims 1, 6-7 |
```

**Remember:**
- **K1.1, NQP-1.2, S1.1** = Query identifiers (which search found this)
- **US10234567B2, WOS:..., DOI:...** = Reference identifiers (what we found)

### Feature Matrix Validation Checklist

Before outputting Section 4, verify:
- [ ] First column is "Publication Number" (NOT Query ID)
- [ ] Every row represents ONE unique reference
- [ ] Patents have publication numbers (e.g., US10234567B2, JP2007171504A)
- [ ] NPL has WOS ID or DOI (e.g., WOS:000299510600010, 10.1021/...)
- [ ] Each F1..Fn column has Y/Y1/N value
- [ ] Pin-cites included in Comments for all Y/Y1 mappings

```markdown
## 4. Feature Matrix (Core Analytical Deliverable)

| Publication Number | Ref Type | Short Description | Relevance | Earliest Priority | Jurisdiction | F1 | F2 | F3 | F4 | F5 | Which Aspects Covered | Comments | X-category |
|-------------------|----------|-------------------|-----------|-------------------|--------------|----|----|----|----|----|-----------------------|----------|------------|
| JP2007171504A | Patent | Camera module with worm + two worm wheels | A | 2005-12-21 | JP | Y1 | N | N | N | Y | F5 (camera module); worm + "2nd worm wheel" + "1st worm wheel" | Has worm (8) driving 2nd worm wheel (7), which meshes with 1st worm wheel (65). Architecture ambiguous. No adapter gear. Pin-cites: Claims 1, 6-7; Abstract; Fig. 1. | N |
| CN106054342A | Patent | Two worm-wheel pairs on same lens | B | 2016-05-20 | CN | N | N | N | N | Y | F5 (camera focusing) | Two separate worm pairs on same lens, arranged in parallel. Not multiplicative cascade. Pin-cites: Claims 1-4; Abstract. | N |
| CN120312791A | Patent | Secondary worm planetary reducer | B | 2024-08-30 | CN | Y1 | N | Y | N | N | F1 (mentions "two-stage worm"), F3 (large reduction) | Planetary arrangement with 4 groups in parallel, not series cascade. High ratio via parallel engagement. Not miniature scale. Pin-cites: Claims 1, 3, 6-7. | N |
| JP2008134315A | Patent | Lens-barrel with branched power via worm gears | B | 2006-11-16 | JP | N | N | N | N | Y | F5 (lens barrel) | Two worm gears in parallel branches, not series. Pin-cites: Claims 1-2, 6-7; Abstract; Fig. 1. | N |
| JP2008281937A | Patent | Drive transmission with worm + deceleration gears | B | 2007-04-19 | JP | N | N | N | N | Y | F5 (lens drive) | Single worm + spur gear deceleration train. No dual-worm cascade. Pin-cites: Abstract; Claims. | N |
| US6707194B2 | Patent | Motor actuation device with worm gear for camera | B | 2000-08-04 | US | N | N | N | N | Y | F5 (lens barrel) | Single worm gear drives worm wheel to slide lens barrel. Pin-cites: Abstract; Figs. 1-2. | N |
| CN109333579A | Patent | Multistage self-locking mechanical arm joint | B | 2018-11-08 | CN | N | Y1 | Y | N | Y | F2 (worm + spur gears), F3 (multistage), F5 (compact) | Motor → planetary → worm → worm wheel → small gear → big gear. Worm + spur stages, NOT dual-worm. Pin-cites: Abstract; Claims. | N |
| WOS:000299510600010 | Research Paper | Compact Rotary Series Elastic Actuator | B | 2012 | IEEE/ASME Trans. | N | N | N | N | Y | Single worm for compact high-torque actuation | Confirms single worm gear as standard approach for compact actuators. No mention of dual-worm cascades. | N |
| WOS:000390073900031 | Research Paper | Active knee orthosis driven by rotary SEA | B | 2017 | Mechatronics | N | N | N | N | N | Single worm gear in knee actuator | DC motor + single worm gear + torsion spring. No multi-stage worm systems discussed. | N |
| WOS:000297096900018 | Research Paper | Bioinspired Tunable Lens with Electroactive Elastomers | B | 2011 | Advanced Functional Materials | N | N | N | N | N | Non-gear actuation | Represents dominant non-gear trend in miniature optical actuation. | N |
```

**Key Requirements:**
- **EVERY A-level and B-level reference = ONE ROW** with its Publication Number
- **Publication Number** links to detailed Patents/NPL Record View
- **F1..Fn columns**: Y (disclosed), Y1 (partial), N (absent)
- **X-category**: Mark with `X` if ALL core features are Y (anticipatory ref)
- **Pin-cites**: Include claim numbers, paragraphs, figures where applicable

### ⭐ Before filling Y / Y1 / N cells (MANDATORY)

The DWPI title, abstract, and first-claim paragraph returned by a
landscape or narrow Derwent search are NOT sufficient evidence to mark a
feature `N`. They omit the full claim set and detailed description, where
feature-limitation language is frequently buried.

**For EVERY A- or B-rated reference**, before assigning ANY Y / Y1 / N to
ANY feature in its Feature Matrix row, call:

```
get_patent_details(publication_number=<pub>)
```

This retrieves the full claims (`cl`) and DWPI detailed description
(`dtd`) that are intentionally excluded from landscape-search payloads.
Grade each feature against THAT returned content, not against the
summary that was in context at triage time.

**Rule**: mark `N` only when you have actively searched the full claims
+ detailed description for the feature's keywords and synonyms and found
them absent. Marking `N` from title/abstract alone is a hallucination —
the evidence for absence isn't in scope.

Marking `Y1` when the feature is partially disclosed (different
vocabulary, narrower scope, missing a sub-element) is always preferable
to `N` when doubt exists.

**Functional-equivalence rule**: anticipation is functional, not literal.
If the earlier reference performs the SAME FUNCTION the feature
describes — even with different vocabulary, shape, geometry, count, or
materials — grade `Y1`, NOT `N`. Examples:

- "rectangular float" vs "hexagonal frame / outer frame portion" → `Y1`
  (both serve as a closed float body; shape is incidental).
- "four pontoons in four openings" vs "plural floats on coupling posts
  arranged in a vertical row / vertical annular collars" → `Y1` (same
  function: distributed buoyancy in discrete units).
- "cross-shaped internal support" vs "central connecting rod /
  reinforcing rod at center" → `Y1` (same function: structural bracing).
- "triangular mounting" vs "inclined struts / A-frame / angled brackets"
  → `Y1` (same function: tilted panel support).
- "bifacial panel" vs "dual-surface PV / panel with light-active
  underside" → `Y1` (same function: two-sided light capture).

Reserve `N` for cases where the earlier reference genuinely has nothing
that performs the function — not where it uses different words or shapes
for the same function. See the `screening` skill's "Functional-equivalence
rule" for the canonical reference.

**Worked example** — `US11319035B2` ("Floating type solar power generation
equipment stage device"). Landscape search returns a short abstract +
first-claim snippet that says "outer frame portion with connecting rod
at the center". If you mark `F_pontoons = N` from that, you're wrong —
the FULL claims include "a plurality of floats... arranged in a row in a
vertical direction", which is exactly the pontoon-retention feature.
`get_patent_details` returns this text; the landscape search result does
not.

This mandate applies to A and B refs only. C refs and landscape filler
do NOT pay the fetch cost — they stay in Section 5 (Peripherally
Related) without cell-level grading.

---

### 5. Peripherally Related References

C-label references worth mentioning:

```markdown
## 5. Peripherally Related References

| Publication Number | Type | Title | 1-2 Line Rationale / Aspects Covered | Note |
|-------------------|------|-------|--------------------------------------|------|
| CN110646913B | Patent | Voice coil motor periscope lens actuating device | [Market technology] actuation using VCM (not relevant mechanism) | Confirms VCM dominance |
| CN110032024B | Patent | Optical actuator with shape memory alloy wires | SMA wire groups drive lens module; alternative actuation | Alternative miniature technology |
| CN112145916A | Patent | Tripod camera with worm-bevel gear tilt mechanism | Single worm + bevel gear for camera pan/tilt; no cascade | Single-stage application |
| US11543620B2 | Patent | Lens barrel with worm gear locking | Single worm for focus lens position holding; self-locking | Worm self-locking application |
| JP2003295274A | Patent | Worm-gear apparatus for camera with inclined motor axis | Single worm, motor axis inclined for space efficiency | Single-stage positioning |
| CN101767708A | Patent | Jacking mechanism for dual-worm bar conveying line | "Dual-worm" refers to two parallel worm bars for conveyor | Terminology collision; out of scope |
| CN201619864U | Patent | Dual-worm transmission line body | Two worms with opposite rotation for conveyor clamp movement | Parallel worms for material handling |
```

---

### 6. Patents Record View (Bibliographic Details)

Create a **per-patent table** for each A-level and key B-level patent:

```markdown
## 6. Patents Record View (Bibliographic Details)

### JP2007171504A

| Field | Details |
|-------|---------|
| **Publication Number** | JP2007171504A |
| **Publication Date** | 2007-07-05 |
| **Earliest Priority Date** | 2005-12-21 |
| **Applicant/Assignee** | [Name or "Not disclosed"] |
| **Jurisdiction/Office** | Japan Patent Office (JPO) |
| **Legal Status** | Unknown (grant status not retrieved) |
| **Source/Link** | [Espacenet](https://worldwide.espacenet.com/patent/search?q=pn%3DJP2007171504A) |
| **Abstract** | A camera module (1) for small electronic devices comprises: housing (2), lens unit (3), holder (4) movable along optical axis with coil spring (5) biasing, rotation ring (6) with cams (64) and 1st worm wheel (65) on outer periphery, 2nd worm wheel (7) positioned beside rotation ring meshing with 1st worm wheel, worm gear (8) meshing with 2nd worm wheel, stepping motor (9) driving worm gear, and image sensor (11). |
| **Claimed Novelty** | Worm gear driven by stepping motor meshes with 2nd worm wheel positioned beside rotation ring; 2nd worm wheel meshes with 1st worm wheel of rotation ring; holder biased by coil spring can move along optical axis. |
| **Intended Use** | Camera modules for small electronic devices (digital cameras, camera cell phones). |
| **Claims (Salient)** | Claim 1: Housing, lens unit, holder movable along optical axis, elastic member biasing holder downward, rotation ring with ≥3 cams and 1st worm wheel on outer periphery, 2nd worm wheel meshing with 1st worm wheel, worm gear meshing with 2nd worm wheel, stepping motor driving worm gear, image sensor. Claim 6: Worm gear contained in branch part to drive mechanism. |
| **IPC/CPC** | H04N (electric communication), G02B (optical elements) |
| **Feature Mapping** | F1=Y1 (worm + multiple worm wheels, but cascade architecture unclear), F2=N (no adapter gear disclosed), F3=N (no ratio quantification), F4=N (rotary only, no leadscrew), F5=Y (camera module miniaturization). |
| **Comments** | Closest prior art. Architecture suggests worm (8) → 2nd worm wheel (7) → 1st worm wheel (65), but unclear if this constitutes two separate worms in series. No "second worm" shaft explicitly described. No adapter gear between worm wheel outputs. Does not achieve F1 (dual-worm cascade) or F2 (adapter coupling). |

### CN106054342A

| Field | Details |
|-------|---------|
| **Publication Number** | CN106054342A |
| **Publication Date** | 2016-10-26 |
| **Earliest Priority Date** | 2016-05-20 |
| **Applicant/Assignee** | [Not disclosed] |
| **Jurisdiction/Office** | China National Intellectual Property Administration (CNIPA) |
| **Legal Status** | Unknown |
| **Source/Link** | [Espacenet](https://worldwide.espacenet.com/patent/search?q=pn%3DCN106054342A) |
| **Abstract** | External focusing device comprises: transmission mechanism (1) for adjusting lens axial relative distance; worm (2,3) with worm wheels (11,12) meshed with transmission mechanism; adjusting mechanism (4) controlling worm rotation. Two worm wheels combined on outer circumference of lens; two worms positioned along axes intersecting with lens axis. |
| **Claimed Novelty** | Two separate worm-wheel pairs on single lens for external focusing; worms positioned at intersecting axes relative to lens; enables precise positioning. |
| **Intended Use** | Self-locking camera external focusing device. |
| **Claims (Salient)** | Claim 1: Two worms (2,3) comprising worm wheels (11,12); transmission mechanism adjusting lens axial distance; worm wheels on outer circumference of lens; two worms' axes intersect with lens axis. Claim 2: Two worms parallel to each other. |
| **IPC/CPC** | G02B (optical elements), G03B (photographic apparatus) |
| **Feature Mapping** | F1=N (two worms present but in parallel, not series cascade), F2=N (no adapter gear), F3=N (no ratio multiplication discussed), F4=N (focusing only), F5=Y (camera application). |
| **Comments** | Two independent worm-wheel pairs on same lens for dual-axis external focusing adjustment. Parallel arrangement, not series cascade. No multiplicative ratio benefit. No adapter gear coupling between worm stages. |

[Continue for each A-level and key B-level patent...]
```

---

### 7. NPL Record View (Bibliographic Details)

Create a **per-paper table** for each research paper:

```markdown
## 7. NPL Record View (Bibliographic Details)

### WOS:000299510600010

| Field | Details |
|-------|---------|
| **DOI/Identifier** | WOS:000299510600010 |
| **Title** | A Compact Rotary Series Elastic Actuator for Human Assistive Systems |
| **Authors** | Kong, Kyoungchul; Bae, Joohyun; Tomizuka, Masayoshi |
| **Venue** | IEEE/ASME Transactions on Mechatronics |
| **Year** | 2012 |
| **Publisher** | IEEE |
| **Abstract** | Precise and large torque generation, back drivability, low output impedance, and compactness are important for human assistive robots. A compact rotary series elastic actuator (cRSEA) is designed using a worm gear to magnify torque in limited space. Actual torque amplification differs from nominal ratio due to friction. Friction model incorporated in control design. Robust control algorithm for precise torque output despite nonlinearities. |
| **Sections Cited** | Section on worm gear transmission for torque amplification in compact envelope; friction modeling for worm gear efficiency variations. |
| **Notes** | Confirms single worm gear as standard approach for compact high-torque actuation in robotics. No mention of dual-worm cascades or series arrangements. Discusses friction as key challenge in worm systems. |

### WOS:000390073900031

| Field | Details |
|-------|---------|
| **DOI/Identifier** | WOS:000390073900031 |
| **Title** | Design and control of an active knee orthosis driven by a rotary Series Elastic Actuator |
| **Authors** | Giovacchini, Francesco; Vannetti, Federico; Fantozzi, Michele; et al. |
| **Venue** | Mechatronics |
| **Year** | 2017 |
| **Publisher** | Elsevier |
| **Abstract** | Active knee orthosis driven by customized rotary SEA includes DC motor, worm gear, and customized torsion spring. Finite element analysis of spring for knee assistance requirements. Torque and impedance control for safe patient interaction. H-infinity controller for robust performance with parametric uncertainties. |
| **Sections Cited** | Section on actuator mechanical design using worm gear for high ratio in compact form; control strategies for managing worm gear friction. |
| **Notes** | Academic confirmation that single worm gear is standard for compact high-ratio actuation. No multi-stage worm systems in rehabilitation robotics literature. |

[Continue for each NPL reference...]
```

---

### 8. Transactional Search Summary (Client-Facing Cover Note)

```markdown
## 8. Transactional Search Summary (Client-Facing Cover Note)

### Search Approach

- **Scope:** [Detailed scope description - e.g., "Dual worm gear cascade transmission systems for smartphone camera lens actuation (10-13mm thickness constraint)"]
- **Databases/Tools:**
  - Patents: Innography (DWPI editorial coverage), patent semantic search, full-text retrieval
  - Research Papers: Web of Science (2010-2025)
- **Keywords:** [Main search terms - e.g., "Dual/two worm gears, cascade/series transmission, adapter/intermediate gear, camera/lens actuation, miniature/compact/smartphone, high transmission ratio"]
- **Time Period:** [Date range - e.g., "All dates (no filters applied); NPL focused on 2010-2025 for recency"]
- **Search Protocol:** 6-stage methodology — Scoping → Feature Definition → Patent Keyword (X passes, DWPI-first + native field coverage) → NPL Keyword (X passes) → Semantic Expansion (X passes) → Feature Mapping

### Key Findings

- **Total References Screened:** ~[N]+ patents, [M] research papers
- **Relevance Breakdown:**
  - A-level (highly relevant): [Count] patents ([Reference] — closest but lacks [N] of [M] core features)
  - B-level (potential): [Count] patents (partial feature coverage)
  - C-level (peripherally related/out): [Count]+ patents ([description])
  - Research papers: [Finding - e.g., "No dual-worm cascade literature found; single-worm standard in robotics/cameras"]
- **X-Category (All Features):** [Count] patents found
- **Novelty Assessment:** [Strong/Moderate/Weak] novelty — [Summary statement]
- **Closest Prior Art:** [Reference ID] ([brief description])

### Next Steps

- **Optional:** [Extended search recommendations]
- **Recommended:** [Immediate action recommendations]
- **Consider:** [Strategic options]
- **Monitor:** [Ongoing surveillance recommendations]
```

---

### 9. Landscape Overview (Concise)

```markdown
## 9. Landscape Overview (Concise)

### Classes/Themes

- **Dominant theme:** [Description - e.g., "Smartphone camera actuation overwhelmingly uses non-gear technologies (VCM 85%+, emerging SMA/piezoelectric)"]
- **[Technology] applications:** [Description - e.g., "Concentrated in automotive (window lifts, seat adjusters), industrial machinery, robotics — all single-stage only"]
- **Multi-stage transmissions:** [Finding - e.g., "Planetary + worm combinations exist in robotics/machinery, but no dual-worm cascades identified"]
- **Miniaturization trend:** [Finding - e.g., "Optical actuation research focuses on smart materials (elastomers, shape-memory alloys), not mechanical gears"]
- **Key classifications:**
  - [IPC/CPC 1] — [Description and finding]
  - [IPC/CPC 2] — [Description and finding]
  - [IPC/CPC 3] — [Description and finding]

### Notable Assignees/Authors

- **Patents:** [Description - e.g., "Primarily Asian manufacturers (JP/CN); major camera OEMs focus on VCM/SMA"]
- **[Industry] systems:** [Key players - e.g., "Brose, Bosch (single-stage window lifts)"]
- **Research:** [Key institutions - e.g., "Academic institutions (Seoul National University, University of Pisa) study single-worm SEA actuators for robotics"]
- **Gap:** [Finding - e.g., "No major players in dual-worm cascade or gear-based smartphone camera actuation"]

### Density Indicators

- **High density:** [Areas with many patents]
- **Moderate density:** [Areas with some activity]
- **Zero density:** [Identified gaps - e.g., "Dual-worm cascade systems across all application domains"]
- **Geographic concentration:** [Regional analysis - e.g., "CN/JP lead in camera actuation patents; DE/US in automotive worm systems"]
```

---

### 10. Search Traceability (Addendum)

```markdown
## 10. Search Traceability (Addendum)

### Results List (Full)

| Publication Number | Type | Title | Authors/Assignees | Earliest Priority | Publication Date | Jurisdiction | Classifications |
|-------------------|------|-------|-------------------|-------------------|------------------|--------------|------------------|
| JP2007171504A | Patent | Camera module | Unknown | 2005-12-21 | 2007-07-05 | JP | H04N, G02B |
| CN106054342A | Patent | Worm wheel and worm self-locking camera external focusing device | Unknown | 2016-05-20 | 2016-10-26 | CN | G02B, G03B |
| CN120312791A | Patent | Planetary speed reducer of two-stage worm wheel and worm | Unknown | 2024-08-30 | 2024-10-22 | CN | F16H |
| JP2008134315A | Patent | Lens-barrel | Unknown | 2006-11-16 | 2008-06-12 | JP | G02B, G03B |
| JP2008281937A | Patent | Drive transmission apparatus | Unknown | 2007-04-19 | 2008-11-20 | JP | G02B, G03B |
| US6707194B2 | Patent | Motor actuation device | Unknown | 2000-08-04 | 2004-03-16 | US | G02B, H02K |
| CN109333579A | Patent | Multistage transmission mechanism self-locking compact mechanical arm joint | Unknown | 2018-11-08 | 2019-02-22 | CN | F16H, B25J |
| WOS:000299510600010 | Research Paper | A Compact Rotary Series Elastic Actuator | Kong, Bae, Tomizuka | 2012 | 2012 | IEEE/ASME Trans. | Robotics, Actuators |
| WOS:000390073900031 | Research Paper | Design and control of an active knee orthosis | Giovacchini et al. | 2017 | 2017 | Mechatronics | Rehabilitation Robotics |
| WOS:000297096900018 | Research Paper | Bioinspired Tunable Lens with Electroactive Elastomers | Carpi et al. | 2011 | 2011 | Advanced Functional Materials | Smart Materials, Optics |

### Search Log (Detailed)

| Timestamp | Stage | Tool | History ID | Query ID | QP/NQP | Query | Source | Result Count | Kept (pub. numbers) | Notes | Status |
|-----------|-------|------|------------|----------|--------|-------|--------|--------------|---------------------|-------|--------|
| [DATE TIME] | 3A | patent_keyword | — | QP-1.1 | QP-1 | [query text] | Innography | [count] | [pub numbers kept] | [notes] | Complete |
| [DATE TIME] | 3A | patent_keyword | — | QP-1.2 | QP-1 | [query text] | Innography | [count] | [pub numbers kept] | [notes] | Complete |
| [DATE TIME] | 3A | patent_keyword | — | QP-2.1 | QP-2 | [query text] | Innography | [count] | [pub numbers kept] | [notes] | Complete |
| [DATE TIME] | 3B | NQP_search | — | NQP-1.1 | NQP-1 | [query text] | WoS | [count] | [WOS IDs] | [notes] | Complete |
| [DATE TIME] | 4 | patent_semantic | — | QP-4.1 | QP-4 | [semantic query] | Semantic | [count] | [pub numbers kept] | [notes] | Complete |

**Total:** [N] tool calls ([X] patent keyword, [Y] patent semantic, [Z] NPL)

### Query Patterns Used

**Patent Keyword (Innography-Compatible):**
- Seed queries (QP-1): Core feature combinations ([description])
- Context queries (QP-2): Adapter/intermediate + application domains
- Broad queries (QP-3): High ratio + compact + miniature (with escalation to All Text scope)
- Class-filtered (QP-2 variant): IPC/CPC constraints on [classes]

**Patent Semantic:**
- Full invention descriptions with architectural emphasis
- Concept-level matching for [key concepts]

**NPL (Web of Science):**
- Boolean + proximity: TS=(([term1] NEAR/3 [term2]) AND ([term3] OR [term4]))
- Application-focused: TS=(([application] NEAR/5 [mechanism]) AND ([size constraint]))

**Data Sources/Tools:**
- Innography (DWPI editorial coverage): Patent keyword + DWPI-first methodology
- Semantic search engine: Concept-level patent matching
- Web of Science: Research paper retrieval ([date range])
- Full-text patent retrieval: Detailed claim analysis
```

---

### 11. Next Steps

```markdown
## 11. Next Steps

### Immediate Recommendations

#### 1. [PRIMARY ACTION] (High Priority)

- **Timeline:** [Timeframe - e.g., "Within 30 days"]
- **Rationale:** [Justification - e.g., "Strong novelty across all core features (F1-F5); no X-category blocking patents identified"]
- **Claims Strategy:**
  - Independent Claim 1: [Claim focus - e.g., "F1 + F2 for core architecture"]
  - Dependent Claims: [Additional features]
  - Consider: [Divisional/continuation strategy]

#### 2. [OPTIONAL EXTENDED SEARCH] (Medium Priority)

- **[Language/Geographic extension]:** [Description and estimated effort]
- **Expected yield:** [Assessment]
- **Recommend only if:** [Condition]

#### 3. [MONITORING] (Ongoing)

- **Watch:** [Classifications/areas to monitor]
- **Focus:** [Emerging technologies/solutions]
- **Frequency:** [Update cadence]

#### 4. [PROTOTYPE VALIDATION] (Engineering Track)

- **Validate:** [Technical claims to verify]
- **Document:** [Data to collect]
- **Use:** [How data supports prosecution/commercialization]

#### 5. [MARKET ANALYSIS] (Business Track)

- **Assess:** [Cost/market comparisons]
- **Target:** [Customer segments]
- **Challenges:** [Market barriers]

### Search Quality & Limitations

**Search Quality Assessment:**
- Coverage: [Assessment - e.g., "Comprehensive (100+ patents screened, 2 NPL databases, 20 tool calls)"]
- Methodology: [Description - e.g., "Systematic 6-stage approach with DWPI-first + native field coverage"]
- Feature Mapping: [Description - e.g., "Rigorous analysis of N most relevant patents against all M core features"]
- Confidence Level: [High/Medium/Low] ([justification])

**Known Limitations:**
- Language bias: [Description]
- Unpublished applications: [Description]
- Trade secrets: [Description]

**QA Checklist (Completed):**
- ✅ Coverage of all core features (F1-FN)
- ✅ Consistency of triage/matrix labels (A/B/C + Y/Y1/N)
- ✅ Family de-duplication (earliest priority members retained)
- ✅ Pin-cites present for all Y/Y1 feature mappings
- ✅ Earliest priority & publication dates captured
- ✅ Legal status noted where available
- ✅ Tables render correctly in Markdown
- ✅ Links policy complied with (links reserved for Patents Record View)
```

---

## Evaluation-Required Appendix (MANDATORY — scorers key off these exact H2 headers)

⚠️ **CRITICAL**: After sections 1-11 above, ALWAYS append the following four H2 sections. The automated evaluation scorers read these exact section names from `final_report.md`. Do not rename them, do not merge them into existing sections.

These are short synthesis sections (not re-statements of the full report) — just the distilled assessment the scorer needs.

```markdown
## Novelty Assessment

Feature-by-feature synthesis of whether each feature is anticipated, partially anticipated, or novel.

| Feature | Verdict | Anticipating References |
|---------|---------|-------------------------|
| F1: [Name] | anticipated / partial / novel | [ref1], [ref2] |
| F2: [Name] | ... | ... |
| ... | ... | ... |

End this section with a line in this EXACT format (one of the three literal tokens — the scorer matches on it):

**Verdict: not_novel**

(or `**Verdict: novel**` or `**Verdict: partially_novel**` — no other phrasing allowed)

### Verdict decision rule (MANDATORY — do not default to `partially_novel` as a safe middle)

Map from the per-feature grades (`anticipated` / `partial` / `novel`) and
the feature-matrix columns (Y = full match, Y1 = partial match, N = not
disclosed) as follows:

- **`not_novel`** — ALL of the following hold:
  - Every CORE feature has at least one independent earlier reference
    with `Y` or `Y1` coverage (partial match counts — the SME's novelty
    standard is "disclosed in the art," not "disclosed verbatim").
  - At least one earlier reference covers ≥50% of the core features
    (even at `Y1` level), OR two+ references together cover all core
    features.
  - No core feature is graded `novel` in the per-feature table.

- **`partially_novel`** — EXACTLY ONE of:
  - One or more core features are genuinely `novel` (no earlier ref
    discloses them, not even at `Y1`), while others are clearly
    anticipated.
  - Earlier refs together cover the feature set but the SPECIFIC
    CLAIMED COMBINATION (e.g. "the exact arrangement of A+B+C in one
    device") is not shown in any single earlier ref AND no reasonable
    combination reads on it.

- **`novel`** — no core feature has any earlier `Y`/`Y1` coverage from
  independent (non-self-citation) prior art.

**Do not pick `partially_novel` just because one feature was weakly
matched.** Weak ≠ novel. If F2 is only covered at `Y1` by one ref but
all other features are anticipated, the verdict is still `not_novel` —
the feature was disclosed, just not in exact terms.

Worked example (C19904): the agent found US11319035B2 with F1=Y1, F2=Y1
and other refs covering F3/F4/F5. No feature is genuinely `novel`. Even
though F2's match is only partial (Y1), the correct verdict is
`not_novel` — not `partially_novel` — because every core feature has
some independent earlier disclosure.

---

## Risk Assessment

Aggregate novelty risk (Low / Medium / High) and the top 3 references driving it. Two or three sentences.

- **Overall novelty risk:** [Low/Medium/High]
- **Top anticipating refs:** [ref1], [ref2], [ref3]
- **Rationale:** [One-sentence justification]

---

## Limitations

Bulleted list of explicit limitations:

- Databases not queried: [list]
- Date ranges not covered: [list]
- Languages not searched: [list]
- Known gaps in feature coverage: [list]
- Other caveats: [list]

---

## Verdict

Single-line restatement of the verdict from Novelty Assessment, in the same exact format:

**Verdict: not_novel**

Followed by one paragraph of rationale citing the top 1-3 anticipating references.
```

---

**End of Report**

Report compiled: [DATE]
Total pages (if printed): ~[N]-[M]
Recommendation: [Final recommendation summary]

---

## Quality Checklist

Before finalizing, verify:

- [ ] Section 1 includes Types of Solutions, Gap Analysis Table, Risk Assessment
- [ ] Section 2 uses table format with all scope elements
- [ ] Section 3 includes Feature Plan with Variations, Core?, Desirable?, Notes
- [ ] Section 4 (Feature Matrix) includes ALL A/B references with publication numbers and F1..Fn coverage
- [ ] Section 5 lists peripherally related C-refs
- [ ] Section 6 has per-patent tables with full bibliographic details
- [ ] Section 7 has per-paper tables with full bibliographic details
- [ ] Section 8 has client-facing Transactional Search Summary
- [ ] Section 9 has Landscape Overview with Classes, Assignees, Density
- [ ] Section 10 has Results List + Search Log with Query ID/QP/NQP columns
- [ ] Section 11 has prioritized Next Steps with Search Quality Assessment
- [ ] All A-refs have hyperlinks (Espacenet, Google Patents, DOI) in Record View
- [ ] Feature mapping complete for all A and B refs
- [ ] No lengthy debug/troubleshooting text — clean report only
- [ ] **Evaluation Appendix present**: `## Novelty Assessment`, `## Risk Assessment`, `## Limitations`, `## Verdict` as H2 headers after section 11
- [ ] **Verdict line in exact format**: `**Verdict: novel**` / `**Verdict: partially_novel**` / `**Verdict: not_novel**` appears in both Novelty Assessment and Verdict sections
- [ ] **ALL TODOS MARKED COMPLETED** — Call `write_todos` with all tasks set to `"status": "completed"` BEFORE delivering the final report to the user
