# Test Set Requirements Specification

> **Purpose:** Define the evaluation test set for the Novelty Checker Agent — size, composition, difficulty bands, input/output formats, SME collection modes, and quality targets.
>
> **Key assumption:** SMEs provide invention disclosures from their own real or past cases. They already know the prior art landscape for these inventions and submit ground truth alongside the disclosure. We then run the agent on their disclosures and compare.
>
> **Scope — Current Evaluation Round:** Mechanical engineering domain only. Sub-domain diversity within mechanical is encouraged (gear systems, actuators, mechanisms, thermal, fluid, MEMS, etc.).

---

## 1. Test Set Size & Rationale

**Target: 30 invention cases collected from SMEs**

Each SME submits cases from their own real or past novelty assessments. They provide the invention disclosure and the ground truth (features, references, verdict, search strategy) because they already know the prior art landscape for their own cases.

| Difficulty Band | Target Count | Purpose |
|----------------|-------------|---------|
| Easy | 8 | Baseline regression, agent calibration |
| Medium | 14 | Primary evaluation corpus — statistical power for per-metric significance |
| Hard | 8 | Stress testing, edge-case discovery, failure-mode analysis |

**Why 30?**
- With 3 difficulty bands of 8–14 cases each, we get meaningful variance for per-band metrics.
- 3–4 SMEs each submit ~8–10 cases, with 5 cases reviewed by a second SME for inter-rater reliability.
- Expanding beyond 30 offers diminishing returns until the agent is more mature; can be extended in later evaluation rounds.

**SME Contribution Targets (3–4 SMEs):**

| SME | Cases Submitted | Cases Also Reviewed by Another SME | Total Effort |
|-----|----------------|-----------------------------------|-------------|
| SME-A | ~10 | 2 of their cases reviewed by SME-B | ~10 submissions + 2 Mode 2 reviews of others' cases |
| SME-B | ~10 | 2 of their cases reviewed by SME-A | ~10 submissions + 2 Mode 2 reviews of others' cases |
| SME-C | ~10 | 1 of their cases reviewed by SME-B | ~10 submissions + 1 Mode 2 review of others' cases |
| SME-D (if available) | Adjudicator for disagreements | All overlap cases | 5 adjudications |

---

## 2. Domain Distribution (Mechanical Engineering)

This evaluation round focuses on **mechanical engineering**. Since SMEs submit their own cases, we cannot prescribe exact sub-domain counts. Instead, we provide **target ranges** and ask SMEs to aim for sub-domain diversity within mechanical engineering.

| Mechanical Sub-Domain | Target Count | Example Inventions | CPC/IPC Range |
|----------------------|-------------|-------------------|---------------|
| Gear Systems & Power Transmission | 4–8 | Worm gears, planetary drives, harmonic reducers, CVTs | F16H |
| Actuators & Mechanisms | 4–8 | Linkages, cam mechanisms, compliant mechanisms, micro-actuators | F16K, B25J, F15B |
| Structural & Packaging | 3–6 | Housings, brackets, thin-profile assemblies, fastening systems | F16B, F16M |
| Fluid & Pneumatic Systems | 2–5 | Valves, pumps, hydraulic circuits, sealing systems | F16J, F04C, F15B |
| Thermal Management | 2–5 | Heat exchangers, cooling channels, thermal interface materials | F28D, F28F, H05K |
| MEMS & Micro-Mechanisms | 2–5 | Micro-gears, micro-actuators, precision positioning stages | B81B, G02B |
| Cross-Mechanical (hybrid) | 2–4 | Mechanical + materials, mechanical + thermal, electromechanical integration | Mixed |

**Guidance to SMEs when selecting cases to submit:**
- Aim for sub-domain diversity — avoid submitting 10 cases all from the same mechanical area (e.g., all gear systems)
- Include at least 1–2 cases from a sub-domain different from your primary specialisation
- Cross-mechanical or hybrid cases (e.g., mechanism + thermal) are especially valuable for testing the agent's limits
- We will track sub-domain distribution as cases arrive and request specific areas if gaps emerge

---

## 3. Difficulty Band Definitions

When submitting a case, the SME assigns the difficulty band based on the criteria below. This is a self-assessment — the SME knows from their own experience how hard the search was.

### 3.1 Easy (E-band)

