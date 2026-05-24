---
name: npl-search
description: Web of Science NPL search syntax and best practices
triggers:
  - npl
  - academic
  - web of science
  - paper
  - literature
---

# NPL Search Skill

This skill guides you through Stage 3B: Non-Patent Literature Search using Web of Science.

## Web of Science Query Syntax

### Field Tag Syntax (CRITICAL!)

```
TAG=(search terms)
```

⚠️ **NO SPACES** around the `=` sign! ✅ `TS=(term)` ❌ `TS = (term)`

⚠️ **ALL QUERIES MUST START WITH A FIELD TAG!**
❌ `polymer AND fluorescence` — Causes MISS_TAGEQ error!
✅ `TS=(polymer AND fluorescence)`

---

## Field Tags Reference

| Tag | Field | Lemmatization | Use When |
|-----|-------|---------------|----------|
| `TS=` | Topic (title + abstract + keywords) | ✅ Yes | General concept search (BEST for recall) |
| `TI=` | Title only | ✅ Yes | Precise searches, term MUST be in title |
| `AB=` | Abstract only | ✅ Yes | Detailed concept matching |
| `AK=` | Author Keywords | ❌ No | Established terminology (exact match) |
| `AD=` | Address/Affiliation | ❌ No | Institution searches (use with SAME) |
| `SO=` | Source (journal name) | ❌ No | Journal-specific searches |
| `AU=` | Author | ❌ No | Author name searches |
| `PY=` | Publication Year | ❌ No | Time-bounded (NO wildcards!) |
| `DO=` | DOI | ❌ No | Digital Object Identifier |
| `OG=` | Organization-Enhanced | ❌ No | Enhanced organization search |

---

## ⚠️⚠️⚠️ CRITICAL: FORBIDDEN OPERATORS ⚠️⚠️⚠️

The following operators are **INVALID** in Web of Science and **WILL CAUSE ERRORS**:

| Operator | Error | Use Instead |
|----------|-------|-------------|
| `ADJ`, `ADJ/N` | Invalid | Use `NEAR/N` |
| `SENTENCE` | Not supported | Use `NEAR/15` |
| `PARAGRAPH` | Not supported | Use `NEAR/25` |
| `QUOTA ("term"=N)` | Not supported | Use multiple ORs |
| `@(field)` | Invalid | Use `TS=`, `TI=`, `AB=` |
| `"phrase"~N` | Not supported | Use `NEAR/N` |
| `%` wildcard | Invalid | Use `*` |

---

## ⚠️⚠️⚠️ CRITICAL: NEVER USE "AND" INSIDE NEAR CLAUSES ⚠️⚠️⚠️

This is the **#1 cause of query failures**!

### ❌ FATAL PATTERNS (WILL CRASH)

```
TS=((soft AND compliant) NEAR/5 gripper)         ← AND_IN_NEAR error!
TS=(gripper NEAR/5 (soft AND compliant))         ← AND_IN_NEAR error!
TS=((A AND B) NEAR/5 (C AND D))                  ← AND_IN_NEAR error!
TS=(term1 NEAR/5 (term2 AND term3 AND term4))    ← AND_IN_NEAR error!
```

### ✅ SAFE PATTERNS (ALWAYS USE)

```
TS=((soft OR compliant) NEAR/5 gripper)           ← Use OR inside NEAR
TS=(gripper NEAR/5 soft) AND TS=(compliant)       ← AND at TOP level only
TS=(soft NEAR/5 gripper) AND TS=(compliant NEAR/5 gripper)  ← Distribute
```

---

## Proximity Operators

| Operator | Meaning | Max Value |
|----------|---------|-----------|
| `NEAR/x` | Terms within x words (ANY order) | x = 0-15 |
| `SAME` | Terms in SAME SENTENCE | N/A |

### NEAR/0 means ADJACENT
```
TS=(carbon NEAR/0 nanotube)  → "carbon nanotube" or "nanotube carbon"
```

### SAME Operator (for Address searches)
```
AD=(McGill Univ SAME Quebec SAME Canada)
```
All terms must appear in the SAME address line.

---

## Boolean Operators

| Operator | Precedence | Use |
|----------|------------|-----|
| `NEAR/x` | 1 (highest) | Proximity |
| `SAME` | 2 | Address searches |
| `NOT` | 3 | Exclusion |
| `AND` | 4 | Conjunction |
| `OR` | 5 (lowest) | Disjunction |

⚠️ **USE PARENTHESES** to override precedence!

```
❌ copper OR lead AND algae → copper OR (lead AND algae)
✅ (copper OR lead) AND algae → correct intent
```

---

## Wildcards — DETAILED RULES

### Three Wildcard Characters

| Symbol | Meaning | Example |
|--------|---------|---------|
| `*` | 0+ characters | `oxid*` → oxidation, oxidative, oxidizing |
| `?` | Exactly 1 character | `wom?n` → woman, women (NOT "womn") |
| `$` | 0 or 1 character | `colo$r` → color, colour |

### ⚠️ MINIMUM CHARACTER RULE

| Position | Requirement | Examples |
|----------|-------------|----------|
| Right-hand truncation | 3+ chars BEFORE wildcard | ✅ `oxid*` ❌ `ox*` |
| Left-hand truncation | 3+ chars AFTER wildcard | ✅ `*oxide` ❌ `*ox` |

