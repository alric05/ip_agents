---
name: scoping
description: How to scope inventions properly by extracting key information and asking clarifying questions
triggers:
  - scope
  - invention
  - clarifying
  - understand
---

# Scoping Skill

This skill guides you through Stage 1: Scoping the customer's invention.

## Objective

Extract a clear, searchable scope from the customer's invention description.

## Process

### Step 1: Initial Analysis

Read the customer's invention idea and identify:

1. **Technical Domain**: What field is this in? (electrical, mechanical, chemical, software, biotech, etc.)
2. **Problem Statement**: What problem does the invention solve?
3. **Proposed Solution**: How does the invention solve it?
4. **Key Components**: What are the main parts/elements?
5. **Novelty Claims**: What does the customer believe is new?

### Step 2: Clarifying Questions with Proposed Defaults

⚠️ **MANDATORY**: Every question you ask MUST include a `→ **Default if confirmed:**` line showing what will be assumed if the user replies "Confirm defaults". NEVER present a question without its default.

❌ WRONG (question without default):
```
1. **What type is the adapter gear?**
   (a) spur gear, (b) helical gear, (c) bevel gear
```

✅ CORRECT (question with default):
```
1. **What type is the adapter gear?**
   Options: (a) spur gear, (b) helical gear, (c) bevel gear
   → **Default if confirmed: (a) spur gear** — simplest and most common
```

Base your default answers on:
- Typical engineering practice for this domain
- Information inferable from the disclosure
- Common reasonable assumptions

Format each question with its proposed default:

**Technical Details**:
- "What specific mechanism/algorithm does [X] use?" → **Proposed default**: [Your reasoned assumption based on typical practice]
- "What materials/components are involved?" → **Proposed default**: [Common materials for this application]
- "What are the operating conditions (temperature, pressure, etc.)?" → **Proposed default**: [Standard operating ranges for this domain]

**Scope Boundaries**:
- "Is this limited to [specific application] or broader?" → **Proposed default**: [Inferred scope based on disclosure]
- "Are you claiming the combination or individual elements?" → **Proposed default**: [Combination, unless disclosure suggests otherwise]

**Prior Art Awareness**:
- "Are you aware of any similar technologies?" → **Proposed default**: Will search broadly
- "What existing solutions have you seen?" → **Proposed default**: Unknown, will identify in search

### Question Format Template

Present questions in grouped blocks. For EVERY question, show which answer will be used if the user confirms defaults.

⚠️ **RULE**: When a question lists multiple options (a/b/c/d), you MUST mark the default option with **"Default if confirmed"**. The user must be able to see at a glance what "Confirm defaults" will select.

#### Example (follow this pattern exactly):

```markdown
## Clarification Questions

### Technical Implementation

1. **What is the gear sequence?**
   Options: (a) Worm→wheel→adapter→Worm→wheel, (b) Worm→worm→adapter→wheel
   → **Default if confirmed: (a)** — standard cascaded worm arrangement

2. **What type is the adapter gear?**
   Options: (a) spur gear, (b) helical gear, (c) bevel gear, (d) compound gear
   → **Default if confirmed: (a) spur gear** — simplest and most common for this application

3. **What is the output element?**
   Options: (a) rotating lens barrel, (b) cam ring, (c) lead screw nut, (d) direct lead screw
   → **Default if confirmed: (a) rotating lens barrel** — inferred from disclosure

### Scope Boundaries

4. **Primary novelty to protect?**
   Options: (i) two worms + intermediate gear in compact gearbox, (ii) specific spatial layout, (iii) dual-mode rotary+linear, (iv) other
   → **Default if confirmed: (i)** — matches core disclosure emphasis

---

## Defaults Summary

If you confirm, these defaults will be used:

| # | Question | Default Answer |
|---|----------|----------------|
| 1 | Gear sequence | (a) Worm→wheel→adapter→Worm→wheel |
| 2 | Adapter gear type | (a) Spur gear |
| 3 | Output element | (a) Rotating lens barrel |
| 4 | Primary novelty | (i) Two worms + intermediate gear |

**→ Reply "Confirm defaults" to accept all, or answer specific questions.**
```

### Step 3: Scope Formulation

Create a structured scope:

```markdown
## Scope Summary

**Title**: [Descriptive title of the invention]

**Domain**: [Technical field(s)]

**Problem**: 
[1-2 sentences describing the problem]

**Solution**:
[2-3 sentences describing the proposed solution]

**Key Technical Aspects**:
1. [Aspect 1]
2. [Aspect 2]
3. [Aspect 3]

**Novelty Claims** (as stated by customer):
- [What they believe is new about this invention]

**Scope Boundaries**:
- Includes: [What IS covered]
- Excludes: [What is NOT covered]
```

## Deliverable

A `scope_markdown` string containing the formatted scope summary, followed by a request for user confirmation.

**The scope output must include:**
1. The structured scope summary
2. An "Open Questions" table with proposed defaults for each question
3. Clear instructions for the user to either confirm defaults or provide answers

## User Gate Reminder

⚠️ **CRITICAL**: After presenting the scope, you MUST pause and wait for user confirmation before proceeding to Stage 2 (Feature Definition).

Ask: "Reply **'Confirm defaults'** to proceed with the proposed assumptions, or provide your answers to the questions above."

## Todo Update Reminder

⚠️ **AFTER COMPLETING SCOPING**: Immediately call `write_todos` to mark "Scope the invention" as `"status": "completed"` and "Define features" as `"status": "in_progress"` with `"activeForm": "confirmation"`.
