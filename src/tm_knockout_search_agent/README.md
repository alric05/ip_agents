# TM Knockout Search Agent

`tm_knockout_search_agent` performs first-pass trademark and brand clearance
knockout screening. It answers:

> Can this proposed brand be safely shortlisted for deeper legal review?

The current v1 implementation can normalize inputs, plan searches, normalize
source results, assess risk, write session artifacts, and generate a Markdown
report. CompuMark registry search is wired through the Swagger subset API when
`COMPUMARK_API_KEY` is configured. Conversational Studio runs use an
LLM-directed CompuMark flow: intake, natural-language search question, LLM
payload drafting/correction, API execution, content retrieval, and LLM result
analysis. Web/common-law search remains a placeholder.

## Required Input

Provide all of the following:

- Brand name: one proposed mark only in v1.
- Countries or regional systems: for example `US`, `CA`, `EUIPO`.
- Nice classes: for example `3,35`.
- Goods/services: optional but useful context, such as `cosmetics and skincare`.

Jurisdiction notes:

- `EUIPO` or `European Union` is treated as EUIPO only.
- `Europe` is ambiguous and should trigger clarification.
- The agent should not expand EUIPO into all European countries.

## Environment Variables

CompuMark configuration:

```bash
COMPUMARK_API_KEY=...
COMPUMARK_BASE_URL=https://api.clarivate.com/compumark-content/api/v1
COMPUMARK_TIMEOUT_SECONDS=30
COMPUMARK_TEXT_TEST_MODE=false
```

`COMPUMARK_BASE_URL`, `COMPUMARK_TIMEOUT_SECONDS`, and
`COMPUMARK_TEXT_TEST_MODE` are optional. The API key is sent as the `X-ApiKey`
header. The client uses the Swagger flow `POST /count`, `POST /search`, then
`POST /text`.

Provisional web/common-law search configuration:

```bash
WEB_SEARCH_API_KEY=...
TAVILY_API_KEY=...             # possible provider
BRAVE_SEARCH_API_KEY=...       # possible provider
GOOGLE_API_KEY=...             # existing repo setting, if reused
BING_SEARCH_API_KEY=...        # possible provider
```

Current unit and mocked E2E tests do not require live source variables because
they mock CompuMark and do not run web search.

## LangGraph Studio

The assistant is registered in `langgraph.json` as:

```json
"tm_knockout_search_agent": "./src/tm_knockout_search_agent/studio.py:graph"
```

Start Studio locally:

```bash
langgraph dev
```

Then open the Studio URL printed by the server and select
`tm_knockout_search_agent`.

Structured sample state:

```json
{
  "brand": "KLYRA",
  "countries": "US, EUIPO",
  "classes": "3",
  "goods": "cosmetics and skincare",
  "completed_stages": ["EXACT_ACTIVE", "SIMILAR_ACTIVE", "WEB_COMMON_LAW"]
}
```

Conversational sample state:

```json
{
  "input_message": "Please run a first-pass trademark knockout search for KLYRA in the US and EUIPO for class 3 cosmetics and skincare.",
  "session_id": "conversational-klyra-smoke",
  "max_results_per_query": 2
}
```

Conversational mode uses the LLM to extract and validate criteria, asks for
clarification when required fields are missing, drafts a natural-language
CompuMark search question, asks an LLM client node to produce the CompuMark
payload, retries that payload once after API errors, calls `/count`, `/search`,
then `/text` for up to 50 IDs, and asks an LLM analysis node to produce the
final conclusions.

Missing-criteria smoke state:

```json
{
  "brand": "KLYRA"
}
```

Expected missing-criteria behavior:

- The graph returns a `NEEDS_INPUT` style response asking for countries or
  regional systems and Nice classes.
- No live search is attempted.

Live conversational smoke input:

```json
{
  "input_message": "Please run a first-pass trademark knockout search for KLYRA in the US and EUIPO for class 3 cosmetics and skincare.",
  "session_id": "llm-compumark-smoke-klyra",
  "max_results_per_query": 5
}
```

This path makes live LLM calls and, when `COMPUMARK_API_KEY` is configured,
live CompuMark calls. If Azure OpenAI or CompuMark are reachable only through
private endpoints, run this smoke test from the approved network.

Opt-in live CompuMark smoke state:

```json
{
  "brand": "KLYRA",
  "countries": "US, EUIPO",
  "classes": "3",
  "goods": "cosmetics and skincare",
  "include_web_search": false,
  "live_compumark": true,
  "session_id": "compumark-smoke-klyra"
}
```

`live_compumark=true` executes planned CompuMark query groups. Set
`include_web_search=false` for a registry-only smoke run that can reach a final
report without waiting for the deferred web/common-law integration. Do not run
broad live searches unless the source budget and scope are intentional.

## CLI

