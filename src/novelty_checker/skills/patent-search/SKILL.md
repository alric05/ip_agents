---
name: patent-search
description: Derwent Patent Search syntax and best practices
triggers:
  - patent
  - derwent
  - prior art
  - novelty search
  - field syntax
---

# Patent Search Skill

This skill guides you through patent database search using Derwent Patent Search.

## ⚠️ Prefer DWPI-Enhanced Fields

Derwent Patent Search supports both **DWPI-enhanced fields** (`NOV=`, `TID=`, `TIT=`, `CTB=`) and **generic fields** (`TI=`, `AB=`, etc.). DWPI fields are curated by experts and provide higher precision — always prefer them over generic equivalents. See §4 for the full field reference and §6 for the search strategy.

## Critical Syntax Rules

- Every query **must begin with a field tag** (`CTB=`, `ALL=`, `IC=`, etc.).
- Every query **should end with a semicolon** `;`. Derwent will add one automatically if omitted, but always include it explicitly for clarity.
- Every concept group **must be enclosed in parentheses**.
- Every opening parenthesis **must be preceded by an operator** (AND, OR, NOT, SAME, NEARn, ADJn) or a field tag. No bare/orphan parentheses.
- The **default operator** between two adjacent words with no explicit operator is **ADJ** (phrase match). Always use an explicit operator to avoid ambiguity.
- **Always use numbered proximity operators** (`ADJ1`, `ADJ3`, `NEAR5`, etc.). Never use bare `ADJ` or `NEAR` without a number.
- **Only AND, OR, and NOT are allowed between field tags.** Proximity operators (ADJn, NEARn, SAME) can only appear between terms *inside* a single field tag. If you place them between fields, Derwent will reject the query with: `"You have used a proximity operator like ADJ, NEAR or SAME between fields and only the Boolean operators AND, OR, and NOT are allowed between fields."`
- ⚠️ **Do not rely on implicit operators.**
  Adjacent terms without an explicit operator are treated as `ADJ` and can unintentionally:
  - force phrase matching
  - create hidden proximity chains
  - trigger proximity‑limit errors in complex queries
  Always specify operators explicitly.

### Operator Precedence

Operators are processed in this order (highest precedence first):

```
ADJ / NEAR  >  SAME  >  AND / NOT  >  OR
```

Use parentheses to override default precedence whenever mixing operators.

---

## 1. Boolean Operators

| Operator | Meaning | When to Use |
|----------|---------|-------------|
| `AND` | Both terms must be present | Combining independent concepts |
| `OR` | At least one term must be present | Listing synonyms or alternatives for one concept |
| `NOT` | First term present, second absent | Removing ambiguous meanings. Use with caution — risks excluding relevant results |

---

## 2. Proximity Operators

Proximity operators can **only** be used between terms **within a single field tag**. They **cannot** span across AND-joined fields or sit between field tags like CTB=, ALL=, or IC=. Only AND, OR, and NOT can join separate field tags.
- **Numeric limits:** Proximity operators must use values ≤ 100.
  Any `ADJn` or `NEARn` with n > 100 (explicitly or implicitly) will be rejected by Derwent.
- **Proximity operators must be fully contained within a single field scope.**
  The entire proximity expression must appear inside the same `FIELD=( ... )` block.
  ✅ Valid: `TI=((foldable OR flexible) ADJ3 display*)`
  ❌ Invalid: `TI=(foldable OR flexible) ADJ3 display*`

```
✅ CTB=((solar NEAR5 panel) SAME (connector*)) AND CTB=(modular);
❌ CTB=(solar NEAR5 panel) NEAR5 CTB=(connector*);
   → Error: "You have used a proximity operator like ADJ, NEAR or SAME between fields"
```

