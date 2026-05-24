# Derwent API Integration

## Overview
This document describes the Derwent API integration for patent search and citation retrieval. The integration uses JWT Bearer token authentication and provides two main tools:

1. **`search_derwent_patents_fld`** - Full-text search using query syntax
2. **`search_derwent_citations`** - Citation search (forward and backward citations)

## Authentication

All Derwent API calls use JWT Bearer token authentication:

```
Authorization: Bearer <JWT_TOKEN>
```

The JWT token is extracted from LangGraph config:
```python
config = get_config()
jwt_token = config.get("configurable", {}).get("jwt_token")
```

## API Endpoints

### Base URL
Configured via environment variable `DERWENT_API_BASE_URL`

### Endpoints
- **Query Search**: `/ip/patents/derwent/search-by-query-internal`
- **Citation Search**: `/ip/patents/derwent/search-by-ids-internal`

---

## 1. Full-Text Search: `search_derwent_patents_fld`

**Purpose:** Search patents using Derwent query language syntax

**File:** `src/tools/clients/derwent.py`

### Function Signature

```python
@tool
def search_derwent_patents_fld(
    query: str,                                    # Required
    collections: str = "derwentmatlat",           # Optional
    return_fields: str = "pn,ki,ti,tid,ab,nov,adv,use,dtd,cl1,cl,prd,co,in",  # Optional
    size: int = 20,                               # Optional
) -> list[dict]:
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | str | Required | Derwent query syntax (e.g., `ti=neem`, `ab=motor AND co=Toyota`) |
| `collections` | str | `"derwentmatlat"` | Database collections to search |
| `return_fields` | str | See below | Comma-separated field list |
| `size` | int | 20 | Number of results to return |

### Query Syntax Examples

```python
# Title search
"ti=neem"

# Abstract search
"ab=motor"

# Classification search
"cl1=C07K"

# Combined search
"ab=motor AND co=Toyota"

# OR search
"ti=semiconductor OR ti=microchip"
```

### Return Fields Mapping

| Derwent Field | Output Field | Description |
|---------------|--------------|-------------|
| `pn` | `publication_number` | Patent publication number |
| `ti` | `title` | Original patent title |
| `tid` | `dwpi_title` | DWPI enhanced title |
| `ab` | `abstract` | Original abstract |
| `nov` | `dwpi_abstract_novelty` | DWPI novelty description |
| `adv` | `dwpi_abstract_advantage` | DWPI advantage description |
| `use` | `dwpi_abstract_use` | DWPI use description |
| `dtd` | `dwpi_abstract_detailed_description` | DWPI detailed description |
| `cl1` | `claims` (first claim) | First claim text |
| `cl` | `claims` (all claims) | All claims text |
| `prd` | `priority_date` | Priority date |
| `co` | `assignee` | Current assignee |
| `in` | `inventors` | List of inventors |
| `rank` | `relevance_score` | Search relevance score (float) |

### Response Format

Returns `list[dict]` with patent data:

```json
[
  {
    "publication_number": "US12507699B2",
    "title": "Natural mosquito repellent composition and process of preparing the same",
    "dwpi_title": "Natural mosquito repellent composition...",
    "abstract": "<tsip:abstractTsxm>The present invention relates to...</tsip:abstractTsxm>",
    "dwpi_abstract_novelty": "<tsip:paragraph>Natural mosquito repellent composition comprises...</tsip:paragraph>",
    "dwpi_abstract_advantage": "<tsip:paragraph>The composition: is natural, safe...</tsip:paragraph>",
    "dwpi_abstract_use": "",
    "dwpi_abstract_detailed_description": "",
    "claims": "<tsip:claimTsxm>...</tsip:claimTsxm>",
    "priority_date": "2019-06-25",
    "assignee": "E.I.DPARRY (INDIA) LTD",
    "inventors": ["Lakshmi Kanthan Baburaj"],
    "relevance_score": 2.0
  }
]
```

**Note:** XML/HTML formatting in fields is preserved as-is.

### Usage Example

```python
# Simple search
patents = search_derwent_patents_fld("ti=neem")

# Custom search with more results
patents = search_derwent_patents_fld(
    query="ab=motor AND cl1=H01M",
    size=50
)

# Each patent is a dictionary with all mapped fields
for patent in patents:
    print(f"{patent['publication_number']}: {patent['title']}")
    print(f"Relevance: {patent['relevance_score']}")
```

### API Request Example

```bash
curl -X POST "https://api.clarivate.com/ip/patents/derwent/search-by-query-internal" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -d '{
    "params": [{
      "query": "ti=neem",
      "collections": "derwentmatlat",
      "size": "20",
      "search-on-datatype": "fld_dwpi",
      "return-fields": "pn,ki,ti,tid,ab,nov,adv,use,dtd,cl1,cl,prd,co,in"
    }]
  }'
```

---

## 2. Citation Search: `search_derwent_citations`

**Purpose:** Retrieve forward and backward citations for patents

**File:** `src/tools/clients/derwent.py`

### Function Signature

```python
@tool
def search_derwent_citations(
    patent_ids: str,                              # Required
    max_citations: int = 100,                     # Optional
    collections: str = "derwentmatlat",          # Optional
) -> dict | list[dict]:
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `patent_ids` | str | Required | Comma-separated patent IDs (e.g., `"US3256182A_19660614"`) |
| `max_citations` | int | 100 | Maximum citations per patent (forward + backward) |
| `collections` | str | `"derwentmatlat"` | Database collections |

### Field Mappings

