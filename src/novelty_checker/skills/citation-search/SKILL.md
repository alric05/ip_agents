---
name: citation-search
description: Citation network analysis to discover related prior art from A-level references
triggers:
  - citation
  - forward citation
  - backward citation
  - citing patent
  - cited by
  - citation network
  - prior art chain
  - patent family
  - diminishing returns
  - vocabulary expansion
---

# Citation Network Analysis

This skill guides you through citation-based discovery — finding related prior art
by following the citation networks of already-discovered A-level references.

## When to Use

- **After Round 1+** when A-level references have been found
- **Diminishing returns** from keyword searches (< 2 net new refs per round)
- **Coverage gaps remain** on core features despite multiple search rounds
- **Vocabulary expansion needed** — citations often use different terminology
- **Technology lineage** — tracing the evolution of an invention area

## When NOT to Use

- No A-level references found yet → do more keyword/semantic searches first
- All core features already at STRONG → citation analysis has diminishing value
- Only B-level references available → results will be less focused

## Prerequisites

- At least **1 A-level reference** must exist from prior search rounds
- Coverage must be below target (< 70% at STRONG, or core features below STRONG)
- Call `get_all_findings()` first to identify available A-refs and gap features

## How to Trigger

Delegate to `citation-researcher` with:
- List of A-ref publication numbers to analyze (max 5)
- Features still needing coverage (with current level)
- Vocabulary discovered so far (for cross-referencing)

## Example Delegation

```
task(
    description="""
    Analyze citation networks for these A-refs:
    - US10234567B2 (A-ref for F1, core feature)
    - EP9876543A1 (A-ref for F3, gap feature at WEAK)

    Features needing coverage: F2 (WEAK), F4 (NONE)
    Known vocabulary: fluorescence, photoluminescence, UV excitation

    Invention features for triage:
    F1: [description]
    F2: [description]
    F3: [description]
    F4: [description]

    Focus on:
    1. Forward citations for newer related work
    2. Backward citations for foundational prior art
    3. New vocabulary terms for keyword expansion
    """,
    subagent_type="citation-researcher"
)
```

## Available Tools

Whenever you construct any Derwent keyword query inside this workflow (e.g.
vocabulary expansion, seed-patent follow-up), always prefer DWPI-enhanced
fields (`NOV=`, `TID=`, `TIT=`, `CTB=`) over generic fields (`TI=`, `AB=`,
`CL=`). See the `patent-search` skill for the full syntax reference.

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `get_patent_citations` | Get forward + backward citations for one patent | Single A-ref analysis |
| `batch_citation_search` | Get citations for multiple patents at once | Multiple A-refs (preferred) |
| `get_patent_details` | Fetch full abstract + full claims + DWPI detailed description for a patent | Shortlisted promising citations; MANDATORY before Feature Matrix grading on any A/B ref |
| `triage_reference` | Assign A/B/C relevance label | Every promising citation |
| `map_features_to_reference` | Map Y/Y1/N per feature | A or B citations only — requires full-text from `get_patent_details` first |
| `think_tool` | Structured reflection | After each analysis batch |
| `save_round_findings` | Persist findings | End of analysis (MANDATORY) |

## Workflow

```
1. RECALL    → get_all_findings() to see existing coverage + A-refs
2. CITE      → batch_citation_search() or get_patent_citations() per A-ref
3. SCAN      → Review citation titles, shortlist top 5-8 candidates
4. FETCH     → get_patent_details() for each shortlisted citation
5. TRIAGE    → triage_reference() for A/B/C label
6. MAP       → map_features_to_reference() for A/B citations
7. REFLECT   → think_tool to assess overall findings
8. PERSIST   → save_round_findings to prevent memory loss
```

## Why Citation Analysis is Powerful

Citations discover patents that use **different vocabulary** for the same concepts:

| Keyword Search Finds | Citation Network Discovers |
|----------------------|---------------------------|
| "fluorescence sensor" | "photoluminescence detector" (synonym in backward citation) |
| "machine learning classifier" | "neural network categorization" (newer forward citation) |
| "polymer membrane" | "thin-film barrier layer" (foundational prior art) |

## Expected Output

The citation-researcher returns **pre-triaged** references:

```markdown
## Citation Analysis Findings

### Summary
- A-refs analyzed: 3
- Total citations scanned: 142
- New references from citations: 8 (A: 3, B: 5)
- Findings saved to: /findings/citations_round_X.md

### References Found via Citations
| Publication # | Source A-ref | Direction | Triage | Features (Y/Y1/N) | Priority Date |
|--------------|-------------|-----------|--------|-------------------|---------------|
| US1234567B2 | US9999999A1 | forward | A | F1:Y, F2:Y1, F3:N | 2021-06-15 |

### Vocabulary Discovery
| Term | Source Patent | Relevance |
|------|--------------|-----------|
| photoluminescence | US1234567 | Synonym for fluorescence |
```

## Limits

- Max **5 A-refs** per citation analysis delegation
- Fetch full content for max **10 citations** total (use triage to prioritize)
- Focus on **gap features** — skip citations for already-STRONG features
- Top **15-20 forward/backward** citations per A-ref (API returns up to 100)

## Decision: Continue Citation Analysis or Move On?

| Situation | Action |
|-----------|--------|
| Found 3+ new A-refs via citations | Save findings, consider another citation round on NEW A-refs |
| Found 0-2 new refs, gaps remain | Switch back to keyword/semantic with new vocabulary |
| All core features at STRONG | Proceed to report generation |
| Already analyzed 10+ A-refs total | Diminishing returns — proceed to report |