| Operator | Meaning | When to Use |
|----------|---------|-------------|
| `ADJn` | Within n words after the first (order preserved, up to n−1 intervening words). `ADJ1` = immediately adjacent. | Fixed phrases: `ADJ1`. Stable word order with minor insertions: `ADJ2`–`ADJ3` (e.g. `heat ADJ2 treatment`) |
| `NEARn` | Within n words, either order (up to n−1 intervening words). `NEAR1` = adjacent either order. | Concepts phrased together but rewordable. n=3–5 tight coupling, 5–10 loose |
| `SAME` | Both terms in the same paragraph | Linked concepts described variably in the same paragraph. Also the fallback when the right NEARn value is unclear |

### How to Choose a Proximity Operator

1. Fixed phrase, never reworded? → **ADJ1**
2. Order preserved but 1–2 words may be inserted? → **ADJn** (n = max insertions + 1)
3. Either order, adjacent? → **NEAR1**
4. Either order, a few intervening words? → **NEARn** (n = 3–5 tight, 5–10 loose)
5. Related concepts described variably in the same paragraph? → **SAME**
6. Unsure what n should be? → Default to **SAME**
7. - When unsure about the correct `NEARn` distance, prefer **`SAME`**. `SAME` avoids numeric proximity limits while remaining valid within a field.

---

## 3. Truncation and Wildcards

| Symbol | Meaning | Example |
|--------|---------|---------|
| `*` | 0 or more characters (start, middle, or end) | `comput*` → computer, computing, computational |
| `?` | Exactly one character | `stabili?e` → stabilise, stabilize |
| `*n` | 0 to n additional characters | `colo*1r` → color, colour |
| `{d}` | Any single digit | |
| `{a}` | Any single letter | |
| `{c}` | Any consonant | |
| `{v}` | Any vowel | |

⚠️ **Caution**: Truncation on short stems over-matches. `cat*` matches catalog, cattle, category. When the stem is ambiguous, list explicit forms instead (`cat OR cats`).

---

## 4. Field Tags

### Text Search Fields (ordered by precision → recall)

| Tier | Tag | Scope | When to Use |
|------|-----|-------|-------------|
| **1 — Precision** | `NOV=` | DWPI Novelty statement — the unique inventive feature that is new and an improvement on existing technology | Start here. Best for finding the core inventive concept. Also use for IPC harvesting (see §8) |
| **1 — Precision** | `TID=` | DWPI Title — concise English-language title written by DWPI experts highlighting scope, use, and novelty | High-precision keyword searches targeting expert-curated content |
| **1 — Precision** | `TIT=` | DWPI Title Terms — auto-generated preferred forms of words in DWPI titles. May retrieve records even if the exact term does not appear in the title | Harvesting classification codes and broad title-level discovery |
| **2 — Balanced** | `CTB=` | Title + Abstract + Claims (includes DWPI enhanced title/abstract and original title/abstract) | Main workhorse for novelty searches. Use after Tier 1 or as default for broader keyword searches |
| **3 — Broad** | `ALL=` | All text fields including full description/disclosure | Broadening step. Any mention in the disclosure can be novelty-destroying |

### Generic Fields

These are standard (non-DWPI) fields. They work in Derwent but lack DWPI expert curation. Prefer the DWPI equivalents above when available.

| Tag | Scope | DWPI Equivalent |
|-----|-------|-----------------|
| `TI=` | Original patent title | Prefer `TID=` or `CTB=` |
| `AB=` | Original patent abstract | Prefer `CTB=` |
| `CL=` | Claims text | Prefer `CTB=` (includes claims) |
| `DESC=` | Full description/disclosure | Prefer `ALL=` |
| `PA=` | Patent assignee (as published) | Prefer `CUPPA=` (ultimate parent) |
| `IN=` | Inventor name | No DWPI equivalent — use directly |

### Non-Text Fields

