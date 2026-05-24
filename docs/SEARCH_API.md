# POST /search — API Reference

Deep-dive documentation for the single endpoint `POST /api/v1/search`.

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Request](#request)
   - [Query Parameters](#query-parameters)
   - [Form Parameters — Required](#form-parameters--required)
   - [Form Parameters — Optional](#form-parameters--optional)
4. [Search Types](#search-types)
5. [Collections Reference](#collections-reference)
   - [Default Collections](#default-collections)
   - [PAT/FLD — Americas](#patfld--americas)
   - [PAT/FLD — Europe](#patfld--europe)
   - [PAT/FLD — Asia-Pacific (FLD)](#patfld--asia-pacific-fld)
   - [PAT/FLD — Africa, Middle East & Other](#patfld--africa-middle-east--other)
   - [PAT/FLD — International Bodies](#patfld--international-bodies)
   - [PAT/DWPI — Derwent World Patents Index](#patdwpi--derwent-world-patents-index)
   - [PAT/APAC — Native APAC Collections](#patapac--native-apac-collections)
   - [PAT/NONAPAC — Alert-Only APAC](#patnonapac--alert-only-apac)
   - [PAT/LATAM — Latin America Native](#patlatam--latin-america-native)
   - [PAT/NONLATAM — Latin America Biblio](#patnonlatam--latin-america-biblio)
   - [LIT — Literature](#lit--literature)
   - [BUS — Business](#bus--business)
6. [Search Field Codes](#search-field-codes)
7. [Response Structure](#response-structure)
8. [Examples](#examples)
   - [Boolean Standard Search](#example-1-boolean-standard-search)
   - [Boolean Expert Search](#example-2-boolean-expert-search)
   - [AI / NGSP Search](#example-3-ai--ngsp-search)
   - [AI Sub-Search](#example-4-ai-sub-search)
   - [SSTO Smart Search](#example-5-ssto-smart-search)
   - [Patent Number Lookup](#example-6-patent-number-lookup)
   - [Pagination](#example-7-pagination)
   - [Sub-Search (Narrow Results)](#example-8-sub-search-narrow-results)
   - [Record Update Search](#example-9-record-update-search)
   - [DWPI Search — Derwent Abstract Fields](#example-10-dwpi-search--derwent-abstract-fields)
   - [DWPI Search — Manual Codes](#example-11-dwpi-search--manual-codes)
   - [CPC Classification Search](#example-12-cpc-classification-search)
   - [IPC Classification Search](#example-13-ipc-classification-search)
   - [Inventor Search](#example-14-inventor-search)
   - [Assignee / Company Portfolio Search](#example-15-assignee--company-portfolio-search)
   - [Priority Number Search](#example-16-priority-number-search)
   - [INPADOC Family Search](#example-17-inpadoc-family-search)
   - [Date Range Search](#example-18-date-range-search)
   - [Legal Status Search](#example-19-legal-status-search)
   - [Summarization / Facets](#example-20-summarization--facets)
   - [Summarization Filter (Drill Down)](#example-21-summarization-filter-drill-down)
   - [Family-Collapsed View](#example-22-family-collapsed-view)
   - [Sort by Multiple Fields](#example-23-sort-by-multiple-fields)
   - [Native APAC Search (JP/KR/CN)](#example-24-native-apac-search-jpkrcn)
   - [Literature Search — Web of Science](#example-25-literature-search--web-of-science)
   - [Literature Search — INSPEC](#example-26-literature-search--inspec)
   - [Business News Search](#example-27-business-news-search)
   - [Combined Search (Set Algebra)](#example-28-combined-search-set-algebra)
   - [Syntax Check Only](#example-29-syntax-check-only)
   - [Wildcard and Truncation Patterns](#example-30-wildcard-and-truncation-patterns)
   - [Chemical / CAS Number Search](#example-31-chemical--cas-number-search)
   - [DWPI by Accession Number Lookup](#example-32-dwpi-by-accession-number-lookup)
   - [Full Workflow: New Search → Facets → Drill Down → Navigate](#example-33-full-workflow-new-search--facets--drill-down--navigate)

---

## Overview

```
POST https://<host>/tip-innovation/api/v1/search
```

| Property | Value |
|---|---|
| **Method** | `POST` |
| **Content-Type** | `application/x-www-form-urlencoded` |
| **Resource class** | `com.derwent.services.search.SearchResource` |
| **JAX-RS path** | `@Path("search")` |
| **Servlet mount** | `/api/*` + application path `/v1` |

Executes a search query against the Tier-3 (T3) search engine and returns a result set with records, metadata, and optional summarization data.

Each successful new search produces a `rsId` (result set id). Save this value — it is required for subsequent pagination, sub-search, filter, and family-collapse requests.

---

## Authentication

All requests require a valid authenticated browser session.

| Mechanism | Detail |
|---|---|
| Cookie | `JSESSIONID` must be present and valid |
| JWT (optional) | Set `jwtAuth-search=true` for JWT-authenticated flows (external app integration) |

A `403` is returned if the session is expired or missing.

---

## Request

### Query Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `syntaxCheck` | boolean | `false` | When `true`, validates query syntax only — no search is executed. Returns parse status and error messages without consuming T3 resources. |

---

### Form Parameters — Required

| Parameter | Type | Example | Description |
|---|---|---|---|
| `searchType` | string | `STANDARD` | Type of search to execute. See [Search Types](#search-types). |
| `contentSet` | string | `PAT` | Top-level content set. One of: `PAT`, `LIT`, `BUS`, `JAPANESE`, `FED`. |
| `collectionType` | string | `FLD` | Collection grouping within the content set. One of: `FLD`, `DWPI`, `INTEGRATED`, `APAC`, `LATAM`. |
| `collections` | string | `usgrants,usapps,epgrants,epapps,woapps` | Comma-separated list of collection codes. See [Collections Reference](#collections-reference). |
| `query` | string | `TI=(solar cell) AND PY>=(2020)` | Search query string. For `AI` search type this is a JSON object — see [AI / NGSP Search](#example-3-ai--ngsp-search). |

---

### Form Parameters — Optional

#### Pagination & Result Control

| Parameter | Type | Default | Description |
|---|---|---|---|
| `resultsetId` | string | — | Pass for sub-search, pagination, or filter on an existing result set. Omit for a new search. |
| `size` | integer | `50` | Records per page. Max `500`. |
| `offset` | integer | `0` | Zero-based starting record index (e.g. `offset=50` fetches page 2 when `size=50`). |
| `list-format` | string | `hierarchy` | `hierarchy` for family-collapsed view; `flat` for individual documents. |
| `returnFields` | string | _(system default)_ | Comma-separated display field codes to include in each document record (e.g. `pn,ti,ab,pa,py`). |
| `return-documents` | boolean | `true` | Set `false` to retrieve only result counts without document records. |

#### Sorting

| Parameter | Type | Example | Description |
|---|---|---|---|
| `sortCode` | string | `+py,-pn` | Comma-separated sort field codes. Prefix `+` = ascending, `-` = descending. Omit for relevance order. |

#### Sub-Search & Filtering

| Parameter | Type | Example | Description |
|---|---|---|---|
| `subQuery` | string | `PA=(pfizer)` | Additional query to narrow the result set identified by `resultsetId`. Used with `searchType=SUBSEARCH`. |
| `filter` | string | `collapse:derwent-family@latest` | Family collapse or expansion modifier. |
| `summarize` | string | `copa,in,py` | Comma-separated field codes for top-N summarization (facet counts). |
| `summarizeSize` | integer | `100` | Maximum values returned per summarize field. |
| `summarization-filter` | string (JSON) | `{"py":["2020","2021"]}` | JSON map of field → selected values to apply as a summarization filter. |
| `active-selection` | string | `+dwpi` | Active family selection modifier. |

#### Field-Based (Standard) Search Helpers

These parameters are used when `searchType=STANDARD` to build a multi-row standard search form:

| Parameter | Type | Example | Description |
|---|---|---|---|
| `search-fields` | string | `TI~AB~PA` | Tilde (`~`) separated list of field codes, one per form row. |
| `search-value` | string | `solar cell~photovoltaic~siemens` | Tilde-separated values corresponding to each field in `search-fields`. |
| `search-operator` | string | `AND~AND` | Tilde-separated boolean operators between rows (`AND`, `OR`, `NOT`). |
| `stemming` | boolean | `true` | Enable word stemming on text fields. |

#### Patent Lookup

| Parameter | Type | Example | Description |
|---|---|---|---|
| `documentNumberType` | string | `PNS` | Number type: `PNS` (Publication Number), `PAN` (DWPI Accession Number), `IDS`. |
| `specializedSearchOption` | string | `FAMILY-inpadoc-family` | Specialized sub-type for Patent Lookup (e.g. family expansion strategy). |

#### Record Update Search

| Parameter | Type | Example | Description |
|---|---|---|---|
| `modified-start-date` | string (ISO date) | `2023-01-01` | Start date for the `RECORD_UPDATE` search window. |
| `update-fields` | string | `inp,ls,ci` | Comma-separated update-type flags. Allowed values: `inp` (new in-process), `ls` (legal status), `new` (new records), `ci` (citations), `dp` (document publication), `pa` (patent assignment). |

#### Chemical / Structure Search

| Parameter | Type | Description |
|---|---|---|
| `search-on-datatype` | string | `class` for classification search; `corporate` for corporate structure search. |
| `cmr-ids` | string | Space-separated CMR structure ids for chemical structure sub-search. |
| `markush-ids` | string | Space-separated Markush structure ids. |

#### Display & Session

| Parameter | Type | Description |
|---|---|---|
| `dpci-expand` | string | DPCI citation field code to expand from a record view context. |
| `strategyId` | string | Search history object id. Leave empty to target the user's default search history. |
| `dwpi-basic` | boolean | `true` to target DWPI Basic records only. |
| `jwtAuth-search` | boolean | `true` for JWT-authenticated search flows (external app integration). |

---

## Search Types

Passed as `searchType` in the form body.

| Value | Description |
|---|---|
| `STANDARD` | Multi-row field-based search using the standard search form. Fields, values, and operators are passed via `search-fields`, `search-value`, `search-operator`. |
| `EXPERT` | Free-text query string authored directly by the user (e.g. `TI=(solar AND cell) AND PY>=(2020)`). Full query syntax is passed in `query`. |
| `SUBSEARCH` | Narrow an existing result set. Requires `resultsetId` from a prior search. The `subQuery` (or `query`) field contains the narrowing expression. |
| `COMBINED_SEARCH` | Stacked/combined search across multiple history entries or content sets using set-algebra operators. |
| `HYBRID_COMBINED` | Hybrid combined search variant. |
| `COMBINED_SUBSEARCH` | Sub-search within a combined search result set. |
| `PATENT_LOOKUP` | Search by publication number(s) or DWPI accession number(s). Use `documentNumberType` to specify number format. |
| `RECORD_UPDATE` | Track updates (family, legal status, citations, assignment, etc.) for specified publication numbers. Requires `modified-start-date`. |
| `AI` | AI / NGSP (Natural Language) search. The `query` field must be a JSON object — see [AI / NGSP Search](#example-3-ai--ngsp-search). |
| `AISUBSEARCH` | AI-powered sub-search within an existing AI result set. Requires `resultsetId` from a prior `AI` search. |
| `AISUBCOMBINEDSEARCH` | AI sub-search within a combined-search result set. |
| `CITATION` | Citation search. |
| `FAMILY` | Family-based search. |
| `CITATION_LOOKUP` | Look up citation records by identifier. |
| `RELATED_RECORDS` | Related records search. |
| `IDS_SEARCH` | Information Disclosure Statement search. |
| `SMART_SEARCH` | Smart Search (keyword extraction + SSTO field). |
| `RELEVANCY` | Relevancy-ranked search. |
| `FILTERSEARCH` | Filter/facet-only search on an existing result set. |
| `TOC` | Table of Contents search (literature). |
| `TIMESCITED` | Times-cited search (literature). |
| `CITEDAUTHWORK` | Cited author work search (literature). |
| `STRUCTURE_SUBSEARCH` | Chemical structure sub-search using CMR/Markush structure ids. |

---

## Collections Reference

Collections are passed as a comma-separated list in the `collections` form parameter.

### Default Collections

For a new PAT/FLD (patent, fielded) session the typical default starting set is:

| Code | Description |
|---|---|
| `usgrants` | US Granted Patents |
| `usapps` | US Patent Applications |
| `epgrants` | European Patent Office — Granted |
| `epapps` | European Patent Office — Applications |
| `woapps` | PCT / WO International Applications |

These five collections (US, EP, WO) are the lowest `sequenceOrder` entries in the FLD configuration and represent the most commonly used starting point for patent searches.

---

### PAT/FLD — Americas

Use with `contentSet=PAT`, `collectionType=FLD`.

| Code | Description | Earliest Coverage |
|---|---|---|
| `usgrants` | US Granted Patents | 1790 |
| `usapps` | US Patent Applications | 2001 |
| `cagrants` | Canada — Granted Patents | — |
| `caapps` | Canada — Applications | — |
| `arumat` | Argentina — Utility Models | — |
| `aramat` | Argentina — Applications | — |
| `arutils` | Argentina — Utility (biblio) | — |
| `arapps` | Argentina — Applications (biblio) | — |
| `brumat` | Brazil — Utility Models | — |
| `brgmat` | Brazil — Granted | — |
| `bramat` | Brazil — Applications | — |
| `brutils` | Brazil — Utility (biblio) | — |
| `brgrants` | Brazil — Granted (biblio) | — |
| `brapps` | Brazil — Applications (biblio) | — |
| `mxgmat` | Mexico — Granted | — |
| `mxamat` | Mexico — Applications | — |
| `mxgrants` | Mexico — Granted (biblio) | — |
| `mxapps` | Mexico — Applications (biblio) | — |
| `coapps` | Colombia — Applications | — |
| `uyapps` | Uruguay — Applications | — |
| `cuapps` | Cuba — Applications | — |
| `cugrants` | Cuba — Granted | — |
| `tnapps` | Tunisia — Applications | — |

---

### PAT/FLD — Europe

Use with `contentSet=PAT`, `collectionType=FLD`.

| Code | Description | Earliest Coverage |
|---|---|---|
| `epgrants` | EP — Granted Patents | 1967 |
| `epapps` | EP — Applications | 1971 |
| `woapps` | PCT / WO Applications | 1978 |
| `gbgrants` | Great Britain — Granted | 1840 |
| `gbapps` | Great Britain — Applications | 1782 |
| `frgrants` | France — Granted | — |
| `frapps` | France — Applications | 1855 |
| `degrants` | Germany — Granted | 1877 |
| `deapps` | Germany — Applications | 1960 |
| `deutils` | Germany — Utility Models (Gebrauchsmuster) | 1670 |
| `atgrants` | Austria — Granted | — |
| `atapps` | Austria — Applications | — |
| `atutils` | Austria — Utility Models | — |
| `beapps` | Belgium — Applications | — |
| `begrants` | Belgium — Granted | — |
| `bgapps` | Bulgaria — Applications | — |
| `bggrants` | Bulgaria — Granted | — |
| `bgutils` | Bulgaria — Utility Models | — |
| `chapps` | Switzerland — Applications | — |
| `chgrants` | Switzerland — Granted | — |
| `csgrants` | Czechoslovakia — Granted (historical) | — |
| `czapps` | Czech Republic — Applications | — |
| `czgrants` | Czech Republic — Granted | — |
| `czutils` | Czech Republic — Utility Models | — |
| `ddapps` | East Germany (DDR) — Applications | — |
| `ddgrants` | East Germany (DDR) — Granted | — |
| `dkapps` | Denmark — Applications | — |
| `dkgrants` | Denmark — Granted | — |
| `dkutils` | Denmark — Utility Models | — |
| `eeapps` | Estonia — Applications | — |
| `eegrants` | Estonia — Granted | — |
| `eeutils` | Estonia — Utility Models | — |
| `esapps` | Spain — Applications | — |
| `esgrants` | Spain — Granted | — |
| `esutils` | Spain — Utility Models | — |
| `figrants` | Finland — Granted | — |
| `fiapps` | Finland — Applications | — |
| `grapps` | Greece — Applications | — |
| `grgrants` | Greece — Granted | — |
| `hrapps` | Croatia — Applications | — |
| `hrgrants` | Croatia — Granted | — |
| `hrutils` | Croatia — Utility Models | — |
| `hugrants` | Hungary — Granted | — |
| `ieapps` | Ireland — Applications | — |
| `iegrants` | Ireland — Granted | — |
| `ieutils` | Ireland — Utility Models | — |
| `isgrants` | Iceland — Granted | — |
| `itgrants` | Italy — Granted | — |
| `ltgrants` | Lithuania — Granted | — |
| `lugrants` | Luxembourg — Granted | — |
| `luapps` | Luxembourg — Applications | — |
| `lvgrants` | Latvia — Granted | — |
| `mcgrants` | Monaco — Granted | — |
| `mdgrants` | Moldova — Granted | — |
| `mdutils` | Moldova — Utility Models | — |
| `nlapps` | Netherlands — Applications | — |
| `nlgrants` | Netherlands — Granted | — |
| `noapps` | Norway — Applications | — |
| `nogrants` | Norway — Granted | — |
| `plgrants` | Poland — Granted | — |
| `plutils` | Poland — Utility Models | — |
| `ptapps` | Portugal — Applications | — |
| `ptgrants` | Portugal — Granted | — |
| `ptutils` | Portugal — Utility Models | — |
| `roapps` | Romania — Applications | — |
| `rogrants` | Romania — Granted | — |
| `routils` | Romania — Utility Models | — |
| `rsapps` | Serbia — Applications | — |
| `rsgrants` | Serbia — Granted | — |
| `rsutils` | Serbia — Utility Models | — |
| `ruumat` | Russia — Utility Models | 2010 |
| `ruamat` | Russia — Applications | 2010 |
| `rugmat` | Russia — Granted (utility model patent) | — |
| `seapps` | Sweden — Applications | — |
| `segrants` | Sweden — Granted | — |
| `sigrants` | Slovenia — Granted | — |
| `siutils` | Slovenia — Utility Models | — |
| `skapps` | Slovakia — Applications | — |
| `skgrants` | Slovakia — Granted | — |
| `skutils` | Slovakia — Utility Models | — |
| `sugrants` | Soviet Union (SU) — Granted (historical) | — |
| `bygrants` | Belarus — Granted | — |
| `byutils` | Belarus — Utility Models | — |
| `amgrants` | Armenia — Granted | — |
| `gegrants` | Georgia — Granted | — |
| `uagrants` | Ukraine — Granted | — |
| `uautils` | Ukraine — Utility Models | — |
| `mngrants` | Mongolia — Granted | — |
| `mnutils` | Mongolia — Utility Models | — |

---

### PAT/FLD — Asia-Pacific (FLD)

Use with `contentSet=PAT`, `collectionType=FLD`.

| Code | Description | Earliest Coverage |
|---|---|---|
| `hkgrants` | Hong Kong — Granted | — |
| `hkapps` | Hong Kong — Applications | — |
| `hkutils` | Hong Kong — Utility Models | — |
| `myapps` | Malaysia — Applications | — |
| `phapps` | Philippines — Applications | — |
| `phgrants` | Philippines — Granted | — |
| `phutils` | Philippines — Utility Models | — |
| `saamat` | Saudi Arabia — Applications | 2014 |
| `sagmat` | Saudi Arabia — Granted | 2015 |
| `thamat` | Thailand — Applications | — |
| `thumat` | Thailand — Utility Models | — |
| `trapps` | Turkey — Applications | — |
| `trgrants` | Turkey — Granted | — |
| `trutils` | Turkey — Utility Models | — |
| `vnumat` | Vietnam — Utility Models | — |

---

### PAT/FLD — Africa, Middle East & Other

Use with `contentSet=PAT`, `collectionType=FLD`.

| Code | Description | Earliest Coverage |
|---|---|---|
| `eagrants` | Eurasian Patent Organization (EA) — Granted | — |
| `ilgrants` | Israel — Granted | — |
| `maapps` | Morocco — Applications | — |
| `magrants` | Morocco — Granted | — |
| `nzgrants` | New Zealand — Granted | — |
| `oagrants` | African Intellectual Property Organization (OAPI) — Granted | — |
| `apgrants` | African Regional Intellectual Property Organization (ARIPO) — Granted | — |
| `zaapps` | South Africa — Applications | 1827 |

---

### PAT/FLD — International Bodies

Use with `contentSet=PAT`, `collectionType=FLD`.

| Code | Description | Earliest Coverage |
|---|---|---|
| `inpadoc` | INPADOC (EPO International Patent Documentation) | 1827 |
| `gcgrants` | Gulf Cooperation Council (GCC Patent Office) — Granted | — |

---

### PAT/DWPI — Derwent World Patents Index

Use with `contentSet=PAT`, `collectionType=DWPI`.

| Code | Description | Earliest Coverage |
|---|---|---|
| `derwent` | DWPI — Derwent World Patents Index | 1670 |

DWPI provides Derwent-enhanced abstracts, manual codes (MC), and Derwent accession numbers (AN). Search using DWPI-specific fields such as `TID`, `ABD`, `NOV`, `USE`, `ADV`, `ACT`, `MC`, and `AN`.

---

### PAT/APAC — Native APAC Collections

Use with `contentSet=PAT`, `collectionType=APAC`. Full-text native language collections for major Asian patent offices.

| Code | Description | Earliest Coverage |
|---|---|---|
| `cnymat` | China — Utility Models (CN Yu) | 1985 |
| `cngmat` | China — Granted Patents | 1985 |
| `cnamat` | China — Applications | 1985 |
| `ingmat` | India — Granted Patents | 1912 |
| `inamat` | India — Applications | 2000 |
| `idumat` | Indonesia — Utility Models | 1996 |
| `idamat` | Indonesia — Applications | 1988 |
| `jpumat` | Japan — Utility Models | 1936 |
| `jpgmat` | Japan — Granted Patents | 1928 |
| `jpamat` | Japan — Applications (Kokai) | 1964 |
| `krumat` | Korea — Utility Models | 1978 |
| `krgmat` | Korea — Granted Patents | 1881 |
| `kramat` | Korea — Applications | 1978 |
| `mygmat` | Malaysia — Granted Patents | 1953 |
| `sggmat` | Singapore — Granted Patents | 1983 |
| `sgamat` | Singapore — Applications | 1990 |
| `thgmat` | Thailand — Granted Patents | 1992 |
| `vngmat` | Vietnam — Granted Patents | 1984 |
| `vnamat` | Vietnam — Applications | 1986 |

---

### PAT/NONAPAC — Alert-Only APAC

These collections are available for alert/monitoring purposes only (not live search). Use with `contentSet=PAT`, `collectionType=NONAPAC`.

`jputils`, `krutils`, `cnutils`, `jpgrants`, `cngrants`, `cnapps`, `vngrants`, `mygrants`, `thgrants`, `vnapps`, `ingrants`, `inapps`, `idapps`, `idutils`, `sggrants`, `sgapps`, `jpapps`, `krapps`, `krgrants`

---

### PAT/LATAM — Latin America Native

Use with `contentSet=PAT`, `collectionType=LATAM`. Native full-text Latin American patent collections.

| Code | Description |
|---|---|
| `arumat` | Argentina — Utility Models |
| `aramat` | Argentina — Applications |
| `brumat` | Brazil — Utility Models |
| `brgmat` | Brazil — Granted |
| `bramat` | Brazil — Applications |
| `mxgmat` | Mexico — Granted |
| `mxamat` | Mexico — Applications |

---

### PAT/NONLATAM — Latin America Biblio

Bibliographic-only Latin America collections. Use with `contentSet=PAT`, `collectionType=NONLATAM`.

| Code | Description |
|---|---|
| `arutils` | Argentina — Utility (biblio) |
| `arapps` | Argentina — Applications (biblio) |
| `brutils` | Brazil — Utility (biblio) |
| `brgrants` | Brazil — Granted (biblio) |
| `brapps` | Brazil — Applications (biblio) |
| `mxgrants` | Mexico — Granted (biblio) |
| `mxapps` | Mexico — Applications (biblio) |

---

### LIT — Literature

Use with `contentSet=LIT`.

| Code | Description | Earliest Coverage |
|---|---|---|
| `WOS` | Web of Science (Science Citation Index, SSCI, A&HCI) | 1987 |
| `ISIP` | Conference Proceedings Citation Index | 1990 |
| `CCC` | Current Contents Connect | 1998 |
| `INSPEC` | INSPEC — Engineering, Physics & Electronics | 1898 |
| `XWOS` | Web of Science (extended / citation subset) | 1987 |
| `XCONF` | Conference Proceedings (extended / citation subset) | 1990 |

---

### BUS — Business

Use with `contentSet=BUS`.

| Code | Description |
|---|---|
| `NEWS` | Business & Financial News (Dialog 989) |

---

## Search Field Codes

Key field codes for use in queries, `search-fields`, `returnFields`, and `sortCode`.

### Common Patent Fields

| Code | Description |
|---|---|
| `ALL` | All text fields |
| `TI` | Title |
| `AB` | Abstract |
| `CL` | Claims |
| `CL1` | First Claim |
| `PA` | Assignee / Patent Holder (current at grant) |
| `COPA` | Current Patent Assignee (post-assignment updates) |
| `CUPPA` | Current Ultimate Parent Patent Assignee |
| `IN` | Inventor |
| `AG` | Agent / Attorney |
| `PN` | Publication Number |
| `CC` | Country Code |
| `KI` | Kind Code |
| `DP` | Publication / Document Date (`YYYYMMDD`) |
| `PY` | Publication Year (`YYYY`) |
| `AN` | DWPI Accession Number |
| `AC` | DWPI Accession Code |
| `AD` | Application Date |
| `AY` | Application Year |
| `PR` | Priority Number |
| `PRC` | Priority Country Code |
| `CPC` | CPC (Cooperative Patent Classification) |
| `IC` | IPC (International Patent Classification) |
| `AIC` | Any IPC or CPC code |
| `EC` | ECLA (European Classification) |
| `UC` | UPC (Uniform Patent Classification) |
| `MC` | Derwent Manual Code (DWPI only) |
| `DOI` | Digital Object Identifier |
| `LS` | Legal Status |
| `AS` | Assignment Status |
| `CAS` | Chemical Abstract Service Number |
| `DS` | Designated States (PCT) |

### DWPI-Specific Fields

| Code | Description |
|---|---|
| `ALLD` | All DWPI text fields |
| `TID` | Derwent Title |
| `ABD` | Derwent Abstract |
| `NOV` | Novelty section (Derwent abstract) |
| `USE` | Use section (Derwent abstract) |
| `ADV` | Advantage section (Derwent abstract) |
| `ACT` | Activity section (Derwent abstract) |
| `FOC` | Focus section (Derwent abstract) |
| `DRW` | Drawing / Figure description (Derwent) |
| `CK` | Chemical Key (Derwent) |
| `CO` | Company code |

### AI / Smart Search Fields

| Code | Description |
|---|---|
| `SSTO` | Smart Search / NGSP field — AI-extracted concept terms |

> **Note:** `COPA` and `CUPPA` are excluded from NGSP/AI searches. `SSTO` is the recommended concept-search field for use with natural-language terms.

### Literature Fields

| Code | Description |
|---|---|
| `TI` | Title |
| `AB` | Abstract |
| `AU` | Author |
| `SO` | Source (journal) |
| `PY` | Publication Year |
| `DOI` | DOI |

---

## Response Structure

`POST /search` returns a JSON object `SearchResponse`:

```json
{
  "rsId": "abc123",
  "header": {
    "found": 1234,
    "listref": "<T3 internal listref>",
    "size": 50,
    "offset": 0,
    "parseStatus": 0,
    "statusMessage": ""
  },
  "insertedQuery": "TI=(solar SAME cell) AND PY>=(2020)",
  "searchFields": ["pn", "ti", "ab", "pa", "py"],
  "parseStatus": 0,
  "statusMessage": "",
  "documents": [
    {
      "fields": {
        "pn": "US20230123456A1",
        "ti": "Solar cell with improved efficiency",
        "pa": "ACME Corp",
        "py": "2023"
      }
    }
  ],
  "summarization": {
    "copa": [
      { "value": "ACME Corp", "count": 42 },
      { "value": "BetaTech Inc", "count": 28 }
    ],
    "py": [
      { "value": "2023", "count": 312 },
      { "value": "2022", "count": 289 }
    ]
  }
}
```

| Field | Type | Description |
|---|---|---|
| `rsId` | string | Result set id — required for all follow-up requests (pagination, sub-search, filter). |
| `header.found` | integer | Total number of matching records. |
| `header.listref` | string | T3 internal list reference. |
| `header.parseStatus` | integer | `0` = valid query; non-zero = warning or error. |
| `header.statusMessage` | string | Human-readable parse status or error message. |
| `insertedQuery` | string | Query string after default operator insertion and normalization. |
| `searchFields` | string[] | Field codes returned in this result page. |
| `documents` | object[] | Array of result records, each containing a `fields` map of field code → value. |
| `summarization` | object | Top-N facet value counts for each requested `summarize` field. |

---

## Examples

### Example 1: Boolean Standard Search

Multi-row standard search form. Searches for patents about "solar cells" in the title AND "perovskite" in the abstract, limited to Siemens, published 2020 onwards.

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=STANDARD
&contentSet=PAT
&collectionType=FLD
&collections=usgrants,usapps,epgrants,epapps,woapps
&search-fields=TI~AB~PA~PY
&search-value=solar cell~perovskite~siemens~2020,2025
&search-operator=AND~AND~AND
&stemming=true
&size=50
&offset=0
&returnFields=pn,ti,ab,pa,py,ic,cpc
```

**Equivalent expert query:**
```
TI=(solar cell) AND AB=(perovskite) AND PA=(siemens) AND PY=(2020,2025)
```

---

### Example 2: Boolean Expert Search

Full query syntax entered as an expert string. Uses `AND`, `OR`, `NOT`, proximity operators (`SAME`, `NEAR`), wildcard (`*`), and range operators.

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=EXPERT
&contentSet=PAT
&collectionType=FLD
&collections=usgrants,usapps,epgrants,epapps,woapps,dkgrants,figrants
&query=TI%3D(wind+NEAR3+turbine*)+AND+CPC%3D(F03D%2F%2F)+NOT+PA%3D(vestas)
&size=50
&offset=0
&returnFields=pn,ti,pa,py,cpc
&sortCode=-py,+pn
```

**Decoded query:**
```
TI=(wind NEAR3 turbine*) AND CPC=(F03D//) NOT PA=(vestas)
```

**Key syntax notes:**
- `NEAR3` — terms within 3 words of each other in any order
- `SAME` — terms in the same sentence
- `*` — right truncation wildcard (e.g. `turbine*` matches turbines, turbine-based, etc.)
- `//` — CPC subclass wildcard (all subdivisions under `F03D`)
- Ranges: `PY>=(2018)`, `PY=(2015,2023)` (from/to)
- Boolean: `AND`, `OR`, `NOT` (uppercase required)
- Phrase: `TI=("organic photovoltaic")` (quotes for exact phrase)

---

### Example 3: AI / NGSP Search

AI (Natural Language / NGSP) search. The `query` field must be a **JSON object** with:
- `naturalText` — free-form natural language description of the invention
- `additionalFields` — (optional) AND-joined boolean filter expression to focus results

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=AI
&contentSet=PAT
&collectionType=FLD
&collections=usgrants,usapps,epgrants,epapps,woapps
&query=%7B%22naturalText%22%3A%22method+of+treating+atopic+dermatitis+using+JAK+inhibitor+compounds%22%2C%22additionalFields%22%3A%22PA%3D(pfizer+OR+abbvie)+AND+PY%3E%3D(2018)%22%7D
&size=50
&offset=0
&returnFields=pn,ti,ab,pa,py,cpc
```

**Decoded `query` value:**
```json
{
  "naturalText": "method of treating atopic dermatitis using JAK inhibitor compounds",
  "additionalFields": "PA=(pfizer OR abbvie) AND PY>=(2018)"
}
```

**How AI search works:**
1. The `naturalText` is sent to the NGSP (Next Generation Search Platform) engine with `query-syntax=ai`.
2. NGSP extracts semantic concept vectors from the natural language text and finds conceptually similar patent documents.
3. The `additionalFields` expression is applied as a boolean filter on top of the semantic results.
4. Results are ranked by semantic similarity (relevance score).
5. Fields `COPA` and `CUPPA` are excluded from AI search requests.
6. The `SSTO` field is used internally as the concept matching field; it should not be combined manually with `naturalText`.

**Tips:**
- Write `naturalText` as a description of what the invention *does* or *is about*, not as keywords.
- Use full sentences: *"process for manufacturing lithium-ion battery electrodes with improved cycle life"* performs better than keyword lists.
- Use `additionalFields` to constrain by assignee, date, classification, or country — keeping the AI engine focused on semantic matching.

---

### Example 4: AI Sub-Search

Narrow an existing AI result set using a boolean filter. Requires the `rsId` from a prior `AI` search.

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=AISUBSEARCH
&contentSet=PAT
&collectionType=FLD
&collections=usgrants,usapps,epgrants,epapps,woapps
&resultsetId=abc123
&query=CPC%3D(A61K31%2F%2F)+AND+PY%3E%3D(2020)
&size=50
&offset=0
```

**Decoded `query`:**
```
CPC=(A61K31//) AND PY>=(2020)
```

This narrows the AI result set (`rsId=abc123`) to records classified under CPC A61K31 (pharmaceutical preparations) published from 2020 onwards.

---

### Example 5: SSTO Smart Search

`SSTO` (Smart Search/NGSP field) allows you to use AI-extracted concept terms directly in a standard boolean query. Use this when you want semantic concept matching combined with other boolean operators.

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=EXPERT
&contentSet=PAT
&collectionType=FLD
&collections=usgrants,usapps,epgrants,epapps,woapps
&query=SSTO%3D(%22machine+learning%22+%22neural+network%22+%22image+classification%22)+AND+CPC%3D(G06N%2F%2F)+AND+PY%3E%3D(2019)
&size=50
&offset=0
```

**Decoded `query`:**
```
SSTO=("machine learning" "neural network" "image classification") AND CPC=(G06N//) AND PY>=(2019)
```

SSTO terms are space-joined within the parentheses and matched against the AI/NGSP concept index. This combines concept-based matching with standard boolean filters.

---

### Example 6: Patent Number Lookup

Search by publication numbers. Useful for retrieving specific known patents.

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=PATENT_LOOKUP
&contentSet=PAT
&collectionType=FLD
&collections=usgrants,usapps,epgrants,epapps,woapps
&query=US20230123456A1+EP3456789B1+WO2022012345A1
&documentNumberType=PNS
&size=50
&offset=0
&returnFields=pn,ti,ab,pa,py,ic,cpc,ls
```

Multiple publication numbers are space-separated in the `query` field. Use `documentNumberType=PAN` to look up by DWPI Accession Number instead.

---

### Example 7: Pagination

Retrieve page 2 of results from an existing result set. Pass the `rsId` returned by the initial search.

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=STANDARD
&contentSet=PAT
&collectionType=FLD
&collections=usgrants,usapps,epgrants,epapps,woapps
&resultsetId=abc123
&size=50
&offset=50
&returnFields=pn,ti,pa,py
```

Set `offset` to `pageNumber * size` to navigate pages:
| Page | `offset` (with `size=50`) |
|---|---|
| 1 | `0` |
| 2 | `50` |
| 3 | `100` |
| N | `(N-1) * size` |

---

### Example 8: Sub-Search (Narrow Results)

Narrow an existing patent result set to records matching an additional query. Requires `rsId` from a prior search.

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=SUBSEARCH
&contentSet=PAT
&collectionType=FLD
&collections=usgrants,usapps,epgrants,epapps,woapps
&resultsetId=abc123
&subQuery=PA%3D(samsung)
&size=50
&offset=0
&returnFields=pn,ti,pa,py
```

**Decoded `subQuery`:** `PA=(samsung)`

The sub-search result will contain only the intersection of `rsId=abc123` and records where the assignee is Samsung.

---

### Example 9: Record Update Search

Track changes to a set of known patents — new family members, legal status changes, citation updates, etc.

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=RECORD_UPDATE
&contentSet=PAT
&collectionType=FLD
&collections=usgrants,usapps,epgrants,epapps,woapps
&query=US9876543B2+EP2345678A1+WO2021098765A1
&documentNumberType=PNS
&modified-start-date=2024-01-01
&update-fields=inp,ls,ci,pa
&size=50
&offset=0
```

**`update-fields` values:**

| Code | Tracks |
|---|---|
| `inp` | New in-process records |
| `ls` | Legal status changes |
| `new` | Newly added records |
| `ci` | New citations |
| `dp` | Document publication updates |
| `pa` | Patent assignment changes |

---

### Example 10: DWPI Search — Derwent Abstract Fields

Search against DWPI-enhanced content using Derwent-specific abstract sections. DWPI provides curated abstracts with separate sections for Novelty, Use, Advantage, and Activity, plus Derwent Manual Codes and compound/chemical keys.

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=EXPERT
&contentSet=PAT
&collectionType=DWPI
&collections=derwent
&query=NOV%3D(polypropylene+NEAR3+catalyst)+AND+USE%3D(film+OR+packaging)+AND+PY%3E%3D(2015)
&size=50
&offset=0
&returnFields=pn,an,tid,abd,nov,use,adv,pa,mc,py
```

**Decoded query:**
```
NOV=(polypropylene NEAR3 catalyst) AND USE=(film OR packaging) AND PY>=(2015)
```

**DWPI abstract section fields:**

| Field | Searches |  
|---|---|
| `NOV` | Novelty — what is new about the invention |
| `USE` | Use — application / end-use description |
| `ADV` | Advantage — benefit vs. prior art |
| `ACT` | Activity — biological / pharmaceutical activity |
| `FOC` | Focus — secondary technical focus |
| `DRW` | Drawing / figure captions |
| `TID` | Derwent title (enhanced/translated) |
| `ABD` | Full Derwent abstract (all sections combined) |
| `ALLD` | All DWPI text (title + abstract + all sections) |

This type of search is especially powerful for chemistry and pharmaceutical patents where the original language abstract may be insufficient.

---

### Example 11: DWPI Search — Manual Codes

Derwent Manual Codes (MC field) are expert-assigned classification codes within DWPI covering 20 subject-matter sections (A–X). Useful for narrow, precise technology retrieval.

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=EXPERT
&contentSet=PAT
&collectionType=DWPI
&collections=derwent
&query=MC%3D(D12-A04+OR+D12-A05+OR+D12-B)+AND+PA%3D(basf+OR+dow+OR+dupont)+AND+PY%3D(2010,2025)
&size=50
&offset=0
&returnFields=pn,an,tid,pa,mc,py,cpc
&sortCode=-py
```

**Decoded query:**
```
MC=(D12-A04 OR D12-A05 OR D12-B) AND PA=(basf OR dow OR dupont) AND PY=(2010,2025)
```

Manual code `D12` corresponds to plastics/polymer chemistry. Sub-codes like `D12-A04` identify specific polymer types. This allows searching by chemical domain even when exact terms differ across publications.

---

### Example 12: CPC Classification Search

Search by CPC (Cooperative Patent Classification) code. CPC codes follow the pattern `Section Class Subclass Group/Subgroup` (e.g. `H01L 21/4763`).

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=EXPERT
&contentSet=PAT
&collectionType=FLD
&collections=usgrants,usapps,epgrants,epapps,woapps
&query=CPC%3D(H01L21%2F4763)+AND+PA%3D(intel+OR+tsmc+OR+samsung)+AND+PY%3E%3D(2018)
&size=50
&offset=0
&returnFields=pn,ti,pa,py,cpc,ic
```

**Decoded query:**
```
CPC=(H01L21/4763) AND PA=(intel OR tsmc OR samsung) AND PY>=(2018)
```

**CPC wildcard patterns:**

| Pattern | Matches |
|---|---|
| `H01L//` | All of subclass H01L (semiconductor devices) |
| `H01L21/4%` | All groups starting with H01L21/4 |
| `H01L21/4763` | Exact subgroup only |

Use `AIC=(H01L//)` to search both IPC and CPC simultaneously with the same wildcard.

---

### Example 13: IPC Classification Search

Search by IPC (International Patent Classification). IPC and CPC are similar hierarchies; use `IC` for strict IPC-only and `AIC` to match either.

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=EXPERT
&contentSet=PAT
&collectionType=FLD
&collections=usgrants,usapps,epgrants,epapps,woapps,cagrants,caapps
&query=AIC%3D(C12N15%2F%2F)+AND+AIC%3D(A01H5%2F%2F)+AND+PY%3D(2015,2025)
&size=50
&offset=0
&returnFields=pn,ti,pa,py,ic,cpc,ab
```

**Decoded query:**
```
AIC=(C12N15//) AND AIC=(A01H5//) AND PY=(2015,2025)
```

This finds patents classified under both `C12N15` (genetic engineering) and `A01H5` (new plant varieties) — i.e. GM crop patents.

---

### Example 14: Inventor Search

Search by inventor name. Names are indexed in `Surname Forename` format. Use truncation for partial names and `OR` for name variations.

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=EXPERT
&contentSet=PAT
&collectionType=FLD
&collections=usgrants,usapps,epgrants,epapps,woapps
&query=IN%3D(smith+john*+OR+smith+j*)+AND+PA%3D(mit+OR+%22massachusetts+institute%22)+AND+PY%3E%3D(2010)
&size=50
&offset=0
&returnFields=pn,ti,in,pa,py
```

**Decoded query:**
```
IN=(smith john* OR smith j*) AND PA=(mit OR "massachusetts institute") AND PY>=(2010)
```

**Inventor name tips:**
- Use right truncation `*` to handle middle initials: `IN=(zhang wei*)`
- Use `OR` for transliteration variants: `IN=(mueller karl OR muller karl OR mü ller karl)`
- Combine with `PA` (assignee at grant) or `COPA` (current assignee) for disambiguation
- For Japanese inventors, the romanised and Japanese name variants may differ — consider searching both

---

### Example 15: Assignee / Company Portfolio Search

Retrieve all patents owned by a company, including subsidiaries via current assignee (`COPA`) and ultimate parent (`CUPPA`). Demonstrates use of `OR` groups, `COPA`, and summarization to profile a portfolio.

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=EXPERT
&contentSet=PAT
&collectionType=FLD
&collections=usgrants,usapps,epgrants,epapps,woapps
&query=PA%3D(toyota+OR+toyota+motor+OR+%22toyota+jidosha%22)+AND+CPC%3D(B60L%2F%2F)+AND+PY%3E%3D(2015)
&size=50
&offset=0
&returnFields=pn,ti,pa,py,cpc,ic
&summarize=cpc,py,cc
&summarizeSize=20
```

**Decoded query:**
```
PA=(toyota OR toyota motor OR "toyota jidosha") AND CPC=(B60L//) AND PY>=(2015)
```

The `summarize=cpc,py,cc` parameter returns top-20 CPC codes, filing years, and countries in the response, giving a portfolio heat-map without needing additional requests.

> **Tip:** Use `CUPPA=(toyota)` instead of `PA` to automatically include all Toyota subsidiaries tracked by Derwent assignee normalization, avoiding the need to enumerate every legal entity name.

---

### Example 16: Priority Number Search

Find all patent documents that claim priority from a specific application — useful for tracing a patent family across jurisdictions.

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=EXPERT
&contentSet=PAT
&collectionType=FLD
&collections=usgrants,usapps,epgrants,epapps,woapps,cagrants,caapps,augrants,auapps,jpgmat,krgmat,cngmat
&query=PR%3D(US20210123456)+OR+PR%3D(US2021123456)
&size=50
&offset=0
&returnFields=pn,ti,pa,py,pr,cc,ki
```

**Decoded query:**
```
PR=(US20210123456) OR PR=(US2021123456)
```

Returns all publications that claim priority from the given US application, across all selected jurisdictions. Include both with and without leading zeros to handle formatting variation.

---

### Example 17: INPADOC Family Search

Search the INPADOC collection for all patent family members of a known publication. INPADOC provides the widest family coverage via EPO's international patent documentation.

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=PATENT_LOOKUP
&contentSet=PAT
&collectionType=FLD
&collections=inpadoc
&query=EP3456789B1
&documentNumberType=PNS
&specializedSearchOption=FAMILY-inpadoc-family
&size=100
&offset=0
&returnFields=pn,ti,pa,py,cc,ki,pr
```

Using `specializedSearchOption=FAMILY-inpadoc-family` expands the lookup to retrieve all INPADOC family members rather than just the exact document. The `inpadoc` collection (1827–present) has the broadest bibliographic family linkage.

---

### Example 18: Date Range Search

Demonstratesall supported date/year range operators. Use `DP` (exact document date `YYYYMMDD`) for precision or `PY` (year) for broader ranges.

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=EXPERT
&contentSet=PAT
&collectionType=FLD
&collections=usgrants,usapps,epgrants,epapps,woapps
&query=TI%3D(mRNA+vaccine)+AND+DP%3D(20200101,20231231)
&size=50
&offset=0
&returnFields=pn,ti,pa,dp,py
```

**Decoded query:**
```
TI=(mRNA vaccine) AND DP=(20200101,20231231)
```

**Date/year operator reference:**

| Syntax | Meaning |
|---|---|
| `PY=(2020)` | Exact year 2020 |
| `PY=(2018,2023)` | Year range 2018 to 2023 inclusive |
| `PY>=(2020)` | Year 2020 or later |
| `PY<=(2019)` | Year 2019 or earlier |
| `DP=(20200101,20231231)` | Document date range (YYYYMMDD) |
| `AD>=(20210601)` | Application date on or after 1 June 2021 |
| `AY=(2021,2023)` | Application year range |

---

### Example 19: Legal Status Search

Filter patents by their current legal status. Useful for identifying live/active patents, lapsed, or abandoned applications.

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=EXPERT
&contentSet=PAT
&collectionType=FLD
&collections=usgrants,epgrants
&query=TI%3D(gene+editing+OR+CRISPR)+AND+LS%3D(in+force)+AND+PY%3E%3D(2015)
&size=50
&offset=0
&returnFields=pn,ti,pa,py,ls,cc
```

**Decoded query:**
```
TI=(gene editing OR CRISPR) AND LS=(in force) AND PY>=(2015)
```

**Common `LS` values:**

| Value | Description |
|---|---|
| `in force` | Patent currently in force (examined / granted and active) |
| `lapsed` | Patent has lapsed (fees not paid) |
| `abandoned` | Application abandoned or withdrawn |
| `pending` | Application pending examination |
| `granted` | Patent granted |
| `revoked` | Patent revoked post-grant |

> Note: Legal status coverage and terminology varies by national office. Not all collections have uniform LS data.

---

### Example 20: Summarization / Facets

Run a search and request facet counts (top assignees, top years, top CPC codes) in a single request. This is the equivalent of a faceted search panel — no second request needed.

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=EXPERT
&contentSet=PAT
&collectionType=FLD
&collections=usgrants,usapps,epgrants,epapps,woapps
&query=TI%3D(solid+state+battery+OR+%22all-solid-state%22)+AND+PY%3E%3D(2012)
&size=25
&offset=0
&returnFields=pn,ti,pa,py,cpc
&summarize=copa,py,cc,cpc
&summarizeSize=15
```

**Decoded query:**
```
TI=(solid state battery OR "all-solid-state") AND PY>=(2012)
```

The response `summarization` object will contain:
- `copa` — top 15 current assignee names with record counts
- `py` — record counts by publication year
- `cc` — record counts by country code
- `cpc` — top 15 CPC codes

Use this to quickly understand the landscape before narrowing: who owns the most patents, when activity peaked, which countries are filing, and which technology sub-areas are most active.

---

### Example 21: Summarization Filter (Drill Down)

After running Example 20, drill into a specific year range and assignee without re-running the full search. Pass the `rsId` back with a `summarization-filter`.

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=FILTERSEARCH
&contentSet=PAT
&collectionType=FLD
&collections=usgrants,usapps,epgrants,epapps,woapps
&resultsetId=abc123
&summarization-filter=%7B%22py%22%3A%5B%222020%22%2C%222021%22%2C%222022%22%5D%2C%22copa%22%3A%5B%22Toyota%22%2C%22Panasonic%22%5D%7D
&size=50
&offset=0
&returnFields=pn,ti,pa,py,cpc
```

**Decoded `summarization-filter`:**
```json
{
  "py": ["2020", "2021", "2022"],
  "copa": ["Toyota", "Panasonic"]
}
```

This filters the existing result set (`rsId=abc123`) to records published in 2020–2022 AND assigned to Toyota or Panasonic. The values must match exactly as they appear in the summarization response.

---

### Example 22: Family-Collapsed View

Use `list-format=hierarchy` (the default) to collapse results by Derwent patent family, showing one representative record per family with the family count. Use `list-format=flat` to see every individual document.

**Hierarchy (family-collapsed — default):**
```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=EXPERT
&contentSet=PAT
&collectionType=FLD
&collections=usgrants,usapps,epgrants,epapps,woapps
&query=TI%3D(hydrogen+fuel+cell)+AND+PA%3D(toyota)+AND+PY%3E%3D(2010)
&list-format=hierarchy
&filter=collapse%3Aderwent-family%40latest
&size=50
&offset=0
&returnFields=pn,ti,pa,py,cc,an
```

**Flat (all documents individually):**
```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=EXPERT
&contentSet=PAT
&collectionType=FLD
&collections=usgrants,usapps,epgrants,epapps,woapps
&query=TI%3D(hydrogen+fuel+cell)+AND+PA%3D(toyota)+AND+PY%3E%3D(2010)
&list-format=flat
&size=50
&offset=0
&returnFields=pn,ti,pa,py,cc
```

The `filter=collapse:derwent-family@latest` value collapses by Derwent family and picks the latest-published document as the representative record. Family member count is returned per record.

---

### Example 23: Sort by Multiple Fields

Sort results using `sortCode`. Prefix `+` for ascending, `-` for descending. Multiple sort keys are comma-separated and applied in order.

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=EXPERT
&contentSet=PAT
&collectionType=FLD
&collections=usgrants,epgrants
&query=CPC%3D(G06F40%2F%2F)+AND+PY%3E%3D(2020)
&size=50
&offset=0
&returnFields=pn,ti,pa,py
&sortCode=-py,+pa,+pn
```

**Sort key examples:**

| `sortCode` | Result |
|---|---|
| `-py` | Newest first (descending publication year) |
| `+py` | Oldest first (ascending publication year) |
| `+pa` | Alphabetical by assignee |
| `-py,+pa` | Newest first, then alphabetical by assignee |
| `+pn` | Ascending publication number |
| `-dp` | Most recently published first (by exact date) |

Omit `sortCode` entirely to use the engine's default relevance ranking.

---

### Example 24: Native APAC Search (JP/KR/CN)

Search Japanese, Korean, and Chinese patents using native-language collections in `collectionType=APAC`. These collections include original-language full text, enabling deeper retrieval than translated documents alone.

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=EXPERT
&contentSet=PAT
&collectionType=APAC
&collections=jpgmat,jpamat,krgmat,kramat,cngmat,cnamat
&query=TI%3D(lithium+battery+OR+%E3%83%AA%E3%83%81%E3%82%A6%E3%83%A0%E9%9B%BB%E6%B1%A0)+AND+CPC%3D(H01M10%2F%2F)+AND+PY%3E%3D(2018)
&size=50
&offset=0
&returnFields=pn,ti,pa,py,cpc,cc
```

**Decoded query:**
```
TI=(lithium battery OR リチウム電池) AND CPC=(H01M10//) AND PY>=(2018)
```

Native APAC collections allow inclusion of Japanese/Chinese/Korean terms directly in the query alongside standard field codes.

**Available APAC collections by country:**

| Country | Grants | Applications | Utility Models |
|---|---|---|---|
| Japan | `jpgmat` | `jpamat` | `jpumat` |
| Korea | `krgmat` | `kramat` | `krumat` |
| China | `cngmat` | `cnamat` | `cnymat` |
| India | `ingmat` | `inamat` | — |
| Singapore | `sggmat` | `sgamat` | — |

---

### Example 25: Literature Search — Web of Science

Search peer-reviewed scientific literature using the WOS (Web of Science) collection.

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=EXPERT
&contentSet=LIT
&collectionType=FLD
&collections=WOS
&query=TI%3D(perovskite+NEAR3+solar+cell*)+AND+PY%3E%3D(2015)
&size=50
&offset=0
&returnFields=ti,au,so,py,doi,ab
&sortCode=-py
```

**Decoded query:**
```
TI=(perovskite NEAR3 solar cell*) AND PY>=(2015)
```

**Literature-specific field codes:**

| Code | Field |
|---|---|
| `TI` | Article title |
| `AB` | Abstract |
| `AU` | Author name |
| `SO` | Source (journal / book title) |
| `PY` | Publication year |
| `DOI` | Digital Object Identifier |
| `UT` | Unique article identifier (WOS key) |
| `DE` | Keywords / descriptors |
| `ID` | KeyWords Plus (WOS) |
| `J9` | Journal ISO abbreviation |
| `TC` | Times cited count |

---

### Example 26: Literature Search — INSPEC

Search INSPEC (physics, electronics, and computing literature from 1898).

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=EXPERT
&contentSet=LIT
&collectionType=FLD
&collections=INSPEC
&query=TI%3D(convolutional+neural+network*)+AND+AB%3D(object+detection)+AND+PY%3D(2018,2024)
&size=50
&offset=0
&returnFields=ti,au,so,py,ab,doi
```

**Decoded query:**
```
TI=(convolutional neural network*) AND AB=(object detection) AND PY=(2018,2024)
```

INSPEC is the premier source for electronics, control theory, computing, and physics literature. It reaches back to 1898, making it valuable for historical technology research.

---

### Example 27: Business News Search

Search business and financial news using the `BUS` content set.

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=EXPERT
&contentSet=BUS
&collectionType=FLD
&collections=NEWS
&query=TI%3D(merger+OR+acquisition)+AND+AB%3D(semiconductor)+AND+PY%3E%3D(2022)
&size=50
&offset=0
&returnFields=ti,so,py,ab
&sortCode=-py
```

**Decoded query:**
```
TI=(merger OR acquisition) AND AB=(semiconductor) AND PY>=(2022)
```

The `NEWS` collection (Dialog 989) covers business news, press releases, and financial reports. Use it alongside patent searches to correlate IP activity with corporate M&A events.

---

### Example 28: Combined Search (Set Algebra)

Combine multiple prior search history entries using set algebra operators. Search history rows are referenced by their position in the current session.

**Scenario:** 
- Search #1 (rsId `s1`) = battery patents by Toyota
- Search #2 (rsId `s2`) = battery patents by Panasonic

Combine them with `OR` to create a merged set:

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=COMBINED_SEARCH
&contentSet=PAT
&collectionType=FLD
&collections=usgrants,usapps,epgrants,epapps,woapps
&query=%231+OR+%232
&size=50
&offset=0
&returnFields=pn,ti,pa,py
```

**Decoded query:** `#1 OR #2`

**Set algebra operators:**

| Operator | Meaning |
|---|---|
| `#1 OR #2` | Union — all records in either set |
| `#1 AND #2` | Intersection — records in both sets |
| `#1 NOT #2` | Difference — records in #1 but not #2 |
| `#1 AND NOT #2` | Same as `NOT` — explicit form |

Row numbers correspond to the order of searches in the user's current search history session.

---

### Example 29: Syntax Check Only

Validate a query without executing it. Returns parse status, error messages, and any auto-corrections. Use `syntaxCheck=true` as a query parameter.

```http
POST /tip-innovation/api/v1/search?syntaxCheck=true
Content-Type: application/x-www-form-urlencoded

searchType=EXPERT
&contentSet=PAT
&collectionType=FLD
&collections=usgrants,epgrants
&query=TI%3D(solar+NEAR3+cell*)+AND+PY%3E%3D(2020
```

**Response when invalid (missing closing parenthesis):**
```json
{
  "rsId": null,
  "parseStatus": 1,
  "statusMessage": "Syntax error at position 42: expected ')'",
  "insertedQuery": null,
  "documents": [],
  "header": { "found": 0 }
}
```

**Response when valid:**
```json
{
  "rsId": null,
  "parseStatus": 0,
  "statusMessage": "",
  "insertedQuery": "TI=(solar NEAR3 cell*) AND PY>=(2020)",
  "documents": [],
  "header": { "found": 0 }
}
```

No T3 search credits are consumed. Useful for building and testing queries before executing them.

---

### Example 30: Wildcard and Truncation Patterns

Demonstrates all supported wildcard and truncation forms in query expressions.

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=EXPERT
&contentSet=PAT
&collectionType=FLD
&collections=usgrants,usapps,epgrants,epapps,woapps
&query=TI%3D(nanotub*+OR+nano-tub*+OR+%22carbon+nanostructur%3F%22)+AND+PY%3E%3D(2010)
&size=50
&offset=0
&returnFields=pn,ti,pa,py
```

**Decoded query:**
```
TI=(nanotub* OR nano-tub* OR "carbon nanostructur?") AND PY>=(2010)
```

**Wildcard reference:**

| Character | Meaning | Example | Matches |
|---|---|---|---|
| `*` | Zero or more characters (right truncation) | `nanotub*` | nanotube, nanotubes, nanotube-based |
| `?` | Exactly one character | `nanostructur?` | nanostructure, nanostructures |
| `#` | Zero or one character | `colo#r` | color, colour |
| `$` | Zero or one character (same as `#`) | `organi$ation` | organisation, organization |
| `*` (in phrase) | Phrase with wildcard | `"carbon nano*"` | carbon nanotube, carbon nanofiber |

> Wildcards cannot appear at the **start** of a term. `*tube` is invalid; use `AB=(tube*)` and broaden manually.

---

### Example 31: Chemical / CAS Number Search

Search patents by a CAS (Chemical Abstracts Service) Registry Number. CAS numbers identify specific chemical compounds.

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=EXPERT
&contentSet=PAT
&collectionType=FLD
&collections=usgrants,usapps,epgrants,epapps,woapps
&query=CAS%3D(50-78-2)+AND+PY%3E%3D(2000)
&size=50
&offset=0
&returnFields=pn,ti,pa,py,cas,ab
```

**Decoded query:**
```
CAS=(50-78-2) AND PY>=(2000)
```

CAS `50-78-2` is aspirin (acetylsalicylic acid). Returns all patents referencing this specific compound by its registry number.

For DWPI chemical compound searching you can also use the `CK` (Chemical Key) field specific to Derwent Manual Code chemistry sections.

---

### Example 32: DWPI by Accession Number Lookup

Look up specific DWPI records by their Derwent Accession Number (`AN`). Accession numbers take the format `YYYY-NNNNNN` (e.g. `2020-123456`).

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=PATENT_LOOKUP
&contentSet=PAT
&collectionType=DWPI
&collections=derwent
&query=2020-123456+2021-987654+2019-456123
&documentNumberType=PAN
&size=50
&offset=0
&returnFields=pn,an,tid,abd,pa,mc,py
```

Multiple Derwent Accession Numbers are space-separated. Set `documentNumberType=PAN` (Patent Accession Number) to instruct the engine to parse them as `AN` values rather than publication numbers.

---

### Example 33: Full Workflow — New Search → Facets → Drill Down → Navigate

This example shows a complete multi-request workflow as a user would experience it in the product.

#### Step 1 — Execute new search with facets

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=EXPERT
&contentSet=PAT
&collectionType=FLD
&collections=usgrants,usapps,epgrants,epapps,woapps
&query=TI%3D(autonomous+vehicle*+OR+self-driving)+AND+CPC%3D(B60W%2F%2F)+AND+PY%3E%3D(2015)
&list-format=hierarchy
&filter=collapse%3Aderwent-family%40latest
&size=25
&offset=0
&returnFields=pn,ti,pa,py,cpc
&summarize=copa,py,cc,cpc
&summarizeSize=10
```

**Save from response:** `rsId = "xyz789"`, `header.found = 8432`

**Summarization response excerpt:**
```json
"summarization": {
  "copa": [
    { "value": "Waymo LLC", "count": 412 },
    { "value": "Tesla Inc", "count": 387 },
    { "value": "General Motors", "count": 256 }
  ],
  "py": [
    { "value": "2022", "count": 1893 },
    { "value": "2021", "count": 1644 },
    { "value": "2023", "count": 1512 }
  ]
}
```

#### Step 2 — Drill down to Waymo patents, 2020–2023

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=FILTERSEARCH
&contentSet=PAT
&collectionType=FLD
&collections=usgrants,usapps,epgrants,epapps,woapps
&resultsetId=xyz789
&summarization-filter=%7B%22copa%22%3A%5B%22Waymo+LLC%22%5D%2C%22py%22%3A%5B%222020%22%2C%222021%22%2C%222022%22%2C%222023%22%5D%7D
&size=25
&offset=0
&returnFields=pn,ti,pa,py,cpc
```

**Decoded `summarization-filter`:**
```json
{ "copa": ["Waymo LLC"], "py": ["2020", "2021", "2022", "2023"] }
```

**Save from response:** `rsId = "xyz790"`, `header.found = 312`

#### Step 3 — Sub-search to further narrow to sensor-fusion patents

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=SUBSEARCH
&contentSet=PAT
&collectionType=FLD
&collections=usgrants,usapps,epgrants,epapps,woapps
&resultsetId=xyz790
&subQuery=TI%3D(lidar+OR+radar+OR+%22sensor+fusion%22)
&size=25
&offset=0
&returnFields=pn,ti,pa,py,cpc
```

**Save from response:** `rsId = "xyz791"`, `header.found = 47`

#### Step 4 — Page 2 of results

```http
POST /tip-innovation/api/v1/search
Content-Type: application/x-www-form-urlencoded

searchType=SUBSEARCH
&contentSet=PAT
&collectionType=FLD
&collections=usgrants,usapps,epgrants,epapps,woapps
&resultsetId=xyz791
&size=25
&offset=25
&returnFields=pn,ti,pa,py,cpc
```

This completes a typical research session: broad search → facet overview → filter to key player → sub-search to narrow topic → paginate through results.
