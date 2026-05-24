# Derwent Migration - Implementation Changes

**Date**: March 31, 2026 (updated April 14, 2026 — Innography deactivation)
**Status**: ✅ COMPLETED - Derwent is the sole patent search provider; Innography deactivated
**Fallback**: Innography client file (`innography.py`) retained as reference only — not wired to any tool

---

## Overview

This document details all code changes made to switch from Innography to Derwent as the primary patent keyword search provider.

### What Changed
- ✅ Derwent tools now active by default
- ✅ All search.py wrappers (patent_keyword_search, get_patent_details, get_patent_citations, batch_patent_search, batch_citation_search, citation_chain_search) internally route through Derwent
- ✅ Agent system prompts updated with Derwent syntax
- ✅ Query syntax guidance changed to Derwent format
- ✅ **Innography registry entry removed** (April 14): `INNOGRAPHY_TOOLS` constant and `get_fallback_tools()` function deleted from `src/tools/registry.py` — no way for the agent to pick up Innography tools
- ✅ **Innography client re-exports removed** (April 14): `InnographyClient`, `InnographyConfig`, `patent_keyword_search_tool`, `get_patent_by_number`, `get_patent_citations_tool`, `patent_keyword_search`, `get_patent`, `get_patent_citations`, `convert_patents_to_search_results` removed from `src/tools/clients/__init__.py` and `src/tools/__init__.py` public API
- ✅ **Dead import removed** (April 14): `from src.tools.clients.innography import InnographyClient` removed from `src/tools/search.py` (was no longer referenced after Phase-C migration)

### What Stayed the Same
- ✅ `src/tools/clients/innography.py` file itself retained as reference/reading material
- ✅ No breaking changes to any active code paths
- ✅ If rollback is needed, re-add the imports and restore `INNOGRAPHY_TOOLS` from git history

### Response Cleanup (follow-up)

After the initial Innography → Derwent migration, we discovered that Derwent's
raw responses contained XML namespace markup, trailing comma padding, and
duplicate language variants that leaked into agent-facing data.

A response cleanup layer was added to `src/tools/clients/derwent.py` to
normalize these artifacts. See
[DERWENT_RESPONSE_CLEANUP_PLAN.md](DERWENT_RESPONSE_CLEANUP_PLAN.md) for the
full problem catalog, design, and verification approach.

**Summary of fixes:**
- Strip `<tsip:…>`, `<tsxm:…>`, `<b>`, `<ul>`, `<li>` markup from text fields
- Normalize DWPI `"None given."` placeholder → empty string
- Strip trailing `,,,,` padding from single-valued fields (assignee)
- Split + clean joined values into proper lists (inventors)
- Prefer English (`lang="en"`) when Derwent returns multiple language variants
- Prefer correct form (`orig` for abstract, `dwpi` for novelty) when multiple forms are returned
- Trimmed default `return_fields` — dropped `dtd` (detailed description) and
  `cl` (full claims) to reduce payload noise; `cl1` (first claim) retained

**Verification:** 33 new unit tests + 2 new real-API invariant tests in
`tests/test_derwent_migration.py` assert the invariants at both the raw-dict
and rendered-markdown layers.

---

## Files Modified

### 1. `src/tools/registry.py`

**Location**: Patent tool registry and selection logic

#### Change 1.1: Added INNOGRAPHY_TOOLS List

```python
# LEGACY: Innography tools (kept for fallback/reference only)
INNOGRAPHY_TOOLS: list[BaseTool] = [
    patent_keyword_search,
    batch_patent_search,
    get_patent_citations,
]
```

**Purpose**: Clearly mark Innography tools as legacy while preserving functionality

**Location**: Before SEARCH_TOOLS definition

#### Change 1.2: Updated `get_all_tools()` Function

**Before:**
```python
def get_all_tools() -> list[BaseTool]:
    """Get all available tools for the novelty checker agent."""
    tools = (
        SEARCH_TOOLS              # ← Innography tools
        + BATCH_SEARCH_TOOLS
        + CONTENT_TOOLS
        + CITATION_TOOLS
        + DERWENT_TOOLS
        + LOGGING_TOOLS
        + ANALYSIS_TOOLS
        + REFLECTION_TOOLS
        + FINDINGS_PERSISTENCE_TOOLS
    )
    # ...
```