| Tag | Scope | Notes |
|-----|-------|-------|
| `IC=` | IPC classification code | For parallel classification-based searches. Combine with keyword search via OR |
| `PRD>=` | Earliest priority date (YYYYMMDD format) | For date-restricted searches. See §5.3 |
| `CUPPA=` | Ultimate parent assignee | For assignee/competitor searches. See §7.5 |

### DWPI-Specific Field Examples

```
NOV=(laser AND robot);
TID=(((printer AND scanner) NOT inkjet));
TIT=(((print AND scan) NOT ink));
```

- **Independent** concepts are joined with **AND**, each in its own field tag.
- **Linked** concepts (e.g. an object and the process applied to it) are joined with **SAME** within the same field tag.

## 5. Query Assembly Rules

### 5.1 Within a Concept

- All synonyms for a single concept are joined by **OR**.
- Multi-word synonyms use the appropriate proximity operator between their component terms.
- Wrap each concept group in parentheses.

### 5.2 Between Concepts

- **Independent** concepts are joined with **AND**, each in its own field tag.
- **Linked** concepts (e.g. an object and the process applied to it) are joined with **SAME** within the same field tag.

### 5.3 Date Restrictions

**Novelty search (patentability):** Do **not** apply any date restriction. A comprehensive novelty search must confirm the technology has never been described anywhere at any point in time.

**Freedom-to-operate search:** Use the earliest priority date field `PRD>=` to cover the relevant period. Patents last 20 years, but patent term extensions are possible. Recommendations:

- General technology: **20 years back** from today.
- Pharmaceutical technology: **25 years back** from today.

```
... AND PRD>=(20060101);
```

### 5.4 Templates

**Independent concepts:**
```
CTB=(concept1 terms) AND CTB=(concept2 terms) AND ...;
```

**Linked concepts within one field:**
```
CTB=((object synonyms) SAME (process synonyms));
```

**Parallel classification search:**
```
CTB=(remaining keyword concepts) AND IC=(classification code);
```

Combine keyword and classification queries using **OR** in search management. Terminate each query with a semicolon.

### 5.5 Multi-Line Queries

When a search requires combining multiple independent search statements (e.g. a keyword search OR an assignee search), use multi-line syntax:

- Intermediate statements end with a **colon** `:` (not a semicolon). The colon is **required**.
- The **final** statement ends with a **semicolon** `;`.
- The final line combines previous statements by their line numbers.

**Syntax constraints (rule-like):**
- Every intermediate line **must end with `:`**
- Only the final line **may end with `;`**
- Line numbers can only be referenced after a colon‑terminated definition
- Proximity operators are not allowed across referenced lines


```
CTB=(keyword search terms):
IC=(classification) AND CUPPA=(assignee):
1 OR 2;
```

This is especially useful when incorporating assignee searches alongside keyword searches.

---

## 6. Search Strategy

### 6.1 Precision Ladder

Every search must progress through field tiers from narrow to broad. Do not skip straight to `CTB=` or `ALL=`.

| Step | Field Tier | Purpose | Action |
|------|-----------|---------|--------|
| **A** | `NOV=` / `TID=` | Precision — find inventions where the concept is the core novelty | Run 1–3 queries using core concepts and tight proximity |
| **B** | `CTB=` | Balanced — capture patents where the concept appears in title, abstract, or claims | Broaden synonyms, relax proximity (SAME instead of NEARn) |
| **C** | `ALL=` | Broad — sweep the full disclosure text | Same queries as Step B but with ALL= |
| **D** | `IC=` | Classification — parallel path | Run alongside Steps A–C if a strong IPC match exists (see §8) |

### 6.2 One-Turn vs Multi-Turn Mode

The system prompt defines whether the agent operates in **one-turn** or **multi-turn** mode. The skill file does not decide the mode — but the agent must follow different strategies in each.

**One-turn mode** (produce all queries in a single response):

