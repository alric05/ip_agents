---
name: parallel-search
description: Execute iterative research loop with parallel SubAgent delegation for comprehensive coverage
triggers:
  - feature confirmation
  - parallel search
  - search strategy
  - after gate 2
  - research loop
---

# Parallel Search Skill

Execute the **Iterative Research Loop** after feature confirmation to achieve comprehensive coverage.

## When to Use

Immediately after **Gate 2 (Feature Confirmation)** — this replaces the old sequential Stage 3A/3B/4 workflow.

---

## ⭐ Iterative Research Loop (Core Pattern)

This is NOT a single-pass process. Execute multiple rounds until coverage targets are met:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    RESEARCH LOOP (Max 5 rounds)                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ 1. PLAN: Prepare feature context with current gaps               │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                              ↓                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ 2. DELEGATE: Send parallel tasks to 3 search sub-agents         │  │
│  │    • patent-researcher (Innography)                              │  │
│  │    • npl-researcher (Web of Science)                             │  │
│  │    • semantic-researcher (NGSP)                                  │  │
│  │    Make ALL task() calls in ONE response!                        │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                              ↓                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ 3. RECEIVE: Collect findings from all sub-agents                 │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                              ↓                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ 4. REFLECT: Use think_tool to analyze coverage (MANDATORY!)      │  │
│  │    • Per-feature coverage levels                                 │  │
│  │    • Gaps remaining                                              │  │
│  │    • Decision: continue or stop                                  │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                              ↓                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ 5. DECIDE:                                                       │  │
│  │    Coverage met (70%+ STRONG, core at STRONG)? → EXIT LOOP       │  │
│  │    Gaps remain AND iteration < 5? → CONTINUE to step 1           │  │
│  │    Max iterations reached? → EXIT with available coverage        │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Round 1: Comprehensive Initial Search

### Step 1: Prepare Full Feature Context

```markdown
feature_context = """
## Invention
[Brief invention description]

## Features to Search

| ID | Name | Core? | Keywords | Description |
|----|------|-------|----------|-------------|
| F1 | PA6 Granule Degradation | Y | PA6, polyamide-6, nylon-6, degradation | Detect thermo-oxidative degradation |
| F2 | UV Excitation (300-350nm) | Y | UV excitation, 300-350nm, LED | UV light source in specific range |
| F3 | Fluorescence Emission | Y | emission, 350-400nm, photodiode | Measure fluorescence as indicator |
| F4 | Inline Monitoring | Y | inline, real-time, conveyor | Integrated with production line |
| F5 | Intensity Threshold | N | threshold, calibration | Go/no-go decision logic |

## Current Coverage Status
Round 1 — all features start at NONE.

## Search Focus
Comprehensive initial coverage of all core features (F1-F4).
"""
```

### Step 2: Delegate to All 3 Search Types in Parallel

```python
# Make ALL task() calls in ONE response for parallel execution!

task(
    description=f"Execute patent keyword searches.\n\n{feature_context}",
    subagent_type="patent-researcher"
)
task(
    description=f"Execute NPL academic literature searches.\n\n{feature_context}",
    subagent_type="npl-researcher"
)
task(
    description=f"Execute semantic searches for conceptual matches.\n\n{feature_context}",
    subagent_type="semantic-researcher"
)
```

### Step 3: Receive & Aggregate Results

Each sub-agent returns structured findings:
- References found (publication numbers, titles, relevance)
- Per-feature coverage achieved
- Gap recommendations

### Step 4: Reflect with think_tool (MANDATORY!)

```markdown
### Coverage Analysis (Round 1 of 5)

**New References Found:**
- Patents: 5 (A: 1, B: 4)
- NPL: 3 (all B-level)
- Semantic: 2 (1 overlap with patents)

**Coverage Status:**
| Feature | Core? | A-Refs | B-Refs | Level | Target | Gap? |
|---------|-------|--------|--------|-------|--------|------|
| F1 | Y | 1 | 2 | STRONG ✅ | STRONG | NO |
| F2 | Y | 0 | 1 | WEAK ❌ | STRONG | YES |
| F3 | Y | 0 | 0 | NONE ❌ | STRONG | YES |
| F4 | Y | 0 | 2 | MODERATE ⚠️ | STRONG | YES |
| F5 | N | 0 | 1 | WEAK | MODERATE | YES |

**Summary:**
- Core at STRONG: 1/4 (25%) ← Target: 100%
- Overall at STRONG: 1/5 (20%) ← Target: 70%

**Decision:** CONTINUE — F2, F3, F4 need more coverage
```

### Step 5: Decide

- **CONTINUE**: Gaps remain, proceed to Round 2 with targeted searches
- **STOP**: Coverage targets met, proceed to screening/report

---

## Round 2+: Targeted Gap-Filling

### Prepare Gap-Specific Context

```markdown
gap_context = """
## Gap Analysis from Previous Round

| Feature | Level | Target | Gap? | Strategy |
|---------|-------|--------|------|----------|
| F1 | STRONG ✅ | STRONG | NO | Skip |
| F2 | WEAK ❌ | STRONG | YES | Need 1 A-ref + 1 B-ref |
| F3 | NONE ❌ | STRONG | YES | Priority! Any refs |
| F4 | MODERATE ⚠️ | STRONG | YES | Need 1 A-ref |

## Gap-Filling Strategies

**F2 (UV Excitation):**
- Wavelength variations: 280-320nm, 320-380nm, UVA, UVB
- Source variations: laser, excitation source, light source
- Suggested: CTB=(UV NEAR3 (LED OR laser) NEAR5 polymer);

**F3 (Fluorescence Emission):**
- Wavelength variations: 360-390nm, 380-420nm
- Detection variations: photomultiplier, spectrometer
- Suggested: TS=(fluorescence emission polymer degradation)
"""
```

