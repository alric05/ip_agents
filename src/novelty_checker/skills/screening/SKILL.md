---
name: screening
description: Triage labels, feature mapping, coverage analysis, and citation consolidation
triggers:
  - screen
  - triage
  - coverage
  - A/B/C
  - Y/Y1/N
  - consolidate
  - cite
---

# Screening Skill

This skill guides you through Stage 4: Screening, Triaging, and Coverage Analysis.

## Role in the Research Workflow

Screening happens **AFTER** the Iterative Research Loop exits. By this point:
- Multiple research rounds have been completed
- References have been collected from patent/NPL/semantic searches
- Coverage targets have been met (or max iterations reached)

Your job now is to:
1. **Consolidate** all references with unified citation numbers
2. **Triage** each reference (A/B/C labels)
3. **Map** each reference against all features (Y/Y1/N)
4. **Analyze** final coverage and identify any remaining gaps
5. **Prepare** data for report generation

---

## ⚙️ Citation Consolidation (First Step!)

Before triaging, consolidate all references from the research loop:

### Deduplication Process

```markdown
### Citation Consolidation

**Input:** All references from Rounds 1-N

**Step 1: Group by Publication Number**
- Same patent number → Single entry
- Same DOI/WOS ID → Single entry
- Note all rounds where reference was found

**Step 2: Merge Feature Mappings**
- Combine feature coverage from all rounds
- Keep highest confidence level (Y > Y1 > N)

**Step 3: Calculate Diversity Score**
| Factor | Bonus |
|--------|-------|
| Base | 1.0 |
| Per additional round found | +0.3 |
| Per additional source (Innography, WoS, NGSP) | +0.5 |
| Found via semantic search | +0.2 |

**Step 4: Assign Sequential Citation Numbers**
- Sort by: Relevance (A first) → Diversity Score → Priority Date
- Assign [1], [2], [3], etc.
```

### Consolidated Reference Table

```markdown
## Consolidated References

| Cite # | Publication Number | Type | Sources | Rounds | Diversity Score | Initial Relevance |
|--------|-------------------|------|---------|--------|-----------------|-------------------|
| [1] | US10234567B2 | Patent | Innography, NGSP | R1, R2 | 2.5 | A |
| [2] | JP2007171504A | Patent | Innography | R1 | 1.0 | A |
| [3] | WOS:000299510600010 | NPL | WoS, NGSP | R1, R3 | 2.2 | B |
| [4] | CN106054342A | Patent | Innography | R2 | 1.3 | B |
| [5] | EP3456789A1 | Patent | Innography | R1 | 1.0 | B |
```

---

## Triage Labels

After consolidation, confirm/refine the relevance label for each reference:

### A - High Relevance ⭐⭐⭐

**Criteria**:
- Directly impacts novelty assessment
- Describes substantially the same invention/technique
- Would be cited in a patent examiner's rejection
- Discloses **core features**

**Action**: Deep analysis required, full feature mapping with pin-cites

### B - Medium Relevance ⭐⭐

**Criteria**:
- Related technology but partial overlap
- Different application of similar principles
- Discloses **some features** but not the core combination

**Action**: Feature mapping, may inform claim drafting

### C - Low Relevance ⭐

**Criteria**:
- Background/peripheral information only
- Same general field but different approach
- Doesn't impact novelty assessment

**Action**: Record in "Peripherally Related References" section, minimal analysis

---

## Feature Mapping with think_tool

Use think_tool for systematic feature mapping:

```markdown
### Feature Mapping Analysis

**Reference: [1] US10234567B2 - UV-fluorescence polymer detection**

| Feature | Mapping | Evidence | Pin-Cite |
|---------|---------|----------|----------|
| F1 (PA6 Degradation) | Y | "polyamide-6 thermal degradation" | Claim 1, ¶[0023] |
| F2 (UV 300-350nm) | Y1 | "UV source" mentioned but range unspecified | ¶[0015] |
| F3 (Emission 350-400nm) | Y | "fluorescence emission at 380nm" | Claim 3, ¶[0031] |
| F4 (Inline Monitoring) | N | Lab apparatus only | — |
| F5 (Threshold) | N | No decision logic | — |

**Summary:** Covers 2Y + 1Y1 + 2N. Strong F1/F3 coverage, partial F2, no F4/F5.
**Relevance Confirmed:** A (impacts novelty for F1, F3)
```

### Mapping Decision Tree

```
Is the feature explicitly described?
├── YES → Y (Disclosed)
│         └── Add pin-cite: claim/paragraph/figure
└── NO
    ├── Is it implied or partially disclosed?
    │   ├── YES → Y1 (Partial)
    │   │         └── Add pin-cite with caveat
    │   └── NO → N (Absent)
    └── Would a skilled person recognize it as enabled?
        ├── YES → Y1 (Partial)
        └── NO → N (Absent)
```

### ⭐ Functional-equivalence rule (MANDATORY when comparing against full text)

After `get_patent_details(pub)` returns the full claims and DWPI detailed
description, grade against the **same function** the feature describes —
NOT against exact vocabulary or geometry. Novelty anticipation in patent
law is functional, not literal.