- Generate a **complete query set** covering all tiers of the precision ladder (A → B → C, and D if applicable) in one output.
- Use **multi-line query syntax** to combine tiers where appropriate.
- Include broadening variations (relaxed proximity, expanded synonyms) as separate queries rather than waiting for result feedback.
- The output should be a numbered list of queries the user can run in sequence, from most precise to broadest.

**Multi-turn mode** (iterative search with result feedback):

- **Start narrow** — run Tier A queries (`NOV=` / `TID=`) first.
- Review result counts and sample results before broadening.
- Progress to Tier B (`CTB=`) only if Tier A yields insufficient results.
- Progress to Tier C (`ALL=`) only if Tier B is still insufficient.
- Adjust synonyms, proximity distances, and concept groupings between turns based on what the results reveal.
- Use `TIT=` to harvest IPC codes from early results to inform classification searches in later turns.

### 6.3 Concept Decomposition (Both Modes)

Before writing any query, decompose the invention into independent concepts:

1. **Identify** 3–5 key concepts from the invention disclosure.
2. **Classify** each concept as Core, Linked, or Narrowing.
3. **Generate synonyms** for each concept (see §5.1).
4. **Decide relationships** — which concepts are independent (AND across field tags) vs linked (SAME within one field tag).
5. **Write queries** — start with the most distinctive feature pair, not all features at once.

When a search requires combining multiple independent search statements (e.g. a keyword search OR an assignee search), use multi-line syntax:

## 7. Reusable Query Patterns

### 7.1 Object + Process

Object and its manufacturing/processing method, linked by SAME:

```
CTB=((object synonyms) SAME (process synonyms));
```

**Example** — manufacturing a cat toy:
```
CTB=(((cat or cats or feline* or kitten* or pet or pets) NEAR5 (toy or plaything or play ADJ1 thing)) SAME (manufacturing or manufacture or producing or production));
```

### 7.2 Product + Component Material

A product containing specific materials:

```
CTB=((product synonyms) SAME (component synonyms)) AND CTB=(other component synonyms);
```

**Example** — dry cat food with phyllosilicates:
```
CTB=((dry or dried or granular or kibble) SAME ((cat or cats or feline* or kitten*) NEAR5 (food or nutrition))) AND CTB=(phyllosilicates or sheet ADJ1 silicates or layer ADJ1 silicates);
```

### 7.3 Keyword + Classification (Parallel)

Run both and combine with OR:
```
Search A: CTB=(keyword concepts);
Search B: CTB=(narrowed keywords) AND IC=(code);
Final: Search A OR Search B
```

### 7.4 Process + Conditions

```
CTB=((process synonyms) SAME (object synonyms)) AND CTB=(condition synonyms);
```

**Example** — heat treating a fibre bundle:
```
CTB=((heat ADJ1 treat* or heating or warming) SAME (bundle or collection or group) SAME (fiber* or fibre*));
```

### 7.5 Assignee Searches

There are two scenarios for incorporating assignees.

**Scenario 1 — Assignee covers only the relevant technology area** (all their patents could be relevant):

Add the assignee in `CUPPA=` joined by OR to the main search. Use extra parentheses to ensure correct processing given operator precedence (`ADJ/NEAR > SAME > AND/NOT > OR`).

```
(IC=((A23K005042)) AND CTB=(cat or cats or kitten* or feline*) OR CUPPA=(in ADJ1 bowl ADJ1 animal ADJ1 health)) AND PRD>=(20030101);
```

**Scenario 2 — Assignee covers a broader technology range** (only some patents relevant):

Filter the assignee's results with an IPC code to focus on the relevant technology area.

Single-line:
```
ALL=(keyword search) AND IC=(code) AND ALL=(material terms) OR (IC=((A23K005040 OR A23K005042 OR A23K005045 OR A23K005048)) AND CUPPA=(mars));
```