**Main Patent Fields:**
| Derwent Field | Output Field | Description |
|---------------|--------------|-------------|
| `pn` | `publication_number` | Patent number |
| `ti` | `title` | Original title |
| `tid` | `dwpi_title` | DWPI title |
| `co` | `current_assignee_name` | Current assignee |
| `pa` | `derwent_current_assignee_name` | DWPI assignee |
| `pd` | `publish_date` | Publication date |
| `prd` | `priority_date` | Priority date |
| `ceed` | `expiration_date` | Expiration date |
| `caid` | `status` | Legal status |
| `nov` | `dwpi_abstract_novelty` | DWPI novelty |
| `ab` | `abstract` | Abstract |
| `dcipct` | `backward_citation_count` | Count of backward citations |
| `dcipfct` | `forward_citation_count` | Count of forward citations |
| `in` | `inventor` | Inventors |

**Citation Fields:**
| Derwent Field | Output Field | Description |
|---------------|--------------|-------------|
| `pn` or `id` | `publication_number` | Patent number (uses `id` as fallback) |
| `ti` | `title` | Title |
| `tid` | `dwpi_title` | DWPI title |
| `co` | `assignee` | Current assignee |
| `pa` | `derwent_assignee` | DWPI assignee |
| `pd` | `publication_date` | Publication date |
| `prd` | `priority_date` | Priority date |
| `ceed` | `expiration_date` | Expiration date |
| `caid` | `status` | Legal status |
| `re` | `relevance` | Relevance score (string) |
| `ab` | `abstract` | Abstract |
| `nov` | `dwpi_novelty` | DWPI novelty |

### Response Format

**Single Patent:**
```json
{
  "patent_number": "US3256182A",
  "total_forward_citations": 10,
  "total_backward_citations": 5,
  "forward_citations": [
    {
      "publication_number": "US1234567A",
      "title": "...",
      "dwpi_title": "...",
      "assignee": "Company Name",
      "derwent_assignee": "COMPANY NAME",
      "publication_date": "2020-01-01",
      "priority_date": "2019-01-01",
      "relevance": "0.95",
      "abstract": "...",
      "dwpi_novelty": "..."
    }
  ],
  "backward_citations": [...]
}
```

**Multiple Patents:**
Returns `list[dict]` with the same structure per patent.

### Usage Example

```python
# Single patent
result = search_derwent_citations("US3256182A_19660614")
print(f"Forward citations: {result['total_forward_citations']}")
print(f"Backward citations: {result['total_backward_citations']}")

# Multiple patents
result = search_derwent_citations(
    "US3256182A_19660614, US3256223A_19660614",
    max_citations=50
)
for patent_data in result:
    print(f"{patent_data['patent_number']}: {patent_data['total_forward_citations']} forward")
```

### API Request Example

```bash
curl -X POST "https://api.clarivate.com/ip/patents/derwent/search-by-ids-internal" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -d '{
    "params": [{
      "ids": "US3256182A_19660614",
      "collections": "derwentmatlat",
      "size": 1,
      "return-fields": "pn,ki,tid,ti,nov,pd,prd,ceed,caid,re,ab,adv,pa,co,in,cl,cl1,id,dcipct,dcipfct",
      "filter": "expand:citations@1;1;100",
      "search-on-datatype": "fld_dwpi",
      "response-id-validation": false,
      "return-body": "true",
      "return-documents": "true",
      "return-listref": "false",
      "dwpi-basic": true
    }]
  }'
```

---

## Error Handling

Both functions include comprehensive error handling:

| Status | Error Type | Message |
|--------|-----------|---------|
| 401 | Authentication | "Invalid or expired authentication token" |
| 403 | Permission | "Insufficient permissions to access Derwent database" |
| 429 | Rate Limit | "Rate limit exceeded. Please try again later" |
| Timeout | Connection | "Request timed out. The Derwent API is not responding" |
| Network | Connection | "Network error - unable to reach the Derwent API" |

**Error Response Format:**
- FLD Search: Returns error string on failure
- Citation Search: Returns `{"error": "message"}` dict on failure

---

## Tool Registration

Both tools are registered in `src/tools/registry.py`:

```python
from .clients.derwent import (
    search_derwent_patents_fld,
    search_derwent_citations,
)

SEARCH_TOOLS: list[BaseTool] = [
    search_derwent_patents_fld,
    search_derwent_citations,
]
```

Tools are automatically available to all agents via `get_all_tools()`.

---

## Testing

### Test Server

A FastAPI test server is available for testing both tools:

```bash
python test_derwent_api_endpoint.py
```

**Endpoints:**
- `POST /test-derwent-fld` - Test FLD search
- `POST /test-derwent-citations` - Test citation search
- `GET /docs` - Swagger UI

**Example FLD Test:**
```bash
curl -X POST http://localhost:8001/test-derwent-fld \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -d '{"query": "ti=neem"}'
```

**Example Citation Test:**
```bash
curl -X POST http://localhost:8001/test-derwent-citations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -d '{"patent_ids": "US3256182A_19660614"}'
```

---

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `DERWENT_API_BASE_URL` | Base URL for Derwent API (e.g., `https://api.clarivate.com`) |

### LangGraph Config

JWT token must be passed via config:
```python
config = {
    "configurable": {
        "jwt_token": "<YOUR_JWT_TOKEN>"
    }
}
```

---

## Related Files

- `src/tools/clients/derwent.py` - Implementation
- `src/tools/registry.py` - Tool registration
- `test_derwent_api_endpoint.py` - Test server
- `.env` - Configuration

---

## Notes

1. **XML/HTML Preservation**: Field values containing XML/HTML markup are preserved as-is from the API response
2. **Inventor Filtering**: Empty inventor strings are filtered out after splitting by comma
3. **Fallback Logic**: Citation `publication_number` falls back to document `id` if `pn` field is empty
4. **Response Types**: FLD search returns `list[dict]`, citation search returns `dict` (single) or `list[dict]` (multiple)

