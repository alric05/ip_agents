---
name: feature-definition
description: How to decompose inventions into searchable features (claim-element granular when claims available)
triggers:
  - feature
  - decompose
  - F1
  - F2
---

# Feature Definition Skill

This skill guides you through Stage 2: Decomposing the invention into searchable features.

## Objective

Break down the invention into searchable features that capture what makes it novel.
Granularity depends on what the disclosure provides:

- **Claim-element mode (preferred when claims are present)**: emit **one
  feature per independent claim element or dependent-claim limitation**.
  Expect 8-15 features. This aligns with how SMEs grade prior art
  (element-by-element anticipation) and is what evaluation ground-truth
  datasets compare against. Do NOT merge distinct claim elements into a
  single composite feature.

- **Prose-only mode (fallback when no claim text is present)**: emit 3-7
  composite features that capture what makes the invention novel. Use
  this only when the disclosure has no clear numbered claims or
  sub-elements.

### How to tell which mode to use

**ALWAYS read the original disclosure (e.g. the ORIGINAL invention
description supplied as input to the novelty run, not just the summarized
`/scope.md`)** before deciding. The scoping stage commonly aggregates
claim elements into prose, so `/scope.md` alone will make every
disclosure look like prose-only. Go back to the source disclosure.

If the source disclosure shows numbered claims like "The system of claim
1, further comprising X", numbered "Key Technical Aspects", or a
structured list of structural sub-elements — you are in **claim-element
mode**. Split each sub-element into its own feature. Example: a
disclosure reading "(2) a rectangular float having a divided top platform
and four walls; (3) a cross-shaped support configured to fit between the
four walls; (4) a set of four pontoons..." produces three separate
features (F2 rectangular float, F3 cross-shaped support, F4 four
pontoons) — NOT a single composite "Rectangular Float with Cross-Core
Pontoon Retention" feature.

If in doubt, err toward **more features** (claim-element mode). Evaluation
metrics (`feature_coverage_accuracy`, `feature_recall`) reward
fine-grained alignment with claim structure.

## ⚠️ CRITICAL: OUTPUT FORMAT IS A TABLE — NOT BULLET POINTS

You MUST output the Feature Matrix as a **Markdown table**.

❌ WRONG FORMAT (DO NOT DO THIS):
```
* Core Features
   1. Feature name: Description...
   2. Feature name: Description...
```

✅ CORRECT FORMAT (YOU MUST DO THIS):

| ID | Feature Name | Type | Core? | Priority | Description | Keywords | Variations | Search Strategy |
|----|--------------|------|-------|----------|-------------|----------|------------|-----------------|
| F1 | Feature Name Here | Structural | Y | P1 | Description here | keyword1, keyword2 | • alt1 • alt2 | DWPI + CPC |

---

## Feature Matrix Table Columns (REQUIRED)

Your table MUST have these columns IN THIS ORDER:

| ID | Feature Name | Type | Core? | Priority | Description | Keywords | Variations | Search Strategy |
|----|--------------|------|-------|----------|-------------|----------|------------|-----------------|

### Column Definitions

1. **ID**: F1, F2, F3, etc.

2. **Feature Name**: Short 3-7 word title (e.g., "UV Excitation System")

3. **Type**: One of:
   - `Structural` — Physical component/arrangement
   - `Functional` — Behavior/function
   - `Material` — Material/composition
   - `Process` — Method/sequence
   - `System` — Integration/system-level

4. **Core?**: `Y` = essential for novelty, `N` = supporting only

5. **Priority**: `P1` = critical, `P2` = important, `P3` = optional

6. **Description**: 1-2 sentences explaining the feature

7. **Keywords**: Comma-separated search terms (include synonyms)

8. **Variations**: Known alternatives (use • bullets inline)

9. **Search Strategy**: Brief note (e.g., "DWPI + CPC G01N")

---

## Concrete Example (PA6 Fluorescence Invention)

| ID | Feature Name | Type | Core? | Priority | Description | Keywords | Variations | Search Strategy |
|----|--------------|------|-------|----------|-------------|----------|------------|-----------------|
| F1 | PA6 Granule Degradation Detection | Material | Y | P1 | Detect thermo-oxidative degradation in PA6 granules via UV-induced fluorescence | PA6, polyamide-6, nylon-6, granules, pellets, degradation | • PA66 • Other polyamides | Keyword + Semantic |
| F2 | UV Excitation Band (300-350nm) | Process | Y | P1 | UV light source in 300-350nm range to excite fluorescence | UV excitation, 300-350nm, UVA, LED 320nm | • 280-320nm • 320-380nm | DWPI + CPC G01N21 |
| F3 | Fluorescence Emission Detection | Process | Y | P1 | Measure fluorescence emission in 350-400nm band as degradation indicator | emission 350-400nm, fluorescence detection, photodiode | • 360-390nm • 380-420nm | CPC G01N21/64 |
| F4 | Inline Granule Monitoring System | System | Y | P1 | Real-time monitoring integrated with hopper/conveyor | inline inspection, conveyor sensor, hopper monitoring | • Offline batch • At-line | CPC B29C + G01N |
| F5 | Intensity Thresholding | Functional | N | P2 | Go/no-go decision based on fluorescence intensity vs calibrated threshold | threshold, intensity, calibration, golden sample | • Spectral ratio | Keyword focus |
| F6 | Ambient Light Rejection | Functional | N | P2 | Shielding or modulation to reject ambient light interference | shielding, lock-in, modulation, dark enclosure | • Pulsed LED • Optical filters | NPL + Keyword |