Multi-line (preferred for readability):
```
ALL=((Cat or cats or feline* or kitten*) SAME (preparing or prepared or manufacture or manufacturing or preparation or producing or production)) AND IC=(A23K005042) AND ALL=((Phyllosilicates or sheet ADJ1 silicates or layer ADJ1 silicates) OR (Glucomannan or Glucomannans or konjac ADJ1 mannan or konjac ADJ1 powder or konjac ADJ1 gum or E425)):
IC=((A23K005040 OR A23K005042 OR A23K005045 OR A23K005048)) AND CUPPA=(mars):
1 OR 2;
```

**Example** — heat treating a fibre bundle:
```
CTB=((heat ADJ treat* or heating or warming) SAME (bundle or collection or group) SAME (fiber* or fibre*));
```

## 8. IPC / CPC Selection Guidance

Only use IPC classification codes when there is a **strong match** to the concept being searched — one that requires no more than a few additional keywords to focus.

### How to Decide Whether to Use an IPC

1. Run a keyword search for the concept of interest using the `NOV=` field tag.
2. Review the IPC codes present in the results.
3. If one class appears on **75% or more** of the results → good candidate to use.
4. If no single class dominates → do not use IPC for this concept.

### How to Choose the Right IPC Granularity

1. Run searches with the broadest (4-character) IPC and a more specific sub-class.
2. Compare hit counts.
3. If the broad IPC returns **double or more** the hits of the narrow one → prefer the narrow one first.

Not every concept has a useful IPC. For example, "cat toy" has no specific IPC class, so keyword-only searching is appropriate.

---

## 9. Worked Example: Palatable Dry Cat Food

**Invention**: Producing palatable dry cat food comprising phyllosilicates and/or glucomannans with a palatability enhancer.

### Step 1 — Identify key concepts

| # | Concept | Type | Relationship |
|---|---------|------|--------------|
| 1 | Dry cat food | Core | Linked to #2 via SAME |
| 2 | Preparation / production | Linked to #1 | Same paragraph as the food |
| 3 | Phyllosilicates or glucomannans | Core | Two alternatives joined by OR |
| 4 | Palatability | Narrowing | Could be dropped to broaden |

### Step 2 — Identify synonyms

| Concept | Synonyms | Proximity Logic |
|---------|----------|-----------------|
| Dry cat food | dry, dried, granular, kibble + cat, cats, feline, kitten, pet, pets + food, nutrition | Dryness SAME with (animal NEAR5 food) |
| Preparation | preparing, prepared, manufacturing, manufacture, preparation, producing, production | Joined to concept 1 via SAME |
| Phyllosilicates | phyllosilicates, sheet silicates, layer silicates | Multi-word forms use ADJ1 |
| Glucomannans | glucomannan, glucomannans, konjac mannan, konjac powder, konjac gum, E425 | Multi-word forms use ADJ1 |
| Palatability | organoleptic | Single terms, OR |

### Step 3 — Construct queries (Tier A: Precision)

Start with DWPI expert fields to find patents where these concepts are the core novelty:

**Novelty field — core concept pair (food + material):**
```
NOV=((cat or cats or feline* or kitten*) NEAR5 (food or nutrition) AND (phyllosilicates or glucomannan*));
```

**DWPI title — broader concept:**
```
TID=((cat or feline*) AND (food or nutrition) AND (phyllosilicate* or glucomannan* or konjac));
```

**Title terms — for IPC harvesting:**
```
TIT=((cat AND food) AND (mineral or silicate or glucomannan));
```

Review Tier A results. If insufficient, proceed to Tier B.

### Step 4 — Construct queries (Tier B: Balanced — CTB=)

**Keyword search:**
```
CTB=((Dry or dried or granular or kibble) SAME ((Cat or cats or feline* or kitten* or pet or pets) NEAR5 (food or nutrition)) SAME (preparing or prepared or manufacture or manufacturing or preparation or producing or production)) AND CTB=((Phyllosilicates or sheet ADJ1 silicates or layer ADJ1 silicates) OR (Glucomannan or Glucomannans or konjac ADJ1 mannan or konjac ADJ1 powder or konjac ADJ1 gum or E425));
```

