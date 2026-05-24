---
name: semantic-search
description: NGSP semantic/vector search best practices - YOUR SECRET WEAPON!
triggers:
  - semantic
  - ngsp
  - vector
  - similarity
  - gist
  - vocabulary
  - synonyms
---

# Semantic Search Skill

This skill guides you through semantic search using NGSP (Natural Language Graph Search Platform).

## ⭐⭐⭐ SEMANTIC SEARCH IS YOUR SECRET WEAPON! ⭐⭐⭐

The NGSP semantic search finds patents that keyword searches **MISS** because it understands **MEANING**, not just exact word matches.

### Why This Changes Everything

| Keyword Search | Semantic Search |
|----------------|------------------|
| Matches exact words only | Matches **MEANING** |
| Misses synonyms and variants | Finds different vocabulary for same concept |
| Limited to terms you know | Discovers terminology you didn't consider |
| May miss cross-domain patents | Finds conceptually similar inventions |
| Good for known terminology | **ESSENTIAL** for novel concepts |

### The Vocabulary Feedback Loop (Critical!)

Semantic search enables a powerful feedback loop:

```
┌─────────────────────────────────────────────────────────────────┐
│ Round 1: Keyword finds "UV fluorescence detection"              │
│          Semantic finds "photoluminescence inspection" (NEW!)   │
│                            ↓                                    │
│ Round 2: Add "photoluminescence" to keyword queries             │
│          → Find patents that keyword alone would MISS!          │
│                            ↓                                    │
│ Round 3: Semantic finds "luminescence spectroscopy" (NEW!)      │
│          → Even more complete coverage!                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## ⚠️ NEVER SKIP SEMANTIC SEARCH! ⚠️

Include semantic-researcher in EVERY research round:

```python
# Round 1: Always include semantic alongside keyword searches
task(description="Patent keyword search...", subagent_type="patent-researcher")
task(description="NPL keyword search...", subagent_type="npl-researcher")  
task(description="Semantic search...", subagent_type="semantic-researcher")  # NEVER SKIP!
```

---

## Key Principle: Natural Language, NOT Boolean!

NGSP uses vector embeddings to find semantically similar documents. Write queries as **natural language descriptions**, NOT Boolean expressions.

❌ **Wrong**: `hydraulic AND valve AND variable AND orifice`
✅ **Right**: `A hydraulic valve system with variable orifice control for adaptive flow regulation`

---

## ⭐ The Six Query Types (Use ALL!) ⭐

### TYPE A — Invention Gist (Overall)

Summarize the **entire invention** in 1-2 sentences:

```
"A method for detecting thermal degradation in polymer pellets using 
UV-induced fluorescence spectroscopy with specific excitation and 
emission wavelength ranges."
```

### TYPE B — Feature-Specific Gist

Create a **separate gist per feature**:

```
F1: "UV fluorescence detection method for polymer quality assessment"
F2: "Polyamide PA6 material degradation monitoring"
F3: "Spectral analysis with 300-350nm excitation wavelength"
F4: "At-line process analytical technology for pellet inspection"
```

### TYPE C — Mechanism Gist (How it works)

Focus on the **HOW**:

```
"Detecting oxidative degradation by measuring fluorescence intensity 
changes in polymer materials exposed to UV light."
```

### TYPE D — Problem/Application Gist (What it solves)

Focus on the **problem solved**:

```
"Quality control system for identifying degraded polymer pellets 
before they enter the manufacturing process."
```

### TYPE E — Alternative Terminology Gist

Use **different vocabulary** for the same concept:

```
"Photoluminescence-based inspection of thermoplastic granules for 
detecting aging and thermal history effects."
```

### TYPE F — Cross-Pollination Gist

Use **titles of A-refs** as new queries to find related patents.

---

## Recommended Query Count Per Cycle

| Cycle | Minimum | Ideal | For Gap Features |
|-------|---------|-------|------------------|
| 1 | 3 | 5-7 | +2 per gap |
| 2 | 2 | 4-5 | +2 per gap |
| 3+ | 2 | 3-4 | +1 per gap |

**Rule**: 1 gist per feature + 1-2 overall invention gists per cycle.

---

## Query Construction Best Practices

### DO ✅

- Write in **plain English** (no Boolean operators)
- Use **1-3 sentences** (sweet spot for embedding quality)
- Include **key technical terms** from the domain
- Describe the **function** (what it does)
- Describe the **mechanism** (how it works)
- **Vary phrasing** across queries for better coverage
- Focus on: **what it does, how it works, what problem it solves**

### DON'T ❌

- Use Boolean operators (AND, OR, NOT)
- Send the full invention disclosure (too long, confidential!)
- Write single-word queries (not enough semantic context)
- Write paragraphs (dilutes the semantic signal)
- Add unrelated context (confuses the embedding)

---

## Query Templates

### For Mechanical Features

```
"A [mechanism type] comprising [key components] for [function/purpose] 
in [application domain]"