**After:**
```python
def get_all_tools() -> list[BaseTool]:
    """Get all available tools for the novelty checker agent.

    Returns:
        Complete list of all tools (NPL tools excluded when enable_npl_search=False)
        NOTE: Derwent is now the primary patent search provider. Innography tools
              are NOT included by default (kept in SEARCH_TOOLS for fallback/reference).
    """
    tools = (
        DERWENT_TOOLS                # PRIMARY: Derwent patent search
        + BATCH_SEARCH_TOOLS
        + CONTENT_TOOLS
        + CITATION_TOOLS
        + LOGGING_TOOLS
        + ANALYSIS_TOOLS
        + REFLECTION_TOOLS
        + FINDINGS_PERSISTENCE_TOOLS
    )
    # ...
```

**Impact**: All agents now use Derwent for patent searches

#### Change 1.3: Added `get_fallback_tools()` Function

**New Function:**
```python
def get_fallback_tools() -> list[BaseTool]:
    """Get tools with Innography (legacy fallback) instead of Derwent.
    
    Use this only if Derwent is unavailable.
    
    Returns:
        Complete tool list with Innography patent search instead of Derwent
    """
    tools = (
        INNOGRAPHY_TOOLS             # FALLBACK: Use Innography instead
        + BATCH_SEARCH_TOOLS
        + CONTENT_TOOLS
        + CITATION_TOOLS
        + LOGGING_TOOLS
        + ANALYSIS_TOOLS
        + REFLECTION_TOOLS
        + FINDINGS_PERSISTENCE_TOOLS
    )
    if not is_npl_enabled():
        tools = [t for t in tools if t.name not in NPL_TOOL_NAMES]
    return tools
```

**Purpose**: Provides emergency fallback path to Innography if needed

**When to Use**: Only if Derwent API becomes unavailable

---

### 2. `src/novelty_checker/subagents.yaml`

**Location**: Agent configurations and system prompts

#### Change 2.1: Updated Agent Description

**Before:**
```yaml
patent-researcher:
  description: "Execute Innography patent searches with proper @(field) syntax. Returns references with feature coverage analysis."
```

**After:**
```yaml
patent-researcher:
  description: "Execute Derwent patent searches with proper field=value syntax. Returns references with feature coverage analysis."
```

#### Change 2.2: Updated Query Syntax Instructions

**Before:**
```yaml
## Query Syntax (CRITICAL!)
Use @(field) syntax: @(dwpi_title,dwpi_abstract) (keyword NEAR/5 term)
NO SPACES in field lists!
```

**After:**
```yaml
## Query Syntax (CRITICAL!)
Use field=value syntax: ti=keyword, ab=term, (ti=soft OR ab=soft), in=inventor
Boolean operators (AND, OR, NOT) work as expected. NO SPACES in field lists!
```

**Key Differences**:
- Innography: `@(dwpi_title,dwpi_abstract)` → Derwent: `(ti=term OR ab=term)`
- Innography: `@(dwpi_novelty)` → Derwent: `nov=term`
- Innography: `@inventor` → Derwent: `in=inventor`
- Innography: `NEAR/5` → Derwent: `NEAR` (contextual distance)

#### Change 2.3: Updated Search Tool Instructions

**Before:**
```yaml
│ 1. SEARCH: Call patent_keyword_search or batch_patent_search │
```

**After:**
```yaml
│ 1. SEARCH: Call search_derwent_patents_fld              │
```

#### Change 2.4: Updated Gap-Filling Query Examples

**Before:**
```yaml
### Gap-Filling Queries for Next Round
- F2: Try "@(dwpi_novelty) [specific terms]"
```

**After:**
```yaml
### Gap-Filling Queries for Next Round
- F2: Try "nov=[specific terms]" or "ab=[new terms]"
```