| Criterion | Specification |
|-----------|--------------|
| Prior art density | >100 patents in the space |
| Vocabulary | Standard, well-indexed DWPI terminology |
| Search complexity | Single-database keyword search is sufficient |
| Feature count | 3–4 features, all use standard terms |
| Expected agent outcome | Finds blocking X-category or near-X references within 2 rounds |
| SME time estimate | 2–3 hours per case |
| Agent expected runtime | 15–25 minutes, 2 search rounds typical |
| Example | Improved bicycle helmet ventilation system |

**What makes a case Easy:**
- Inventor's terminology aligns with standard patent classification language
- The core concept has been patented many times before (well-studied field)
- A simple Boolean search on Innography returns relevant A-refs in the first query
- The novelty answer is clearly "not novel" — strong prior art exists

### 3.2 Medium (M-band)

| Criterion | Specification |
|-----------|--------------|
| Prior art density | 20–100 patents in the space |
| Vocabulary | Mix of standard and non-standard terms; agent must discover synonyms |
| Search complexity | Requires multi-database search (patent + NPL + semantic) |
| Feature count | 4–6 features, some with non-standard vocabulary |
| Expected agent outcome | Finds A-refs covering 3–4 of 5 features; specific combination may be novel |
| SME time estimate | 4–6 hours per case |
| Agent expected runtime | 25–45 minutes, 3 search rounds typical |
| Example | Dual-worm gear transmission for smartphone cameras (existing test case) |

**What makes a case Medium:**
- Prior art exists but is scattered across databases and classification codes
- Some features require vocabulary discovery (synonyms, alternate terms)
- The answer is typically "partially novel" — the combination is new even if individual features are known
- Citation-chain search adds value (Round 2+ finds additional relevant references)

### 3.3 Hard (H-band)

| Criterion | Specification |
|-----------|--------------|
| Prior art density | <20 patents in the immediate space |
| Vocabulary | Inventor-coined terms, emerging/frontier terminology |
| Search complexity | Requires semantic search + cross-domain analogy detection |
| Feature count | 5–7 features, some crossing domain boundaries |
| Expected agent outcome | Struggles to find A-refs; closest references are analogues from adjacent fields |
| SME time estimate | 6–10 hours per case |
| Agent expected runtime | 45–75 minutes, 4–5 search rounds (may hit max iterations) |
| Example | Shape-memory alloy compliant gripper with embedded strain-sensing lattice for sub-millimetre assembly |

**What makes a case Hard:**
- Combines concepts from 2+ mechanical sub-domains (e.g., compliant mechanisms + smart materials + micro-assembly)
- Inventor-coined terminology not yet in DWPI vocabulary or IPC classification
- Closest prior art is analogous art from adjacent mechanical areas (requires creative search strategies)
- The novelty answer is typically "novel" or close to it — truly new concept
- Semantic search is critical because keyword search fails on non-standard vocabulary

---

## 4. Input Format: Disclosure Text Specification

Each SME submits an invention disclosure from their own real or past cases. The disclosure is what gets fed to the agent. SMEs should follow this format to ensure consistency across submissions.

### 4.1 Disclosure Template

```markdown
---
case_id: "TST-{SUBDOMAIN}-{SEQ:03d}"
domain: "Gear Systems | Actuators & Mechanisms | Structural & Packaging | Fluid & Pneumatic | Thermal Management | MEMS & Micro-Mechanisms | Cross-Mechanical"
difficulty: "easy | medium | hard"
source: "synthetic | client_redacted"
created_by: "{author_name}"
created_date: "YYYY-MM-DD"
---

# Invention Disclosure

## Title
[Descriptive title, 10–20 words]

## Technical Field
[1–2 sentences identifying the IPC/CPC area and application domain]

## Background / Problem Statement
[2–4 sentences describing the problem being solved. Include context about
existing solutions and why they are insufficient. Do NOT include patent
numbers or prior art references — the agent and SME must find these.]

## Proposed Solution
[3–6 sentences describing the invention. Must include enough specificity
for decomposition into 3–7 features. Describe key components, materials,
mechanisms, or algorithms. Be concrete — avoid vague language like
"an improved method" without describing what is improved.]

## Key Technical Aspects
1. [Aspect 1 — what the inventor considers most novel]
2. [Aspect 2]
3. [Aspect 3]
... (up to 7 aspects)

## Optional: Inventor's Prior Art Awareness
[Any references the inventor is already aware of. May be empty.
If provided, these should NOT be treated as the complete prior art.]

## Optional: Known Constraints
[Physical, regulatory, or market constraints relevant to the search.
E.g., "must fit within 10mm", "FDA-cleared materials only",
"operating temperature range -40 to +85C"]
```

### 4.2 Disclosure Constraints