If the earlier reference discloses a structure or mechanism that performs
the SAME FUNCTION the feature describes — even with different vocabulary,
geometry, shape, orientation, count, or materials — you MUST grade `Y1`
(partial), not `N`.

Common functional-equivalence collisions where `N` is wrong:

| Disclosure feature | Earlier ref language | Correct grade | Why |
|---|---|---|---|
| "rectangular float" | "hexagonal frame / outer frame portion" | **Y1** | Both serve as a closed float body; shape is incidental |
| "four pontoons in four openings" | "plural floats on coupling posts / vertical annular collars" | **Y1** | Same function: distributed buoyancy in discrete units |
| "cross-shaped internal support" | "central connecting rod / reinforcing rod at center" | **Y1** | Same function: structural bracing across the float body |
| "bifacial panel" | "dual-surface PV / panel with light-active underside" | **Y1** | Same function: two-sided light capture |
| "triangular mounting" | "inclined struts / A-frame / angled brackets" | **Y1** | Same function: tilted panel support |

**Rule**: reserve `N` for cases where the earlier reference genuinely has
nothing that performs the function — not where it performs the function
with different words or shapes. When in doubt between `Y1` and `N`,
choose `Y1`. Under-rating feature coverage leads to false novelty
conclusions.

---

## ⚠️ CRITICAL: Feature Matrix Output Format

The Feature Matrix must use **consolidated citation numbers** AND **publication numbers**:

### ❌ ANTI-PATTERN: Query IDs as Row Identifiers

```
❌ WRONG — Query IDs are NOT valid row identifiers:
| Query | F1 | F2 | Comments |
| K1.1 | Y | N | ... |
| NQP-1.2 | N | Y1 | ... |
```

### ✅ CORRECT: Consolidated Citations with Publication Numbers

```
✅ CORRECT — Citation numbers + Publication Numbers:
| Cite # | Publication Number | Ref Type | F1 | F2 | F3 | F4 | F5 | Comments |
| [1] | US10234567B2 | Patent | Y | Y1 | Y | N | N | Claims 1, 3; ¶[0023] |
| [2] | JP2007171504A | Patent | Y1 | N | N | N | Y | Abstract; Fig. 1 |
| [3] | WOS:000299510600010 | Research Paper | N | Y | Y1 | N | N | Section 3.2 |
```

### Full Feature Matrix Template

| Cite # | Publication Number | Ref Type | Short Description | Relevance | Priority Date | Jurisdiction | F1 | F2 | F3 | F4 | F5 | Which Aspects Covered | Comments | X-category |
|--------|-------------------|----------|-------------------|-----------|---------------|--------------|----|----|----|----|----|-----------------------|----------|------------|

### Key Rules
- **Include ALL A-level and B-level references** as rows in this table
- Each patent/paper MUST have Y/Y1/N for EVERY feature column
- The Publication Number links to detailed analysis in Patents/NPL Record View sections

### Feature Matrix Example (All A/B References with Feature Coverage)

| Publication Number | Ref Type | Short Description | Relevance | Priority Date | Jurisdiction | F1 | F2 | F3 | F4 | F5 | F6 | Which Aspects Covered | Comments | X-category |
|-------------------|----------|-------------------|-----------|---------------|--------------|----|----|----|----|----|----|----------------------|----------|------------|
| JP2007171504A | Patent | Camera module with worm + two worm wheels | A | 2005-12-21 | JP | Y1 | N | N | N | Y | — | F5 (camera module); worm + worm wheels | Architecture ambiguous; no adapter gear | |
| CN106054342A | Patent | Two worm-wheel pairs on same lens | B | 2016-05-20 | CN | N | N | N | N | Y | — | F5 (camera focusing) | Parallel arrangement, not cascade | |
| CN120312791A | Patent | Secondary worm planetary reducer | B | 2024-08-30 | CN | Y1 | N | Y | N | N | — | F1 (two-stage worm), F3 (large ratio) | Planetary array, not series cascade | |
| US10234567B2 | Patent | UV-fluorescence polymer detection | A | 2018-03-15 | US | Y | Y1 | Y | N | N | N | UV detection, fluorescence emission | Broad polymer, not PA6-specific | |
| EP3456789A1 | Patent | Inline quality monitoring system | B | 2019-07-20 | EP | Y1 | N | N | Y | Y | N | Inline monitoring, thresholding | Different sensing modality | |
| CN109333579A | Patent | Multistage self-locking arm joint | B | 2018-11-08 | CN | N | Y1 | Y | N | Y | — | F2 (worm + spur gears), F3 (multistage) | Worm + spur, not dual-worm cascade | |
| 10.1021/acs.analchem.2c01234 | Research Paper | Fluorescence-based PA6 analysis | A | 2022 | Anal. Chem. | Y | Y | Y | N | N | Y | PA6 fluorescence, UV excitation | Lab-based, not inline | |
| WOS:000299510600010 | Research Paper | Compact Rotary Series Elastic Actuator | B | 2012 | IEEE/ASME Trans. | N | N | N | N | Y | — | Single worm gear compact actuation | Confirms single-worm is standard | |