**Classification search** (IPC A23K005042 = Dry cat or dog food):
```
CTB=((Cat or cats or feline* or kitten*) SAME (preparing or prepared or manufacture or manufacturing or preparation or producing or production)) AND IC=(A23K005042) AND CTB=((Phyllosilicates or sheet ADJ1 silicates or layer ADJ1 silicates) OR (Glucomannan or Glucomannans or konjac ADJ1 mannan or konjac ADJ1 powder or konjac ADJ1 gum or E425));
```

Combine both searches using OR in search management.

### Step 5 — Broaden if needed (Tier C: ALL=)

Replace `CTB=` with `ALL=` in both queries and combine again using OR.

### Step 6 — Add date restriction (freedom-to-operate only)

Append `AND PRD>=(YYYYMMDD)` to each query with the appropriate date:
```
ALL=((Cat or cats or feline* or kitten*) SAME (preparing or prepared or manufacture or manufacturing or preparation or producing or production)) AND IC=(A23K005042) AND ALL=((Phyllosilicates or sheet ADJ1 silicates or layer ADJ1 silicates) OR (Glucomannan or Glucomannans or konjac ADJ1 mannan or konjac ADJ1 powder or konjac ADJ1 gum or E425)) AND PRD>=(20060101);
```

### Step 7 — Add assignee (if needed)

Use multi-line syntax to add a competitor search filtered by IPC:
```
ALL=((Cat or cats or feline* or kitten*) SAME (preparing or prepared or manufacture or manufacturing or preparation or producing or production)) AND IC=(A23K005042) AND ALL=((Phyllosilicates or sheet ADJ1 silicates or layer ADJ1 silicates) OR (Glucomannan or Glucomannans or konjac ADJ1 mannan or konjac ADJ1 powder or konjac ADJ1 gum or E425)):
IC=((A23K005040 OR A23K005042 OR A23K005045 OR A23K005048)) AND CUPPA=(mars):
1 OR 2;
```

---

## 10. Common Mistakes

- Using **generic fields** (`TI=`, `AB=`, `CL=`) when DWPI equivalents (`TID=`, `NOV=`, `CTB=`) are available — DWPI fields are expert-curated and more precise.
- **Skipping Tier 1 fields** (`NOV=`, `TID=`) and jumping straight to `CTB=` or `ALL=` — always start narrow.
- Using **bare ADJ or NEAR** without a number — always use numbered forms (`ADJ1`, `ADJ3`, `NEAR5`).
- Forgetting **spelling variants**: fibre/fiber, colour/color, stabilise/stabilize.
- **Over-truncating** ambiguous stems (`cat*` matches catalog, cattle).
- **ANDing too many concepts**, making the search too restrictive.
- Using **NOT** without considering whether it removes relevant results.
- Treating **linked concepts as independent ANDs** instead of joining with **SAME**.
- Placing **proximity operators across different field tags** — they only work within a single field. They cannot sit between CTB=, ALL=, or IC= blocks.
- Using **no explicit operator** between terms — the default is ADJ/ADJ1 (immediate phrase match), which is often not what you want.
- **Opening a parenthesis without a preceding operator** — every `(` must follow an operator or field tag.
- **Applying date restrictions to novelty searches** — novelty must cover all time.
- **Forgetting colons** in multi-line queries — intermediate lines need `:`, only the final line gets `;`.
- **Missing parentheses** when mixing OR with AND — remember operator precedence: `ADJ/NEAR > SAME > AND/NOT > OR`.

**Illegal but tempting syntax patterns:**
- `FIELD=(term1) ADJ3 term2` → proximity must be inside the parentheses
- `FIELD1=(...) SAME FIELD2=(...)` → SAME cannot join fields
- `(term1 OR term2)` without a preceding field tag or operator → invalid