| Constraint | Requirement |
|-----------|-------------|
| Length | 200–800 words (matching real customer submissions) |
| Language | English |
| Must NOT contain | Patent numbers, IPC/CPC codes, search strategies, or novelty conclusions in the disclosure itself |
| Must NOT embed answers | No "this is novel because..." or "the closest prior art is..." — the disclosure should read as if the agent has never seen this invention before |
| Must be self-contained | Reader should understand the invention without external documents |
| Specificity | Enough detail to decompose into 3–7 searchable features |
| Redaction | If the case is from a real client engagement, redact client-identifying information. Use `source: "client_redacted"` in the header. |

### 4.3 Case ID Convention

Format: `TST-{SUBDOMAIN}-{SEQ:03d}`

| Sub-Domain Code | Mechanical Sub-Domain |
|----------------|----------------------|
| GEAR | Gear Systems & Power Transmission |
| ACTU | Actuators & Mechanisms |
| STRU | Structural & Packaging |
| FLUI | Fluid & Pneumatic Systems |
| THRM | Thermal Management |
| MEMS | MEMS & Micro-Mechanisms |
| XMEC | Cross-Mechanical (hybrid) |

Examples: `TST-GEAR-001`, `TST-ACTU-003`, `TST-XMEC-002`

---

## 5. Expected Outputs

### 5.1 Agent Output (produced automatically by `eval_runner.py`)

For each case, the agent produces a complete session directory:

| Artifact | File | Description |
|----------|------|-------------|
| Scope | `scope.md` | Confirmed invention scope with clarifications |
| Features | `features.md` | Feature table: ID, Name, Description, Core?, Keywords |
| Per-round findings | `findings/{type}_round_{N}.md` | Patent, NPL, semantic search results per round |
| Findings accumulator | `findings_accumulator.json` | Structured JSON: coverage per feature per round |
| References | `references.md` | Consolidated reference list with A/B/C triage labels |
| Final report | `final_report.md` | 11-section novelty assessment report |
| Telemetry | `telemetry.json` | Tool call timing, success rates, round counts |
| Patent statistics | `patent_statistics.md` | Discovery-to-report funnel |

### 5.2 SME Ground Truth (produced per case)

| Artifact | File | Description |
|----------|------|-------------|
| Full ground truth | `gt_case.json` | Main structured file (see SME template) |
| Expected scope | `gt_scope.md` | What the scope should look like |
| Expected features | `gt_features.json` | Feature array with keywords and types |
| Expected references | `gt_references.json` | Reference array with triage + coverage map |
| Search strategy | `gt_search_strategy.md` | Queries, databases, approach narrative |
| Verdict | `gt_verdict.json` | novel/partial/not_novel + per-feature risk |

### 5.3 Comparison Dimensions

The following metrics are computed by comparing agent output to SME ground truth:

| Metric Category | Metric | How Computed |
|----------------|--------|-------------|
| **Feature Extraction** | Feature recall | `|agent_features ∩ gt_features| / |gt_features|` |
| | Feature precision | `|agent_features ∩ gt_features| / |agent_features|` |
| | Core label accuracy | Agreement on `is_core` per matched feature |
| **Search Completeness** | Reference recall | `|agent_AB_refs ∩ gt_AB_refs| / |gt_AB_refs|` |
| | Reference precision | Correctly triaged refs / total agent A+B refs |
| | Database diversity | Count of distinct databases used by agent |
| **Triage Accuracy** | Triage agreement | Cohen's kappa on A/B/C labels for shared refs |
| | A-ref F1 score | Harmonic mean of A-ref precision and recall |
| **Feature Mapping** | Coverage accuracy | Cell-level agreement on Y/Y1/N matrix |
| **Report Quality** | Section completeness | Sections present out of 11 |
| | Verdict agreement | Exact match on novel/partial/not_novel |
| | Risk alignment | Per-feature risk level agreement |
| **Efficiency** | Time ratio | `agent_time / sme_time` |
| | Query efficiency | `unique_refs_found / total_queries` |

---

## 6. SME Ground Truth — Two Collection Modes

### 6.1 Mode 1: SME Submits Case + Ground Truth (Primary Mode)

The SME submits an invention from their own real or past work, along with their complete ground truth assessment. Since it's their own case, they already know the prior art landscape — they are documenting what they already found.

**Protocol:**
1. SME selects a case from their own past novelty assessments
2. SME writes the invention disclosure in the standard template format (redacting client info if needed)
3. SME fills in the ground truth form: features, references, search strategy, verdict
4. SME tracks wall-clock time per stage (time to document, not time of original search — but note the original search time if available)
5. SME submits the disclosure + ground truth form together