### Delegate Targeted Searches

```python
task(
    description=f"Patent gap-filling for F2 and F3.\n\n{gap_context}",
    subagent_type="patent-researcher"
)
task(
    description=f"NPL gap-filling for F2 and F3.\n\n{gap_context}",
    subagent_type="npl-researcher"
)
task(
    description=f"Semantic gap-filling with alternate vocabulary.\n\n{gap_context}",
    subagent_type="semantic-researcher"
)
```

---

## Citation Consolidation (After All Rounds)

Before proceeding to screening, consolidate all citations from all rounds:

### Deduplication Rules

1. **Same publication number** → Keep single entry, merge feature mappings
2. **Same DOI/WOS ID** → Keep single entry
3. **Different sources, same ref** → Note which searches found it (diversity score)

### Unified Citation Format

```markdown
## Consolidated References

| # | Publication Number | Type | Source | Rounds Found | Features | Relevance |
|---|-------------------|------|--------|--------------|----------|-----------|
| 1 | US10234567B2 | Patent | Innography | R1, R2 | F1, F2, F3 | A |
| 2 | WOS:000299510600010 | NPL | WoS | R1 | F2, F5 | B |
| 3 | EP3456789A1 | Patent | Innography, NGSP | R1 | F4 | B |
```

### Diversity Scoring

| Factor | Bonus | Rationale |
|--------|-------|-----------|
| Base | 1.0 | Every reference |
| Multi-round | +0.3/round | Persistent relevance |
| Multi-source | +0.5/source | Cross-validated |
| Semantic path | +0.2 | Vocabulary diversity |

---

## ⭐ Adaptive Stopping Logic (CRITICAL!) ⭐

Don't blindly run 5 rounds — use SMART stopping based on real-time signals!

### Stopping Conditions Summary

| Condition | Signal | Action |
|-----------|--------|--------|
| ✅ **Coverage Met** | Core at STRONG + overall ≥70% STRONG | STOP → Screening |
| ⚠️ **Max Iterations** | Round 5 reached | STOP → Proceed with available |
| ⚠️ **Diminishing Returns** | <2 net new refs for 2 rounds | STOP → Proceed with available |
| ⚠️ **Feature Saturation** | All features SATURATED | STOP → Excellent coverage! |

### Diminishing Returns Detection Template

Include this in your think_tool reflection after each round:

```markdown
### Diminishing Returns Check (Round X)

**This Round:**
- New refs: X
- Duplicates skipped: Y
- Net new: Z

**Trend:**
| Round | New | Dupes | Net New | Trend |
|-------|-----|-------|---------|-------|
| 1 | 15 | 0 | 15 | — |
| 2 | 10 | 4 | 6 | ↓ Declining |
| 3 | 5 | 4 | 1 | ↓↓ WARNING |

**Status:** [HEALTHY (3+) / WARNING (1-2) / TRIGGERED (<2 for 2 rounds)]
```

### Feature Saturation Tracking Template

```markdown
### Saturation Status

| Feature | Level | A | B | Saturated? | Future Action |
|---------|-------|---|---|------------|---------------|
| F1 | SATURATED | 3 | 5 | ✅ | SKIP |
| F2 | STRONG | 1 | 3 | ⚠️ Near | 1 round max |
| F3 | MODERATE | 1 | 1 | ❌ | Target |
| F4 | WEAK | 0 | 1 | ❌ | Priority |

**Saturated (SKIP):** [F1]
**Priority targets:** [F4, F3]
```

### Smart Stop Decision Template

```markdown
### STOP/CONTINUE Decision (Round X of 5)

**Coverage:**
- Core at STRONG: X/Y
- Overall at STRONG: X/Y (Z%)

**Efficiency:**
- Net new refs: X [HEALTHY/WARNING/TRIGGERED]
- Duplicate rate: Y%
- Untried query angles: [YES/NO]

**DECISION:** [CONTINUE / STOP]
**Reason:** [brief explanation]
```

### Early Stop Triggers

| Trigger | Condition | Why Stop |
|---------|-----------|----------|
| **Perfect Coverage** | All STRONG in Round 2 | Target exceeded |
| **Rapid Saturation** | 3+ features SATURATED | No more value |
| **Query Dead-End** | Same results from varied queries | Exhausted |

---

## Critical Reminders

1. **Context Isolation**: Sub-agents have NO memory — include ALL feature info in every task
2. **Parallel Execution**: Make ALL task() calls in ONE response
3. **Mandatory Reflection**: ALWAYS call think_tool after receiving results
4. **Track Rounds**: Note which round each reference was found in
5. **Track Diminishing Returns**: Check net new refs each round
6. **Track Saturation**: Skip searching for SATURATED features
7. **Consolidate Before Screening**: Deduplicate and assign unified citation numbers
8. **Todo Update**: After completing research loop, call `write_todos` to mark search tasks as `"status": "completed"`