---

## Output Structure (FOLLOW EXACTLY)

Your response MUST follow this EXACT structure:

```markdown
**Stage 2 — Feature Definition**

Gate 1 confirmed. Proceeding to Gate 2 — Feature Definition.

## Feature Matrix

| ID | Feature Name | Type | Core? | Priority | Description | Keywords | Variations | Search Strategy |
|----|--------------|------|-------|----------|-------------|----------|------------|-----------------|
| F1 | ... | ... | Y | P1 | ... | ... | ... | ... |
| F2 | ... | ... | Y | P1 | ... | ... | ... | ... |
| F3 | ... | ... | Y | P1 | ... | ... | ... | ... |
| F4 | ... | ... | N | P2 | ... | ... | ... | ... |

## Feature Matrix Summary

| Metric | Count |
|--------|-------|
| Total Features | X |
| Core Features (Core?=Y) | Y |
| P1 Priority | Z |
| P2 Priority | W |

**Core Features for Novelty Search:** F1, F2, F3, F4

## Exclusions (Out of Scope)

| ID | Exclusion | Reason |
|----|-----------|--------|
| X1 | ... | Not core to novelty |
| X2 | ... | Different application |

---
## 🛑 CONFIRMATION REQUIRED — Stage 2 Gate

**The Feature Matrix above requires your approval before I can proceed.**

Please reply with ONE of the following:
- **"Confirm"** — I will proceed to patent and NPL searches
- **"Edit: [your changes]"** — I will update the matrix and ask again

*I am waiting for your response. No searches will begin until you confirm.*
---
```

---

## Anti-patterns (Avoid)

❌ **Too Broad**: "Uses machine learning" → Too many hits
❌ **Too Narrow**: "Uses ResNet-50 with 224x224 input" → Too few hits
❌ **Non-searchable**: "Better performance" → Can't form queries
❌ **Overlapping**: F1 and F2 are essentially the same thing
❌ **Bullet Points**: NEVER use bullet points or numbered lists for features

## Handling Feature Edits

### When User Adds or Edits a Feature

Before accepting any new or edited feature, you MUST cross-check it against
ALL existing features and exclusions:

1. Compare the new feature against every existing feature. If the new feature
   contradicts an existing one (e.g., F7 says "uses red+IR 660/940nm" but F2
   says "dual-IR only, no red wavelength"), flag the contradiction:

   "F7 appears to contradict F2. F2 specifies [X] while F7 specifies [Y].
   Which is correct? Please clarify before I update the matrix."

2. Compare the new feature against every exclusion. If the new feature
   conflicts with an exclusion (e.g., adding a feature about red wavelength
   sensing when X2 excludes standard red+IR pulse oximetry), flag it:

   "F7 conflicts with exclusion X2 which states [exclusion text]. Should I
   remove X2, or should F7 be revised?"

3. Do NOT silently add contradictory features. Do NOT silently remove
   exclusions to resolve a conflict. Always ask the user to resolve.

## ⛔ User Gate Reminder (CRITICAL)

⛔ **AFTER presenting the feature matrix, you MUST STOP AND WAIT.**

DO NOT:
- Call task() to delegate to any sub-agent
- Start any patent, NPL, or semantic searches
- Enter the Research Loop
- Write any search-related files

DO:
- Present the Feature Matrix table with the confirmation block
- Wait for the user to reply "Confirm" or "Edit"
- Only proceed after explicit user confirmation

This is Gate 2. It is MANDATORY. Skipping it invalidates the entire workflow.

🚫 **THIS IS THE LAST CONFIRMATION**: Once the user confirms features (Gate 2), proceed with ALL remaining stages automatically WITHOUT asking for any more confirmations. Simply execute searches and generate the final report.

## Todo Update Reminders

⚠️ **AFTER COMPLETING FEATURE DEFINITION**: Call `write_todos` to mark "Define features" as `"status": "completed"` and update search tasks to `"status": "in_progress"` when proceeding.

⚠️ **AFTER USER CONFIRMS FEATURES (Gate 2)**: Immediately call `write_todos` to update the todo list before starting searches.