### Practical Wildcard Examples

```
✅ TS=(enzym*)                  → enzyme, enzymes, enzymatic
✅ TS=(oxidi?ation)             → oxidization, oxidisation
✅ TS=(colo$r)                  → color, colour
✅ TS=(behavio$r)               → behavior, behaviour
✅ TS=(photo* NEAR/5 catal*)    → photocatalyst, photocatalytic
✅ TS=(organi?ation*)           → organisation, organizations
❌ TS=(UV*)                     → FAILS (only 2 chars before *)
❌ TS=(*synthesis)              → Left-hand truncation discouraged
```

### Combining Wildcards

```
✅ organi?ation* → organisation, organisations, organizational
✅ l?chee$ → lichee, lichees, lychee, lychees
```

---

## Lemmatization (AUTOMATIC!)

WoS **automatically expands terms** — no wildcards needed for common variations:

```
cite → cite, citing, cites, cited, citation
defense → defense, defence
mouse → mouse, mice
color → color, colour
```

### Where Lemmatization Applies

| Field | Lemmatization |
|-------|---------------|
| `TS=` (Topic) | ✅ Full lemmatization |
| `TI=` (Title) | ✅ Full lemmatization |
| `AB=` (Abstract) | ✅ Full lemmatization |
| `AK=` (Author Keywords) | ❌ NO lemmatization |
| `"quoted phrases"` | ❌ NO lemmatization |

### To Disable Lemmatization — Use Quotes

```
"mouse" → finds ONLY mouse, NOT mice
"color" → finds ONLY color, NOT colour
```

⚠️ **Lemmatization is DISABLED when using wildcards**:
```
color* → color, colors, colorful but NOT colour
```
To find ALL variants: `color* OR colour*`

---

## Safe Query Patterns (ALWAYS USE)

### Pattern A — Synonyms with AND (SAFEST, no NEAR)

```
TS=((polyamide OR PA6 OR "nylon-6") AND fluorescence AND degradation)
TS=((UV OR ultraviolet) AND (fluorescence OR luminescence) AND polymer*)
```

### Pattern B — NEAR with Simple OR Groups Only

```
TS=((fluorescen* OR luminescen*) NEAR/5 polymer)
TS=(UV NEAR/3 (excitation OR emission))
TS=((soft OR compliant) NEAR/5 gripper)
```

### Pattern C — Multiple NEAR Clauses with Top-Level AND

```
TS=(UV NEAR/3 excitation) AND TS=(polymer NEAR/5 degradation)
TS=(thermal NEAR/5 degradation) AND TS=(fluorescence AND detection)
```

### Pattern D — Cross-Field Search

```
TI=(fluorescence) AND AB=(polyamide AND detection)
TI=(term1) AND AB=(term2 AND term3)
AK=(technique) AND TS=(application)
```

---

## Query Construction Strategy

### Level 1: NQP-1 — Topic Seed Queries

```
TS=((polyamide OR PA6) AND fluorescence AND degradation)
```

### Level 2: NQP-2 — Synonym Expansion

```
TS=((polymer* OR plastic* OR thermoplast*) AND (fluorescen* OR luminescen*))
```

### Level 3: NQP-3 — Cross-Field + Journal Filter

```
TI=(fluorescence) AND AB=(polymer AND detection)
TS=(polymer degradation) AND SO=(Polymer Degradation and Stability)
```

### Level 4: NQP-4 — Broader NEAR

```
TS=((polymer OR plastic) NEAR/15 (quality OR inspection))
```

---

## Domain-Specific Examples

### Polymer/Fluorescence Domain

```
TS=((polyamide OR PA6 OR "nylon-6") AND (fluorescence OR luminescence) AND degradation)
TS=(UV NEAR/3 excitation) AND TS=(inline AND monitoring)
TS=((thermo-oxidative OR thermal) NEAR/5 degradation) AND TS=(polymer*)
TI=(fluorescence) AND AB=(polyamide AND detection)
TS=((pellet* OR granule*) AND (inspection OR monitoring OR quality))
TS=(colo$r AND polymer)  ← finds color OR colour
```

### Robotics Domain

```
TS=((auxetic OR re-entrant) NEAR/5 gripper)
TS=((soft OR compliant OR flexible) NEAR/3 (gripper OR manipulator))
TI=(soft robot*) AND SO=(IEEE)
```

---

## Result Extraction

For each relevant paper, extract:

| Field | Description |
|-------|-------------|
| DOI | Digital Object Identifier |
| Title | Paper title |
| Authors | First author et al. |
| Journal | Publication venue |
| Year | Publication year |
| Abstract | First 200 chars |
| Relevance | A/B/C triage label |

---

## Common Pitfalls

❌ **Missing field tag**: `polymer AND fluorescence` — MISS_TAGEQ error!
❌ **Spaces around =**: `TS = (term)` BREAKS!
❌ **AND inside NEAR**: `TS=((A AND B) NEAR/5 C)` — AND_IN_NEAR error!
❌ **ADJ operator**: Use `NEAR/N` instead
❌ **Wildcard too short**: `de*` (need 3+ chars before *)
❌ **@(field) syntax**: This is Innography, not WoS!
❌ **Wildcards in PY**: `PY=202*` is invalid