Example:
"A hydraulic valve assembly with servo-controlled variable orifice 
mechanism that enables precise flow modulation based on system 
pressure feedback"
```

### For Software/AI Features

```
"A method using [algorithm/technique] to [action/task] for 
[problem domain] based on [input type]"

Example:
"A neural network-based anomaly detection system for identifying 
abnormal patterns in industrial time series sensor data without 
labeled training examples"
```

### For Chemical/Material Features

```
"A [material/composition] with [property] for use in [application] 
that provides [benefit]"

Example:
"A polymer stabilization formulation using UV absorbers and hindered 
amine light stabilizers to prevent photodegradation in outdoor 
applications"
```

### For Multi-Feature (Holistic)

```
"A system comprising [F1] integrated with [F2] to achieve [F3]"

Example:
"A compliant gripper using auxetic metamaterial fingers that conform 
to irregular objects through negative Poisson ratio deformation for 
robotic pick-and-place operations"
```

---

## Domain-Specific Examples

### Polymer/Fluorescence Domain

```
"UV fluorescence detection of thermal degradation in polyamide pellets"
"Inline optical inspection system for polymer pellet quality control"
"Spectroscopic measurement of oxidation in thermoplastic materials"
"Real-time process monitoring using luminescence in polymer processing"
"Photoluminescence method for detecting oxidative aging in plastics"
```

### Robotics/Gripper Domain

```
"Compliant gripper using auxetic metamaterial for conformable grasping of irregular objects"
"Pneumatic soft actuator with variable stiffness for robotic manipulation"
"Negative Poisson ratio structure for adaptive gripping mechanism"
"Shape-morphing end effector that conforms to object geometry through material deformation"
"Robotic handling system for delicate or irregularly shaped objects in manufacturing"
```

---

## Result Interpretation

Semantic search returns similarity scores (0.0 to 1.0):

| Score Range | Interpretation | Action |
|-------------|----------------|--------|
| 0.9 - 1.0 | Very high similarity | Likely direct match, review carefully! |
| 0.7 - 0.9 | High similarity | Probably relevant, triage as A or B |
| 0.5 - 0.7 | Moderate similarity | May be relevant, triage as B or C |
| < 0.5 | Low similarity | Likely background, triage as C or skip |

---

## Integration with Keyword Searches

Use semantic search to:

1. **Fill coverage gaps**: After Stage 3, check which features are under-covered
2. **Discover alternative terms**: Find papers that describe the same concept differently
3. **Cross-domain references**: Find related work in adjacent fields
4. **Validate findings**: Confirm keyword search results with semantic similarity

---

## Semantic Query Strategy by Coverage

| Feature Coverage | Semantic Strategy |
|------------------|-------------------|
| NONE (no refs) | 3-4 different gist angles |
| WEAK (1 B-ref) | 2-3 gists + use A-ref titles as queries |
| MODERATE | 1-2 gists to confirm saturation |
| STRONG+ | Optional — may skip or run 1 confirmation query |

---

## Expected Output Format

```markdown
## Semantic Search Results for F1

**Query**: "A hydraulic valve assembly with servo-controlled variable 
orifice mechanism for precise flow modulation"

### Top Similar Documents

1. **Similarity: 0.89** | Triage: A
   - Source: Patent US10234567B2
   - Title: Adaptive Hydraulic Flow Control System
   - Relevance: Describes variable orifice valve with feedback control
   - Features: F1(Y), F2(Y), F3(Y1)

2. **Similarity: 0.76** | Triage: B
   - Source: IEEE Paper 10.1109/TMECH.2021.3056
   - Title: Model Predictive Control for Hydraulic Valves
   - Relevance: Related control approach, different valve type
   - Features: F1(Y1), F2(Y), F3(N)

3. **Similarity: 0.65** | Triage: C
   ...
```

---

## Common Pitfalls

❌ **Boolean syntax**: Don't use AND, OR, NOT
❌ **Too short**: Single words don't provide enough semantic context
❌ **Too long**: Paragraphs dilute the semantic signal
❌ **Off-topic terms**: Adding unrelated context confuses the embedding
❌ **Sending full disclosure**: Keep gists concise and non-confidential
❌ **Skipping semantic search**: Always include 3-5 per cycle!