#### Change 2.5: Updated Tool Assignments

**Before:**
```yaml
  tools:
    - patent_keyword_search
    - batch_patent_search
    - batch_citation_search
    - think_tool
    - save_round_findings
    - get_all_findings
    - get_coverage_gaps
```

**After:**
```yaml
  tools:
    - search_derwent_patents_fld
    - search_derwent_patents
    - search_derwent_patents_advanced
    - think_tool
    - save_round_findings
    - get_all_findings
    - get_coverage_gaps
```

**Tool Changes**:
| Old (Innography) | New (Derwent) | Purpose |
|------------------|---------------|---------|
| `patent_keyword_search` | `search_derwent_patents_fld` | Primary search |
| `batch_patent_search` | Covered by `search_derwent_patents_fld` | Not needed separately |
| `batch_citation_search` | Removed | Derwent doesn't have citation API |

---

## Derwent Tools Overview

### Available Derwent Tools

All three tools are now available to the patent-researcher agent:

#### 1. `search_derwent_patents_fld()`
Full-text search using Derwent FLD (field-oriented) syntax.

**Usage:**
```python
search_derwent_patents_fld(
    query="ti=motor",
    collections="derwentmatlat",
    size=20
)
```

**Syntax Examples:**
- `ti=motor` - Title search
- `ab=gripper` - Abstract search
- `(ti=soft OR ab=soft)` - Multiple fields
- `ti=motor AND in=Smith` - Combined search
- `nov=improved` - Novelty statement search

#### 2. `search_derwent_patents()`
Patent lookup by publication numbers.

**Usage:**
```python
search_derwent_patents(
    patent_ids="US1234567B2, EP3411222B1",
    max_results=2
)
```

#### 3. `search_derwent_patents_advanced()`
Advanced search with customizable fields and pagination.

**Usage:**
```python
search_derwent_patents_advanced(
    patent_ids="US1234567B2",
    return_fields="PN,TI,AB,IN,AN",
    offset=0,
    size=50
)
```

---

## Query Syntax Migration Guide

### Common Field Translations

| Innography | Derwent | Example |
|-----------|---------|---------|
| `@title` | `ti=` | `ti=motor` |
| `@abstract` | `ab=` | `ab=gripper` |
| `@claims` | `cl=` | `cl=gear` |
| `@dwpi_title` | `ti=` | `ti=semiconductor` |
| `@dwpi_novelty` | `nov=` | `nov=new` |
| `@dwpi_advantage` | `adv=` | `adv=efficient` |
| `@inventor` | `in=` | `in=Smith` |
| `@assignee` | `an=` | `an=Sony` |
| `@ipc` | `ipc=` | `ipc=H01M` |

### Boolean Operators (Unchanged)
```
motor AND actuator      # Both required
motor OR actuator       # Either term
motor NOT spring        # Exclude spring
(A OR B) AND C          # Grouping
```

### Proximity (Different Syntax)
| Innography | Derwent |
|-----------|---------|
| `motor NEAR/5 actuator` | `motor NEAR actuator` |
| `motor ADJ/2 actuator` | `motor AND actuator` |
| `"exact phrase"` | `"exact phrase"` |

### Example Query Conversions

```
Innography Query                     Derwent Query
────────────────────────────────────────────────────────
@(title,abstract) motor             (ti=motor OR ab=motor)

@(dwpi_title) gripper               ti=gripper

@(title) (soft NEAR/5 gripper)      ti=(soft NEAR gripper)

@(dwpi_novelty) improved             nov=improved

@inventor Smith AND @title motor    in=Smith AND ti=motor
```

---

## Impact Assessment

### What Works the Same
- ✅ Other patent search databases (Web of Science, NGSP)
- ✅ Citation analysis tools (not used in Derwent yet)
- ✅ Triage and coverage evaluation
- ✅ Findings persistence
- ✅ Reflection and iterate loop
- ✅ Result formatting and reporting

### What's Different
- ⚠️ Query syntax (now Derwent format)
- ⚠️ Search tool names in agent configuration
- ⚠️ System prompt instructions for agents
- ⚠️ No backward/forward citation support (Derwent API limitation)

