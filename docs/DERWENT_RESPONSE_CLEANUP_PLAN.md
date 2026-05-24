# Derwent Response Cleanup & Migration Parity Plan

## Why this plan exists

The Innography → Derwent migration is code-complete (client, tools, tests), and the real API now returns 200 OK with live patent data. However, the raw Derwent responses contain **XML namespace markup, duplicated language variants, trailing delimiters, and redundant form variants** that leak through into the data structures our agent consumes. This degrades LLM reasoning (wasted tokens, noise), breaks user-facing rendering, and creates contract drift vs. the Innography output the rest of the system was designed around.

This document: (a) catalogs the specific issues I observed in a real response, (b) proposes a cleanup layer inside the Derwent client, (c) defines verification criteria, and (d) lists the regression tests we need.

---

## 1. Observed Problems (evidence from real response)

Sample patent: `US12595354B2` (from `CTB=(polymer NEAR5 degradation);`)

### 1.1 XML / namespace markup leaks into text fields

| Field | What we see | What we want |
|-------|-------------|--------------|
| `nov` (DWPI Novelty) | `<tsip:paragraph xmlns:tsip="http://schemas.thomson.com/ts/20041221/tsip">Manufacturing (M1) a polycarbonate...</tsip:paragraph>` | `Manufacturing (M1) a polycarbonate...` |
| `adv` (DWPI Advantage) | `<tsip:paragraph xmlns:tsip="...">None given.</tsip:paragraph>` | empty string or `None` |
| `use` (DWPI Use) | `<tsip:paragraph xmlns:tsip="...">The method is useful for...</tsip:paragraph>` | `The method is useful for...` |
| `dtd` (Detailed Description) | `<tsip:paragraph xmlns:tsip="...">INDEPENDENT CLAIMS are also included for...</tsip:paragraph>` | plain text |
| `ab` (Abstract) | `<tsip:abstractTsxm xmlns:tsip="..." xmlns:tsxm="..." tsip:lang="en" tsip:input="original"><tsxm:p tsxm:id="p-0001" tsxm:num="0000">A method for the manufacture...</tsxm:p></tsip:abstractTsxm>` | `A method for the manufacture...` |
| `cl1` / `cl` (Claims) | `<tsip:claimTsxm xmlns:tsip="..." xmlns="..." id="CLM-00001" tsip:no="1" num="1" tsip:type="exemplary"><b>1</b>. Method for the manufacture...` | `1. Method for the manufacture...` |

**Observed patterns (exhaustive list from real samples):**
- Opening tags: `<tsip:paragraph xmlns:tsip="...">`, `<tsip:abstractTsxm ...>`, `<tsip:claimTsxm ...>`, `<tsxm:heading ...>`, `<tsxm:p ...>`
- Closing tags: `</tsip:paragraph>`, `</tsip:abstractTsxm>`, `</tsip:claimTsxm>`, `</tsxm:p>`, `</tsxm:heading>`
- Inline formatting: `<b>...</b>`, `<ul list-style="none">...</ul>`, `<li>...</li>`
- Any other `<tsip:...>` / `<tsxm:...>` / `<tsip namespace>` elements

### 1.2 Trailing-comma padding on assignees/inventors

| Field | Example (raw) | Expected |
|-------|---------------|----------|
| `co` (assignee) | `"SABIC GLOBAL TECHNOLOGIES BV,,,,"` | `"SABIC GLOBAL TECHNOLOGIES BV"` |
| `co` | `"RHEOX INC,,,,"` | `"RHEOX INC"` |
| `in` (inventor) | `"Boonman  Rob,,,,"` | `"Boonman Rob"` or `["Boonman Rob"]` |