**Note:** Every A/B reference from search results appears as a row with complete feature mapping (Y/Y1/N for all F1..Fn)

---

## Peripherally Related References Table

For C-label references worth mentioning:

| Publication Number | Type | Title | 1–2 Line Rationale / Aspects Covered | Note |
|-------------------|------|-------|--------------------------------------|------|

---

## Coverage Matrix (CRITICAL - Maintain This!)

Create and maintain a coverage matrix like this:

| Feature | Core? | Patent A-Refs | Patent B-Refs | NPL Refs | Status | Action Needed |
|---------|-------|---------------|---------------|----------|--------|---------------|
| F1 | ✓ | 0 | 0 | 0 | ❌ GAP | K1 + S1 |
| F2 | ✓ | 1 | 2 | 1 | ✅ OK | — |
| F3 | | 0 | 1 | 0 | ⚠️ WEAK | K2 + NQP-2 |

### Status Levels

| Level | Icon | Criteria | Goal Met? |
|-------|------|----------|-----------|
| **NONE** | ❌ GAP | No relevant refs | ❌ HIGH PRIORITY |
| **WEAK** | ⚠️ | 1 B-ref only | ❌ NEEDS MORE SEARCH |
| **MODERATE** | 🟡 | 2+ B-refs OR 1 A-ref | ⚠️ OK for non-core |
| **STRONG** | ✅ OK | 1+ A-ref AND 2+ B-refs | ✅ TARGET for core |
| **SATURATED** | ✅✅ | 2+ A-refs AND 3+ B-refs | ✅✅ STOP SEARCHING |

---

## Coverage Targets (MINIMUM)

| Feature Type | Required Coverage |
|--------------|-------------------|
| **Core features** (is_core=Y) | STRONG (1+ A-ref AND 2+ B-refs) |
| **Non-core features** (is_core=N) | MODERATE (2+ B-refs OR 1 A-ref) |
| **Overall score** | ≥70% before declaring search complete |

### Coverage Calculation

```
For each feature:
  1. Count A-refs with Y or Y1 for that feature
  2. Count B-refs with Y or Y1 for that feature
  3. Determine coverage level

Overall = (Features at STRONG or better) / (Total features)
```

---

## Stage 5 Output Structure

Your output MUST include:

1. **Status Banner**:
   ```
   **Status:** Stage 5 of 6 — Screening, Triage & Feature Matrix Analysis
   ```

2. **Feature Matrix** table (as shown above with all columns)

3. **Peripherally Related References** table

4. **Coverage Summary**:
   ```markdown
   ## Coverage Summary

   | Feature | A-refs | B-refs | Level | Target Met? |
   |---------|--------|--------|-------|-------------|
   | F1 (CORE) | 2 | 3 | SATURATED | ✅✅ |
   | F2 (CORE) | 1 | 2 | STRONG | ✅ |
   | F3 (SUPPORT) | 0 | 1 | WEAK | ❌ |

   **Overall**: 2/3 = 67% at STRONG or better
   **Core Coverage**: 2/2 = 100% at STRONG or better ✅
   ```

---

## Adaptive Planning Rules

### RULE 1: Prioritize by Coverage Gap

- Features with ❌ GAP status get **highest priority**
- Core features **always outrank** non-core features
- **Never move to next stage** if core features have ❌ or ⚠️ status

### RULE 2: Strategy Rotation

| If This Fails... | Try This Next... |
|------------------|------------------|
| K1 (DWPI-first) | K2 (pairs/combos) |
| K2 (pairs) | K3 (broad sweep with quota) |
| All patent searches | Intensify NQP and semantic |

Track which strategies have been tried per feature!

### RULE 3: Diminishing Returns

| Condition | Action |
|-----------|--------|
| 3+ query variations yield <2 new refs | Expand synonyms |
| 5+ variations still fail | Mark as "HARD_TO_FIND" and move on |
| Never run more than 10 queries for a single feature | |

---

## Completion Criteria Checklist

Before declaring Stage 5 complete:

- [ ] All core features have STRONG coverage (1+ A-ref, 2+ B-refs)
- [ ] Overall coverage score ≥ 70%
- [ ] At least 2 search cycles completed
- [ ] No feature has GAP status (unless marked HARD_TO_FIND)
- [ ] Feature Matrix table is complete with all patent-to-feature mappings

---

## Common Pitfalls

❌ **Over-triaging as A**: Not everything is high relevance
❌ **Missing Y1**: Partial disclosure still matters
❌ **Ignoring B-refs**: They contribute to coverage
❌ **Single-pass screening**: May need multiple review cycles
❌ **Linear execution**: Use adaptive loop, not checklist!
❌ **Stopping too early**: Must meet coverage targets
❌ **Missing feature columns**: All F1..Fn columns are REQUIRED in the matrix
❌ **Forgetting todo update**: After completing screening, call `write_todos` to mark screening as `"status": "completed"` and report generation as `"status": "in_progress"`