### What's Removed
- ❌ `batch_patent_search` (Derwent doesn't need separate batch tool)
- ❌ `batch_citation_search` (Derwent doesn't have citation API)
- ❌ `citation_chain_search` (covered by other tools)

---

## Testing Changes

### Verify Derwent is Active

```bash
python -c "from src.tools.registry import get_all_tools; tools = get_all_tools(); derwent_tools = [t.name for t in tools if 'derwent' in t.name]; print(f'Derwent tools active: {derwent_tools}')"
```

Expected output:
```
Derwent tools active: ['search_derwent_patents_fld', 'search_derwent_patents', 'search_derwent_patents_advanced']
```

### Test Agent Configuration

```bash
python -c "import yaml; config = yaml.safe_load(open('src/novelty_checker/subagents.yaml')); print('Patent researcher tools:', config['patent-researcher']['tools'])"
```

Expected output:
```
Patent researcher tools: ['search_derwent_patents_fld', 'search_derwent_patents', 'search_derwent_patents_advanced', 'think_tool', ...]
```

### Test Derwent Search

```bash
python -c "from src.tools.clients.derwent import search_derwent_patents_fld; result = search_derwent_patents_fld(query='ti=motor', size=5); print(result[:500])"
```

---

## Emergency Fallback

### If Derwent API Fails

To quickly revert to Innography:

**Edit**: `src/tools/registry.py`

Find the `get_all_tools()` function and change it to:

```python
def get_all_tools() -> list[BaseTool]:
    """Get all tools - using Innography fallback."""
    return get_fallback_tools()
```

Then restart the agent:

```bash
langgraph dev
```

### Restore to Derwent

Revert the change:

```python
def get_all_tools() -> list[BaseTool]:
    """Get all tools - Derwent is now primary patent search."""
    tools = (
        DERWENT_TOOLS                # ← Back to Derwent
        + BATCH_SEARCH_TOOLS
        # ... rest of tools
    )
    # ...
```

Restart: `langgraph dev`

---

## Code Preservation

All Innography code remains intact and functional:

- `src/tools/clients/innography.py` - Full client implementation
- `src/tools/search.py` - `patent_keyword_search()`, `batch_patent_search()`, etc.
- `INNOGRAPHY_TOOLS` list in registry - All tools preserved

The implementation is **reversible** - no code has been deleted, only reorganized.

---

## Documentation Updates

Updated references to Derwent:
- ✅ [docs/SWITCHING_INNOGRAPHY_TO_DERWENT.md](SWITCHING_INNOGRAPHY_TO_DERWENT.md) - Primary integration guide
- ✅ [docs/DERWENTAPI_CHANGES.md](DERWENTAPI_CHANGES.md) - Derwent API details
- ✅ This document - Implementation change log

Innography documentation preserved:
- ✅ [src/novelty_checker/skills/patent-search/SKILL.md](../src/novelty_checker/skills/patent-search/SKILL.md) - Still references Innography syntax (marked as legacy)

---

## Summary of Changes

| Component | Change | Status |
|-----------|--------|--------|
| Default patent search | Innography → Derwent | ✅ Done |
| Registry organization | Added INNOGRAPHY_TOOLS list | ✅ Done |
| Fallback function | Added `get_fallback_tools()` | ✅ Done |
| Agent query syntax | `@(field)` → `field=value` | ✅ Done |
| Tool assignments | Updated to Derwent tools | ✅ Done |
| System prompts | Updated with Derwent syntax | ✅ Done |
| Code preservation | Innography remains intact | ✅ Done |

---

## Related Documentation

- [DERWENTAPI_CHANGES.md](DERWENTAPI_CHANGES.md) - Full Derwent API reference
- [SWITCHING_INNOGRAPHY_TO_DERWENT.md](SWITCHING_INNOGRAPHY_TO_DERWENT.md) - Integration guide
- [../ARCHITECTURE.md](ARCHITECTURE.md) - System architecture overview