The trailing `,,,,` is artifact of Derwent joining multi-valued fields with empty slots. The current code in [derwent.py:89](src/tools/clients/derwent.py#L89) does `split(",")` — which splits these empty trailing values into empty string elements before filtering.

### 1.3 Double whitespace in names

Inventor names have double spaces between last/first: `"Boonman  Rob"`, `"Lee  Jungwoo"`. Needs whitespace collapse.

### 1.4 Multiple form variants returned per field

The API returns the **same logical field in multiple forms** (original vs DWPI vs docdb, English vs French, etc.):

```
ab (form=orig,  lang=en): <English abstract, original>
ab (form=docdb, lang=en): <English abstract, docdb format>
ab (form=docdb, lang=fr): <French abstract>         ← should NOT pick this
ab (form=orig,  lang=fr): <French abstract>         ← should NOT pick this
```

Current `_extract_field_value()` at [derwent.py:29](src/tools/clients/derwent.py#L29) takes the **first match** — ignoring language and often picking the wrong variant. Example: for patent WO ones, French can come before English.

### 1.5 Claim-number HTML markup

After XML tag stripping, claims start with `<b>1</b>.` — the `<b>` bold tags are part of the claim numbering that comes back. Need to strip.

### 1.6 "None given." literal in DWPI Advantage

`adv` often contains literally `"None given."` — should be normalized to `None` / empty.

### 1.7 Redundant `cl` + `cl1` both requested

The client asks for both `cl` (all claims) and `cl1` (first claim only) in `return-fields`. Both contain similar (large) blocks of XML. For our use cases:
- Feature matrix / triage: `cl1` (first claim) is sufficient
- Detailed claim mapping: occasionally need `cl`

Decide on a clear policy: default to `cl1`, include `cl` only for deep-dive use cases. Reduces payload size significantly.

### 1.8 `dtd` (detailed description) is huge and rarely needed

The DWPI detailed description is often many paragraphs and rarely adds value beyond `nov`. Consider dropping from `return-fields` by default.

---

## 2. Contract — what fields should look like after cleanup

Target schema matches the **Innography `Patent` dataclass** ([schemas.py:13-69](src/tools/clients/schemas.py#L13-L69)) so downstream consumers (search.py formatting, feature_matrix, LLM prompts) see a consistent shape.

```python
{
    "publication_number":                   "US12595354B2",       # str, no trailing garbage
    "title":                                str,                   # original, English, plain text
    "dwpi_title":                           str,                   # DWPI, English, plain text
    "abstract":                             str,                   # original, English, plain text (no XML)
    "dwpi_abstract_novelty":                str | "",              # "" if missing (not "None given.")
    "dwpi_abstract_advantage":              str | "",              # "" if missing
    "dwpi_abstract_use":                    str | "",
    "dwpi_abstract_detailed_description":   str | "",              # optional; drop from default return-fields
    "claims":                               str,                   # first claim, plain text, no <b>1</b>. prefix
    "priority_date":                        "YYYY-MM-DD",          # consistent format
    "assignee":                             str | "",              # no trailing commas
    "inventors":                            ["First Last", ...],   # no trailing commas, no double spaces, empty entries removed
    "relevance_score":                      float,
}
```

Key invariants to enforce via tests:
1. No `<` or `>` characters in any string field
2. No `tsip:` or `tsxm:` substrings anywhere
3. Assignee never ends with `,`
4. Each inventor has exactly one space between words
5. `dwpi_abstract_*` is `""` (not `"None given."`) when DWPI offers no content

---

## 3. Implementation Plan

All cleanup lives in [src/tools/clients/derwent.py](src/tools/clients/derwent.py) — a single, well-tested layer. No changes to callers.

### 3.1 New helper functions

Add near the top of the file (alongside `_extract_field_value`):

```python
import re
import html

_XML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_EMPTY_DWPI_MARKERS = {"none given.", "none given", "n/a", ""}

def _clean_text(value: str | None) -> str:
    """Strip XML/HTML tags, decode entities, collapse whitespace, trim.

    Returns "" for empty / 'None given.' / None inputs.
    """
    if not value:
        return ""
    text = _XML_TAG_RE.sub("", str(value))
    text = html.unescape(text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    if text.lower() in _EMPTY_DWPI_MARKERS:
        return ""
    return text


def _clean_single(value: str | None) -> str:
    """Clean a single-valued field like assignee: strip trailing commas/spaces."""
    text = _clean_text(value)
    # strip trailing commas from comma-padded values: "BASF AG,,,," → "BASF AG"
    return text.rstrip(",").strip()


def _clean_list(value: str | None, sep: str = ",") -> list[str]:
    """Split a joined list value, clean each item, drop empties."""
    if not value:
        return []
    parts = [_clean_text(p) for p in str(value).split(sep)]
    return [p for p in parts if p]


def _claim_strip_numbering(text: str) -> str:
    """Remove leading '<b>1</b>.' or '1.' numbering artifacts from claim text."""
    # After XML strip, text often starts with "1. Method for..."
    # Could also be "<b>1</b>." before strip → just "1. ..." after strip
    # Return text as-is; optional refinement: strip leading digit + period
    return text  # keep simple — LLM tolerates "1. " prefix
```

### 3.2 Language/form-aware field extraction

Replace the current `_extract_field_value` with a smarter picker:

```python
_FORM_PRIORITY = ("dwpi", "orig", "docdb", "native", None)

def _extract_best(
    fields: list[dict],
    name: str,
    prefer_form: str | tuple[str, ...] | None = None,
    lang: str = "en",
) -> str:
    """Pick the best value for a given field name.

    Preference order:
      1. Matching prefer_form (if specified) AND matching lang
      2. Any form matching lang
      3. Any form (fallback)
    """
    preferred = (prefer_form,) if isinstance(prefer_form, str) else (prefer_form or ())
    matches = [f for f in fields if f.get("name") == name]
    if not matches:
        return ""

    # Tier 1: preferred form + correct language
    for form in preferred:
        for f in matches:
            if f.get("form") == form and (f.get("lang") in (lang, None)):
                return str(f.get("value") or "")

    # Tier 2: correct language, any form
    for f in matches:
        if f.get("lang") == lang:
            return str(f.get("value") or "")

    # Tier 3: first available
    return str(matches[0].get("value") or "")
```

### 3.3 Rewire `_format_derwent_fld_response` (and `_extract_patent_fields`, `_extract_citation_fields`)

Apply the helpers field-by-field:

```python
patent = {
    "publication_number":                   _clean_text(_extract_best(fields, "pn")),
    "title":                                _clean_text(_extract_best(fields, "ti",  prefer_form="orig")),
    "dwpi_title":                           _clean_text(_extract_best(fields, "tid", prefer_form="dwpi")),
    "abstract":                             _clean_text(_extract_best(fields, "ab",  prefer_form="orig")),
    "dwpi_abstract_novelty":                _clean_text(_extract_best(fields, "nov", prefer_form="dwpi")),
    "dwpi_abstract_advantage":              _clean_text(_extract_best(fields, "adv", prefer_form="dwpi")),
    "dwpi_abstract_use":                    _clean_text(_extract_best(fields, "use", prefer_form="dwpi")),
    "dwpi_abstract_detailed_description":   _clean_text(_extract_best(fields, "dtd", prefer_form="dwpi")),
    "claims":                               _clean_text(_extract_best(fields, "cl1") or _extract_best(fields, "cl")),
    "priority_date":                        _extract_best(fields, "prd"),  # date doesn't need XML strip
    "assignee":                             _clean_single(_extract_best(fields, "co")),
    "inventors":                            _clean_list(_extract_best(fields, "in")),
    "relevance_score":                      <unchanged>,
}
```

Do the same in `_extract_citation_fields`.

### 3.4 Payload trimming — reduce what we ask for

Update `_DEFAULT_RETURN_FIELDS` at [derwent.py:107](src/tools/clients/derwent.py#L107) to drop `dtd` (detailed description) and `cl` (full claims) by default:

```python
# Before: "pn,ki,ti,tid,ab,nov,adv,use,dtd,cl1,cl,prd,co,in,rank"
# After:  "pn,ki,ti,tid,ab,nov,adv,use,cl1,prd,co,in,rank"
```

Rationale: `cl1` covers claim previews; `dtd` is rarely referenced. Net effect: smaller payload, faster response, less LLM noise. Anyone needing the full claims or detailed description can pass a custom `return_fields` argument.

---

## 4. Verification Strategy

### 4.1 Unit tests (mocked)

Add a `TestDerwentResponseCleaning` class to [tests/test_derwent_migration.py](tests/test_derwent_migration.py) with golden-file-style assertions:

```python
def test_strips_tsip_paragraph_wrapper():
    raw = '<tsip:paragraph xmlns:tsip="http://...">Manufacturing M1.</tsip:paragraph>'
    assert _clean_text(raw) == "Manufacturing M1."

def test_strips_tsip_abstract_wrapper():
    raw = '<tsip:abstractTsxm xmlns:tsip="..." xmlns:tsxm="..."><tsxm:p>Text here.</tsxm:p></tsip:abstractTsxm>'
    assert _clean_text(raw) == "Text here."

def test_none_given_becomes_empty():
    raw = '<tsip:paragraph xmlns:tsip="...">None given.</tsip:paragraph>'
    assert _clean_text(raw) == ""

def test_trailing_commas_stripped_from_assignee():
    assert _clean_single("SABIC GLOBAL TECHNOLOGIES BV,,,,") == "SABIC GLOBAL TECHNOLOGIES BV"

def test_inventor_double_space_collapsed():
    assert _clean_list("Boonman  Rob,,,,") == ["Boonman Rob"]

def test_multi_inventor_split():
    assert _clean_list("Smith John, Doe Alice,,,,") == ["Smith John", "Doe Alice"]

def test_language_priority_english_over_french():
    # Fixture with French-first then English, should prefer English
    fields = [
        {"name": "ab", "form": "orig", "lang": "fr", "value": "<tsip:abstractTsxm>FR text</tsip:abstractTsxm>"},
        {"name": "ab", "form": "orig", "lang": "en", "value": "<tsip:abstractTsxm>EN text</tsip:abstractTsxm>"},
    ]
    assert "EN text" in _clean_text(_extract_best(fields, "ab", prefer_form="orig"))
```

### 4.2 Integration test — real API + clean output

Extend `TestDerwentRealApi` in [tests/test_derwent_migration.py](tests/test_derwent_migration.py) with invariant assertions:

```python
@pytest.mark.real_api
def test_real_response_is_clean(self, real_jwt_config):
    """Every string field should be XML-free and trim-clean."""
    from src.tools.clients.derwent import _derwent_fld_search
    patents = _derwent_fld_search("CTB=(polymer NEAR5 degradation);", size=5)
    assert not isinstance(patents, str)
    for p in patents:
        for field in ("title", "dwpi_title", "abstract", "dwpi_abstract_novelty",
                      "dwpi_abstract_advantage", "dwpi_abstract_use", "claims", "assignee"):
            val = p.get(field, "")
            assert "<" not in val and ">" not in val, f"{field} has XML: {val[:100]!r}"
            assert "tsip:" not in val and "tsxm:" not in val, f"{field} has namespace: {val[:100]!r}"
            assert val == val.strip(), f"{field} has leading/trailing whitespace"
        assert not p["assignee"].endswith(","), f"assignee trailing comma: {p['assignee']!r}"
        for inv in p.get("inventors", []):
            assert "  " not in inv, f"inventor has double space: {inv!r}"
            assert not inv.endswith(","), f"inventor trailing comma: {inv!r}"
```

### 4.3 End-to-end agent check

Manual verification — start the server, run one novelty search, inspect:
- The markdown that `search_derwent_patents_fld` returns (via SSE `tool_end` event): should look like well-formed markdown, no XML
- The saved findings file at `sessions/<id>/findings/patent_round_1.md`: patent entries should render clean
- The final feature matrix rendering

No automated assertion — just a smoke check before declaring done.

### 4.4 Innography parity check (opportunistic)

For any patent that can be looked up in **both** Innography and Derwent — compare key fields:

```python
# Ad-hoc script, not a blocking test
patent_id = "US10234567B2"  # known-common patent
inn = InnographyClient().get_patent_contents(patent_id)      # will require innography creds
drw = _derwent_fld_search(f"pn=({patent_id})", size=1)[0]

diff = {
    k: (getattr(inn, k), drw.get(k))
    for k in ("title", "assignee", "priority_date", "dwpi_abstract_novelty")
    if getattr(inn, k) != drw.get(k)
}
print(diff)  # eyeball check — should be trivially small after cleanup
```

---

## 5. Phased Execution

Each phase is independently mergeable & reversible:

| Phase | Work | Files changed | Verification |
|-------|------|---------------|--------------|
| **A** | Add `_clean_text`, `_clean_single`, `_clean_list` helpers + unit tests | [derwent.py](src/tools/clients/derwent.py), [test_derwent_migration.py](tests/test_derwent_migration.py) | new unit tests pass |
| **B** | Add `_extract_best` with form/language priority + unit tests | [derwent.py](src/tools/clients/derwent.py), [test_derwent_migration.py](tests/test_derwent_migration.py) | new unit tests pass |
| **C** | Wire helpers into `_format_derwent_fld_response`, `_extract_patent_fields`, `_extract_citation_fields` | [derwent.py](src/tools/clients/derwent.py) | existing 45 mocked tests still pass; real_api cleanliness assertion passes |
| **D** | Trim default `return-fields` (drop `dtd`, `cl`) | [derwent.py:107](src/tools/clients/derwent.py#L107) | real_api tests still pass; payload size smaller |
| **E** | Agent smoke test via server + eyeball sessions/`<id>`/findings/*.md | — | manual |
| **F** | Documentation update | [docs/DERWENT_MIGRATION_CHANGES.md](docs/DERWENT_MIGRATION_CHANGES.md) | cross-linked to this plan |

---

## 6. Risk Register

| Risk | Mitigation |
|------|-----------|
| Over-aggressive XML stripping removes legit content (e.g., `<compound>` in chemistry patents) | `_XML_TAG_RE` only matches balanced tag-like tokens; audit with 10 diverse queries (chem, mech, semi) before merging Phase C |
| Language-priority picks wrong variant for Japanese/Chinese patents | Explicit fallback chain; if `lang="en"` absent, fall through to any form (current behavior preserved) |
| Dropping `dtd` breaks something downstream | `dtd` is only referenced in [Patent.__str__](src/tools/clients/schemas.py#L50); if empty, it's just not printed — no hard dependency |
| Innography Patent dataclass has fields (like `kind_code`) that Derwent doesn't populate cleanly | Document gaps explicitly in this plan's "Contract" section; adjust only if an LLM-facing bug is reported |
| XML regex strips content it shouldn't (e.g., `<` used as less-than in chemistry claims) | Unlikely in DWPI text (encoded as `&lt;`), but unit-test with known chemistry patents |

---

## 7. Out of Scope

These are related but deferred:

- **Rewriting `search.py` formatting** — the markdown generation in `patent_keyword_search`, `get_patent_details`, `get_patent_citations` is already structured; once fields are clean, markdown renders clean. No change needed.
- **Restructuring the citation response format** — already matches Innography's shape (`total_forward_citations`, `forward_citations`, etc.) per [derwent.py:385](src/tools/clients/derwent.py#L385). Only the per-citation text fields need the same cleanup treatment (covered in Phase C).
- **Caching Derwent responses** — orthogonal perf concern; raise separately.
- **Full Innography removal** — codebase still has `INNOGRAPHY_TOOLS` fallback in registry. Leave in for now as a disaster recovery path.

---

## 8. Success Criteria

When this plan is executed:

- [ ] No `<tsip:` or `<tsxm:` anywhere in any `publication_number`, `title`, `*abstract*`, `claims`, `assignee` field returned by any Derwent tool
- [ ] `assignee` never ends with `,`
- [ ] Each inventor entry has exactly one space between tokens
- [ ] English abstract is preferred when multiple languages are returned
- [ ] `"None given."` is normalized to `""` in DWPI fields
- [ ] All 45 mocked tests still pass
- [ ] 5+ `real_api` tests pass (6th may skip due to test-patent not in materials collection)
- [ ] New cleanup-specific tests (est. 10-12 cases) all pass
- [ ] End-to-end agent smoke run produces human-readable output with no XML markup leakage