Run a deterministic local planning/screening pass:

```bash
python -m src.tm_knockout_search_agent.main \
  --brand "KLYRA" \
  --countries "US, EUIPO" \
  --goods "cosmetics and skincare"
```

With classes:

```bash
python -m src.tm_knockout_search_agent.main \
  --brand "KLYRA" \
  --countries "US, EUIPO" \
  --classes "3,35"
```

JSON output:

```bash
python -m src.tm_knockout_search_agent.main \
  --brand "KLYRA" \
  --countries "US, EUIPO" \
  --goods "cosmetics and skincare" \
  --json
```

Opt-in live CompuMark registry-only smoke run:

```bash
python -m src.tm_knockout_search_agent.main \
  --brand "KLYRA" \
  --countries "US, EUIPO" \
  --goods "cosmetics and skincare" \
  --live-compumark \
  --no-include-web-search \
  --max-results-per-query 5 \
  --session-id "compumark-smoke-klyra"
```

The CLI validates required fields before invoking the deterministic checker.
For missing-criteria behavior that returns an agent-style clarification state,
use LangGraph Studio or the mocked E2E runner. Without `--live-compumark`, the
CLI does not call CompuMark.

## Mocked E2E Tests

Run the package test suite:

```bash
pytest tests/tm_knockout_search_agent
```

Run only the mocked E2E runner tests:

```bash
pytest tests/tm_knockout_search_agent/test_eval_runner.py
```

The mocked runner covers:

- Complete request with a high-risk mocked CompuMark result.
- Complete request with no relevant conflicts.
- Missing criteria with no search attempted.
- Required source failure documented as `SEARCH_FAILED`.

Programmatic mocked E2E example:

```python
from src.tm_knockout_search_agent.eval_runner import run_tm_knockout_mock_e2e

result = run_tm_knockout_mock_e2e(
    brand_name="KLYRA",
    countries="US, EUIPO",
    goods_services="cosmetics and skincare",
    mock_compumark_results=[
        {
            "id": "cm-klyra-us",
            "mark_name": "KLYRA",
            "jurisdiction": "US",
            "classes": ["3"],
            "goods_services": "Cosmetics and skincare",
            "status": "Registered",
            "owner": "Klyra Beauty LLC",
        }
    ],
)

print(result.final_risk_label)
print(result.final_report)
```

## Session Artifacts

TM sessions are isolated under:

```text
sessions/tm_knockout_search_agent/<session_id>/
```

Common artifacts:

- `manifest.json`
- `request.json`
- `search_criteria.json`
- `query_plan.json`
- `compumark_results.json`
- `web_results.json`
- `normalized_candidates.json`
- `source_statuses.json`
- `risk_assessment.json`
- `ranked_findings.json`
- `adversarial_review.json`
- `final_decision.json`
- `final_report.md`

Inspect a session:

```bash
ls sessions/tm_knockout_search_agent/<session_id>/
cat sessions/tm_knockout_search_agent/<session_id>/final_report.md
```

## Troubleshooting

- `tm_knockout_search_agent` does not appear in Studio:
  - Run `langgraph validate`.
  - Confirm `langgraph.json` contains the `tm_knockout_search_agent` graph.
  - Restart `langgraph dev` after code or config changes.

- Missing criteria:
  - Provide brand name, countries/regional systems, and Nice classes.
  - `Europe` is ambiguous; use `EUIPO` or specific countries.

- Live CompuMark results are missing:
  - Confirm `COMPUMARK_API_KEY` is present in `.env` or the shell environment.
  - Confirm VPN/private network access if the CompuMark endpoint is restricted.
  - Check the tool JSON for `error_type`, `error_message`, and source status.

- Live web results are missing:
  - Expected in v1. Web/common-law search still returns a deterministic
    placeholder until a web provider is selected and wired.

- LLM smoke call fails with `Public access is disabled`:
  - The Azure OpenAI deployment requires private endpoint/network access.
  - Connect to the approved network or run from an environment with private
    endpoint access, then retry with `use_llm=true`.
  - Check `llm_review.json` for the captured error.

- `SEARCH_FAILED` appears:
  - A required source status was marked failed.
  - Check `source_statuses.json`, `risk_assessment.json`, and `final_report.md`.

- No final report:
  - Check whether the run stopped at missing criteria.
  - Check `final_decision.json` and `manifest.json`.

## Confirming `novelty_checker` Was Not Affected

`novelty_checker` remains registered separately in `langgraph.json`:

```json
"novelty_checker": "./studio.py:graph"
```

Verify both assistants are registered:

```bash
langgraph validate
```

When `langgraph dev` is running, `/assistants/search` should list both:

- `novelty_checker`
- `tm_knockout_search_agent`

The TM package is self-contained under `src/tm_knockout_search_agent/` and does
not modify `src/novelty_checker/`.