**This is the primary collection mode — all 30 cases start here.**

**SME requirements:**
- Minimum 3 years patent search experience
- Proficiency with Innography and Web of Science
- Willing to document their past work in our structured format

### 6.2 Mode 2: SME Reviews Agent Output (Optional Second Pass)

After we receive the SME's submission, we run the agent on their disclosure. We then send the agent's output back to the **same SME** for error annotation.

**Protocol:**
1. We run the agent on the SME's disclosure via `eval_runner.py` (auto-approved gates)
2. We send the agent's full session output back to the SME: scope, features, findings, final report
3. SME reviews and annotates using the [Mode 2 Review Form](SME_MODE2_REVIEW_FORM.md):
   - **Scope:** Did the agent understand the invention correctly?
   - **Features:** Did the agent identify the right features? Any missed or hallucinated?
   - **References:** Did the agent find the same blocking prior art? Any wrong triage labels?
   - **Missing references:** What important references did the agent miss? What queries would have found them?
   - **Report quality:** Any hallucinated facts, wrong coverage percentages, or misleading conclusions?
4. SME fills in the Mode 2 Review Form ([SME_MODE2_REVIEW_FORM.md](SME_MODE2_REVIEW_FORM.md)) — see [Mode 2 instructions](SME_MODE2_REVIEW_INSTRUCTIONS.md)

**Case selection for Mode 2:** Not all 30 cases need a Mode 2 pass. Prioritize:
- All hard-band cases (most informative for understanding agent failures)
- A sample of medium-band cases
- Target: ~15–20 cases get Mode 2 review

**Advantage:** Mode 2 is fast (1–3 hours) because the SME already knows the case. It reveals *specific* agent failure modes: what it misses, what it gets wrong, and where it hallucinates.

### 6.3 Cross-Validation (Overlap Cases)

For 5 cases, a **second SME** (not the original submitter) independently fills in the ground truth form based on the disclosure alone. This measures inter-rater reliability:

| Purpose | What It Measures |
|---------|-----------------|
| SME-vs-SME agreement | Are the ground truth standards being applied consistently? |
| Baseline quality | How much do two experienced searchers agree on the same invention? |

### 6.4 Quality Control Targets

| Metric | Measurement | Target | Action If Below Target |
|--------|------------|--------|----------------------|
| Feature set agreement | Jaccard similarity of feature sets | >= 0.70 | Recalibration session |
| Reference overlap | Jaccard similarity of A+B ref sets | >= 0.50 | Review search strategy differences |
| Triage agreement | Cohen's kappa on A/B/C labels | >= 0.60 | Tighten A/B/C definitions |
| Y/Y1/N matrix agreement | Cell-level exact match rate | >= 0.75 | Add worked examples to template |
| Verdict agreement | Exact match on novel/partial/not_novel | >= 0.80 | Adjudication by senior reviewer |

**Alignment session (recommended before data collection begins):**
1. All SMEs review the instructions document (triage definitions, Y/Y1/N standards, core feature criteria)
2. Discuss any ambiguities or edge cases as a group
3. Optionally, one SME submits a case early as a pilot; others review the output to calibrate expectations
4. Document any team agreements that clarify or refine the standards

---

## 7. Historical Search Log Compatibility

### 7.1 Manual Boolean Workflow vs. Agent Approach

If historical search logs become available in future, here is how the two approaches compare:

