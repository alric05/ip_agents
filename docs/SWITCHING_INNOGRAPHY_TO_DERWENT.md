# Derwent Patent Search - Primary Implementation

This guide explains how Clarivate Derwent patent database is now the **primary** patent search provider, replacing Innography in active workflows.

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Derwent Tools](#derwent-tools)
4. [Agent Configuration](#agent-configuration)
5. [Derwent Query Syntax](#derwent-query-syntax)
6. [Usage Examples](#usage-examples)
7. [Innography Fallback](#innography-fallback)

---

## Overview

### New Integration Model
- **Derwent**: Primary patent keyword search (NEW DEFAULT)
- **Innography**: Legacy tool set (kept intact, not actively used)
- **Independence**: Distinct syntax, no conversion needed
- **Active Use**: Agents use Derwent tools by default

### Key Facts
- **Derwent** is now the primary patent search provider
- **Innography** code remains intact for reference/fallback
- **Query Syntax Difference**: Derwent uses `field=value` syntax (e.g., `ti=motor`)
- **No Message Queue Changes**: Direct tool invocation, no conversion layer needed

---

## Architecture

### Parallel Tool Sets

```
Patent Search Tools (Active Use)
├── Derwent (Now Primary)
│   ├── search_derwent_patents()         → DerwentClient (ID-based)
│   ├── search_derwent_patents_fld()     → DerwentClient (Query-based FLD)
│   └── search_derwent_patents_advanced() → DerwentClient (Advanced)
│
└── Innography (Legacy - Left Intact)
    ├── patent_keyword_search()         → InnographyClient (not used)
    ├── batch_patent_search()           → InnographyClient (not used)
    ├── get_patent_details()            → InnographyClient (not used)
    ├── get_patent_citations()          → InnographyClient (not used)
    ├── batch_citation_search()         → InnographyClient (not used)
    └── citation_chain_search()         → InnographyClient (not used)
```

### Independence & Switching
- **Derwent** and **Innography** are completely independent implementations
- Default behavior uses **Derwent** tools exclusively
- **Innography** can be restored if needed (code remains functional)
- No query conversion or compatibility layer

---

## Current Integration Points

### What Changed
- **Tool Registry**: Derwent tools are now the default in `get_all_tools()`
- **Agent Configuration**: All patent search agents use Derwent tools
- **Skills Documentation**: Patent search skill updated to use Derwent syntax

### What Remained
Innography code structure (kept intact but unused):

### 1. High-Level Search Tools (`src/tools/search.py`)
- `patent_keyword_search()` - **No longer used in production**
- `batch_patent_search()` - **No longer used in production**
- `get_patent_details()` - **No longer used in production**
- `get_patent_citations()` - **No longer used in production**
- `citation_chain_search()` - **No longer used in production**

### 2. API Clients (`src/tools/clients/`)
- **innography.py** - Code intact, not invoked by default
- **derwent.py** - Now the active implementation

### 3. Tool Registry (`src/tools/registry.py`)
```python
# Innography tools (legacy, not in default tools)
INNOGRAPHY_TOOLS: list[BaseTool] = [
    patent_keyword_search,
    batch_patent_search,
    get_patent_details,
    # ... etc (kept for reference)
]

# Derwent tools (now default)
DERWENT_TOOLS: list[BaseTool] = [
    search_derwent_patents,
    search_derwent_patents_fld,
    search_derwent_patents_advanced,
]

def get_all_tools() -> list[BaseTool]:
    """Returns Derwent tools as default patent search."""
    return DERWENT_TOOLS + [other tools]  # Innography tools NOT included
```

### 4. Agent Configuration (`src/novelty_checker/subagents.yaml`)
- Agents now use Derwent tools for patent search
- Innography tool names are no longer referenced

---

## Derwent Tools

**File**: `src/tools/clients/derwent.py`

### 1. `search_derwent_patents()`
Search by patent IDs (publication numbers).

```python
result = search_derwent_patents(
    patent_ids="US3256182A_19660614, US3256223A_19660614",
    collections="derwentmatlat",
    max_results=100
)
```

### 2. `search_derwent_patents_fld()`
Full-text search using Derwent FLD (field-oriented) query syntax.

```python
result = search_derwent_patents_fld(
    query="ti=motor",  # Derwent syntax
    Default: Derwent Tools

**File**: `src/novelty_checker/subagents.yaml`

```yaml
patent-researcher:
  description: "Search patent databases for prior art"
  system_prompt: |
    You are a patent research expert.
    Use the Derwent patent database with the following syntax:
    - ti=term for title search
    - ab=term for abstract search
    - (field1=term OR field2=term) for multiple fields
    - Use AND, OR, NOT for boolean logic
  tools:
    - search_derwent_patents_fld      # Main search tool
    - search_derwent_patents_advanced  # Advanced with pagination
    - search_derwent_patents           # ID-based lookup
```

### Registry Configuration

**File**: `src/tools/registry.py`

```python
# Innography tools (legacy, not in get_all_tools())
INNOGRAPHY_TOOLS: list[BaseTool] = [
    patent_keyword_search,
    batch_patent_search,
    get_patent_details,
    get_patent_citations,
    batch_citation_search,
    citation_chain_search,
]

# Derwent tools (now default)
DERWENT_TOOLS: list[BaseTool] = [
    search_derwent_patents,
    search_derwent_patents_fld,
    search_derwent_patents_advanced,
]

def get_all_tools() -> list[BaseTool]:
    """Get all tools - Derwent is now the primary patent search."""
    return (
        BATCH_SEARCH_TOOLS
        + CONTENT_TOOLS
        + CITATION_TOOLS
        + DERWENT_TOOLS              # ← Derwent is primary
        + LOGGING_TOOLS
        + ANALYSIS_TOOLS
        + REFLECTION_TOOLS
        + FINDINGS_PERSISTENCE_TOOLS
    )
    # NOTE: INNOGRAPHY_TOOLS not included (kept for reference/fallback)
```

### Reverting to Innography (if needed)

If you need to temporarily revert to Innography:

```python
# In src/tools/registry.py, change get_all_tools():
def get_all_tools() -> list[BaseTool]:
    """Fallback to Innography if needed."""
    return (
        BATCH_SEARCH_TOOLS
        + CONTENT_TOOLS
        + CITATION_TOOLS
        + INNOGRAPHY_TOOLS           # ← Switch back
        + LOGGING_TOOLS
        + ANALYSIS_TOOLS
        + REFLECTION_TOOLS
        + FINDINGS_PERSISTENCE_TOOLS
    )
```python
SEARCH_TOOLS: list[BaseTool] = [
    # Innography (unchanged)
    patent_keyword_search,
    batch_patent_search,
    get_patent_details,
    get_patent_citations,
    batch_citation_search,
    citation_chain_search,
]

DERWENT_TOOLS: list[BaseTool] = [
    # Derwent (separate)
    search_derwent_patents,
    search_derwent_patents_fld,
    search_derwent_patents_advanced,
]

def get_all_tools() -> list[BaseTool]:
    """Get all tools (Innography + Derwent)."""
    return SEARCH_TOOLS + DERWENT_TOOLS
```

---

## Derwent Query Syntax

### Field Reference

| Field | Code | Example | Use Case |
|-------|------|---------|----------|
| Patent Number | `PN` | `PN=US1234567B2` | Lookup by number |
| Title | `TI` | `ti=motor` | Title search |
| Abstract | `AB` | `ab=gripper` | Abstract search |
| Keywords | `KI` | `ki=actuator` | Keyword search |
| Novelty | `NOV` | `nov=new feature` | What's new |
| Advantage | `ADV` | `adv=improved` | Benefits |
| Classifications | `CL1` | `cl1=C07K` | Primary class |
| Inventors | `IN` | `in=Smith` | Inventor search |
| Assignees | `AN` | `an=Sony` | Company search |
| Priority Date | `PD` | `pd=2020-01-01` | Date range |

### Boolean Operators

```
coffee AND tea       # Both required
coffee OR tea        # Either one
coffee NOT java      # Exclude term
(A OR B) AND C       # Grouping
```

### Proximity Operators

```
"exact phrase"       # Exact match
motor NEAR actuator  # Within distance (contextual)
```

### Example Queries

```
ti=motor                          # Simple title search
(ti=soft OR ti=compliant) AND cl1=H01M  # Combined search
ab=motor AND in=Smith             # Abstract + Inventor
ti=(hydrogen NEAR fuel)           # Proximity in title
```

---

## Usage Examples

### Example 1: Simple Title Search (Derwent)
```python
from src.tools.clients.derwent import search_derwent_patents_fld

result = search_derwent_patents_fld(
    query="ti=motor",
    size=10
)
print(result)
```

### Example 2: Complex Query (Derwent)
```python
result = search_derwent_patents_fld(
    query="(ti=soft OR ti=compliant) AND cl1=H01M",
    size=20
)
print(result)
```

### Example 3: Patent ID Lookup (Derwent)
```python
from src.tools.clients.derwent import search_derwent_patents

result = search_derwent_patents(
    patent_ids="US1234567B2, EP3411222B1",
    max_results=2
)
print(result)
```

### Example 4: Innography (Unchanged)
```python
from src.tools.search import patent_keyword_search

result = patent_keyword_search.invoke({
    'query': '@(title,abstract) motor',
    'feature_id': 'F1',
    'max_results': 10
})
print(result)
```

---

## Key Differences

### Innography vs Derwent

| Aspect | Innography | Derwent |
|--------|-----------|---------|
| **Query Syntax** | `@(field) term` | `field=term` |
| **Title** | Active (Derwent)
✅ Derwent tools - Default in registry and all agent workflows
✅ `search_derwent_patents_fld()` - Primary query tool
✅ `search_derwent_patents()` - ID-based lookup
✅ `search_derwent_patents_advanced()` - Advanced pagination

### Legacy (Innography)
🔵 Code intact in `src/tools/clients/innography.py`
🔵 Tools defined in `INNOGRAPHY_TOOLS` list
🔵 NOT included in `get_all_tools()` by default
🔵 Can be restored if needed (see "Reverting to Innography")

---

## Innography Fallback

### Code Preservation
Innography implementation is fully preserved:
- `src/tools/clients/innography.py` - Complete client implementation
- `src/tools/search.py` - High-level wrapper functions
- `INNOGRAPHY_TOOLS` list in registry

### When to Use Fallback
Only if:
1. Derwent API becomes unavailable
2. Coverage testing shows significant gaps
3. Specific patent collections unavailable in Derwent

### Quick Switch Back
Edit `src/tools/registry.py`:
```python
def get_all_tools() -> list[BaseTool]:
    # Change DERWENT_TOOLS to INNOGRAPHY_TOOLS
    return INNOGRAPHY_TOOLS + [other tools]
```

Restart agent: `langgraph dev`

**Use Innography** when:
- You have established Innography queries
- You need citation data (forward/backward)
- You prefer the @(field) syntax

**Use Derwent** when:
- You want to evaluate alternative coverage
- You need JWT-based authentication
- You prefer field=value syntax
- You need specific Derwent collections

---

## Registration Status

### Currently Registered
✅ Innography tools - All available in registry  
✅ Derwent tools - Registered in `DERWENT_TOOLS`  

Both tool sets are automatically included in `get_all_tools()` and available to agents.

### No Conversion Needed
- Use Innography queries with Innography tools
- Use Derwent queries with Derwent tools
- Both coexist without interference

---

## Related Documentation

- [DERWENTAPI_CHANGES.md](DERWENTAPI_CHANGES.md) - Derwent API reference
- [src/tools/clients/derwent.py](../src/tools/clients/derwent.py) - Derwent implementation
- [docs/ARCHITECTURE.md](ARCHITECTURE.md) - System architecture