| Aspect | Manual SME Boolean Workflow | Agent Semantic-Augmented Approach |
|--------|---------------------------|----------------------------------|
| Feature decomposition | Implicit (in searcher's head) | Explicit F1–Fn with keywords, types |
| Query construction | Human-crafted Boolean strings | Auto-generated per-feature queries |
| Databases | Innography + WoS (manual entry) | Innography + WoS + NGSP (semantic) |
| Synonym discovery | Classification browsing, thesaurus | Semantic search vocabulary feedback loop |
| Citation analysis | Manual forward/backward | Automated citation-researcher subagent |
| Stopping criterion | Subjective ("enough references found") | Coverage % threshold (70% / STRONG) |
| Output format | Word/PDF, unstructured | Structured markdown, Feature Matrix table |
| Time per case | 4–10 hours | 15–75 minutes |
| Triage system | Varies (star ratings, X/Y categories, relevant/not) | Standardized A/B/C labels |

### 7.2 Format Bridging (for future historical data integration)

If legacy search exports become available:

1. **Extract references** from CSV/XLSX exports, normalize publication numbers
2. **Map legacy triage** to A/B/C labels (e.g., 3-star→A, 2-star→B, 1-star→C)
3. **Reconstruct feature coverage** — SME manually annotates Y/Y1/N per feature (most labor-intensive step)
4. **Extract search queries** from search history exports
5. **Produce `gt_case.json`** with `source: "historical"`

### 7.3 Overlap Metrics (when both human and agent output exist)

| Check | What It Tells Us |
|-------|-----------------|
| `Jaccard(agent_refs, sme_refs)` at family level | Overall search agreement |
| `agent_refs − sme_refs` (A+B only) | What semantic search uniquely adds |
| `sme_refs − agent_refs` (A+B only) | What the agent misses |
| Vocabulary comparison | Whether the agent discovers the same synonyms |

**Caveats for future reference:**
- Use patent-family-level deduplication (US and EP publications of the same family should match)
- Account for date-cutoff differences (if legacy search was done years ago)
- Exclude references from databases the agent cannot access (Google Patents, Orbit) from recall calculations

---

## 8. Timeline & Effort Estimate

### 8.1 Phased Execution

| Phase | Week | Activities | Deliverables |
|-------|------|-----------|-------------|
| **A: Setup** | 1 | Finalize templates; share instructions with SMEs; conduct alignment session | Aligned SME team, templates distributed |
| **B: SME Submissions** | 2–4 | SMEs submit cases (disclosure + ground truth form); we run agent on each as it arrives | 30 disclosure + ground truth packages; 30 agent sessions |
| **C: Mode 2 Reviews** | 5–6 | Send agent output back to SMEs for ~15–20 selected cases; SMEs annotate errors | Mode 2 annotations for selected cases |
| **D: Validation** | 7 | Compute inter-rater reliability on 5 overlap cases; adjudicate disagreements; validate all data; aggregate metrics | Final validated dataset of 30 cases |

### 8.2 Effort Breakdown

| Activity | Per Case | Total |
|----------|----------|-------|
| SME: write disclosure + fill ground truth form (Mode 1) | 2–4 hours | 60–120 hours (30 cases) |
| SME: review agent output + annotate errors (Mode 2) | 1–3 hours | 15–60 hours (~15–20 cases) |
| Engineering: run agent on disclosures | 0.5 hours | 15 hours |
| Engineering: send output back, collect Mode 2 forms | 0.25 hours | 5–8 hours |
| Adjudication (5 overlap cases) | 2 hours | 10 hours |
| Alignment session | — | 2–4 hours (one-time) |
| Template/schema creation | — | 16 hours (one-time, already done) |
| **Total** | | **~90–195 SME hours + ~30 engineering hours** |

### 8.3 SME Workload Distribution (3 SMEs)

| SME | Cases Submitted (Mode 1) | Mode 2 Reviews | Overlap Reviews | Estimated Hours |
|-----|-------------------------|---------------|----------------|----------------|
| SME-A | 10 | 5–7 of their own cases | 2 of SME-B's cases | 35–60 |
| SME-B | 10 | 5–7 of their own cases | 2 of SME-A's cases | 35–60 |
| SME-C | 10 | 5–6 of their own cases | 1 of SME-B's cases | 30–55 |

---

## Appendix A: Per-Case Directory Structure

Each evaluated case produces:

```
evals/golden_datasets/cases/{case_id}/
    disclosure.md                # Input invention disclosure
    gt_case.json                 # Main ground truth (full schema)
    gt_scope.md                  # Expected scope output
    gt_features.json             # Expected features array
    gt_references.json           # Expected references with triage + coverage
    gt_search_strategy.md        # Search strategy narrative
    gt_verdict.json              # Final verdict + per-feature risk
    agent_session/               # Agent output (from eval_runner)
        scope.md
        features.md
        findings/
        references.md
        final_report.md
        telemetry.json
        findings_accumulator.json
        patent_statistics.md
```

## Appendix B: Acceptance Criteria for This Specification

- [ ] 30 cases received from SMEs (disclosure + ground truth form)
- [ ] Sub-domain distribution covers at least 3 mechanical sub-domains
- [ ] Difficulty distribution: at least 5 easy, 10 medium, 5 hard
- [ ] Alignment session completed with all participating SMEs
- [ ] Agent has been run on all 30 cases via `eval_runner.py`
- [ ] Mode 2 annotations received for 15–20 cases
- [ ] Inter-rater reliability computed on 5 overlap cases and meets quality targets
- [ ] All ground truth data validated and organized into `evals/golden_datasets/cases/`
