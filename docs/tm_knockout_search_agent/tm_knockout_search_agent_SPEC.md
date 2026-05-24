# TM Knockout Search Agent — Product & Technical Specification

**Target file path in repo:** `docs/tm_knockout_search_agent/SPEC.md`  
**Agent package name:** `src/tm_knockout_search_agent/`  
**LangGraph assistant ID:** `tm_knockout_search_agent`  
**Status:** Draft v1  
**Scope:** Trademark / brand clearance knockout screening

---

## 1. Purpose of `tm_knockout_search_agent`

`tm_knockout_search_agent` is a trademark and brand clearance knockout screening agent.

Given a proposed brand name, target countries or regional trademark systems, and intended Nice classes and/or goods/services, the agent performs a structured first-pass clearance search to determine whether the brand can be safely shortlisted for deeper legal review.

The agent is not intended to provide a final global trademark clearance opinion. Its purpose is to identify obvious or significant obstacles, such as identical or highly similar trademarks, close commercial uses, or high-risk third-party rights that may prevent the proposed brand from being a good candidate for further consideration.

The primary question answered by the agent is:

> Can this brand be safely shortlisted for deeper legal review?

The expected outcome is a preliminary legal risk evaluation based on trademark registry results, web/common-law signals, and the agent's structured analysis.

---

## 2. Difference from `novelty_checker`

The existing `novelty_checker` agent is a patent-focused prior-art search system. It evaluates whether an invention appears novel by decomposing the invention into technical features, searching patent and non-patent literature sources, and generating a novelty report.

`tm_knockout_search_agent` is different in purpose, domain, workflow, tools, and evaluation logic.

### `novelty_checker`

- Domain: patents and technical prior art
- Input: invention idea or technical disclosure
- Sources: patent search, non-patent literature search, semantic patent search
- Core reasoning: feature coverage against prior-art references
- Output: novelty assessment report
- Goal: assess whether an invention appears novel

### `tm_knockout_search_agent`

- Domain: trademarks and brand clearance
- Input: proposed brand name, target jurisdictions, classes and/or goods/services
- Sources: CompuMark trademark API, web search, future litigation API
- Core reasoning: trademark similarity, goods/services relatedness, country-specific risk, owner/fame considerations, and market-use signals
- Output: trademark knockout clearance report
- Goal: assess whether a brand can be shortlisted for deeper legal review

The new agent should be independent from `novelty_checker`, but may reuse general architectural patterns from the existing repository, such as:

- LangGraph / DeepAgents conventions
- agent factory structure
- tool registry pattern
- session artifact pattern
- telemetry pattern
- middleware style
- report generation pattern
- evaluation runner pattern

The new agent should not reuse patent-specific workflows, patent-specific prompts, or novelty-specific scoring logic.

---

## 3. Expected User Inputs

The v1 agent is designed to process one proposed brand name at a time.

### 3.1 Required inputs

The minimum required criteria are:

1. Proposed brand name
2. Target countries and/or regional trademark systems
3. Nice classes and/or goods/services

Examples:

```text
Brand: NOVALIS
Countries: US, EUIPO, UK
Goods/services: skincare products and cosmetics
```

```text
Brand: VYRA
Countries: United States, Canada
Classes: 3 and 35
```

```text
Brand: AURELIA
Countries: European Union
Goods/services: downloadable mobile app for personal finance management
```

### 3.2 Country and regional system inputs

The user may provide either individual countries or regional trademark systems.

Accepted examples include:

- United States
- US
- European Union
- EUIPO
- United Kingdom
- UK
- Canada
- Other countries supported by the CompuMark API
- Other regional systems supported by the CompuMark API

If the user says `EUIPO` or `European Union`, the agent should search EUIPO only. It should not automatically expand the request to all European countries.

If the user says an ambiguous region such as `Europe`, the agent should ask a clarifying question before searching.

### 3.3 Classes and goods/services

The user may provide:

- Nice class numbers only
- Free-text goods/services only
- Both Nice classes and free-text goods/services

If the user provides free-text goods/services but no Nice classes, the agent may infer likely Nice classes and document the inference in the search criteria.

If the user provides Nice classes but no free-text goods/services, that is sufficient for the agent to proceed. The agent may note that the goods/services context is limited.

### 3.4 Optional inputs

The agent may accept optional context such as:

- Intended market or industry
- Product or service description
- Filing/use strategy
- Launch geography
- Owner/applicant name
- Preferred report language
- Date constraints
- Known competitors
- Risk tolerance
- Business context, such as B2B, B2C, luxury, pharmaceutical, software, consumer goods, financial services, etc.

These inputs are useful but not required for v1.

### 3.5 Missing required inputs

If any minimum required criteria are missing, the agent must ask concise clarifying questions before starting the search.

The agent must not begin a live trademark clearance search without:

- brand name
- target countries or regional systems
- classes and/or goods/services

---

## 4. Expected Final Outputs

The final output is a trademark knockout clearance report in a predefined template.

The report should be generated from structured JSON artifacts. JSON is the source of truth. Markdown is the human-readable output format for v1.

### 4.1 Output format for v1

The v1 output should include:

- `final_report.md`
- supporting structured JSON artifacts

No `.docx` or `.pdf` export is required in v1.

### 4.2 Report purpose

The report should provide:

- search criteria used
- sources searched
- most relevant conflicting results
- similarity analysis
- goods/services relatedness analysis
- owner/fame considerations where relevant
- web/common-law findings where relevant
- overall risk evaluation
- country-specific differences where relevant
- recommendation on whether the brand can be shortlisted for deeper legal review
- fixed disclaimer text

### 4.3 Risk labels

The agent should use the following risk labels:

- `LOW`
- `MEDIUM`
- `HIGH`
- `SEARCH_FAILED`

The report should include a single overall risk evaluation, with explanatory text highlighting differences by country or regional system where relevant.

Example:

```text
Overall risk: HIGH

The United States search identified a highly similar active mark for closely related goods. EUIPO results were lower risk, but the US result is sufficient to prevent clean shortlisting without further legal review.
```

### 4.4 Candidate surfacing

The agent may review many search results internally, but the report should surface only the strongest and most relevant findings.

The report should avoid overwhelming the user with low-relevance results.

The exact number of surfaced results will be configurable in a later implementation step. The guiding principle is:

> Review broadly, surface selectively.

---

## 5. Proposed Workflow Stages

The agent should follow a formal trademark clearance workflow.

### Stage 1 — Intake and criteria validation

The agent receives the user request and verifies that the minimum required criteria are present:

- brand name
- countries or regional systems
- classes and/or goods/services

If required criteria are missing, the agent asks clarifying questions.

If minimum criteria are present, the agent proceeds without human confirmation.

### Stage 2 — Search criteria normalization

The agent normalizes the request into structured search criteria:

- normalized brand name
- target jurisdictions
- regional systems
- provided Nice classes
- inferred Nice classes, if applicable
- goods/services description
- optional business context
- assumptions

If free-text goods/services are provided, the agent may infer likely Nice classes and document the inference.

### Stage 3 — Progressive search planning

The agent creates a progressive search plan.

The exact search progression will be defined in later implementation steps, but v1 should support the concept of staged expansion.

Initial progression concept:

1. Exact or near-exact trademark matches
2. Highly similar textual matches
3. Phonetic and spelling variants
4. Plurals and simple variations
5. Broader similarity search if earlier stages do not identify relevant results
6. Inactive/dead marks as contextual results if needed

The goal is to search broadly enough to surface the most relevant risks, not to stop at the first result.

### Stage 4 — CompuMark trademark search

The agent searches trademark data through a CompuMark API integration.

CompuMark is the primary source of truth for trademark registry results.

The CompuMark tool is not currently available in the repository and must be added as part of the new agent/tooling work. The user has the API Swagger and API key.

### Stage 5 — Web search / common-law search

The agent performs web search to identify:

- common-law or unregistered use
- commercial use
- brand fame or market presence
- company ownership signals
- domain or social-media signals where relevant
- real-world marketplace context

Web search is supplementary to CompuMark, but important for assessing real-world risk.

### Stage 6 — Candidate normalization and ranking

The agent normalizes search results into candidate records and ranks them by relevance and risk.

Ranking factors include:

- exactness or similarity of brand name
- phonetic, visual, or conceptual similarity
- same or related goods/services
- same or relevant jurisdiction
- active trademark status
- owner identity
- whether the owner appears to be a famous, large, or commercially significant company
- evidence of real-world use
- number and quality of corroborating sources

### Stage 7 — Legal risk evaluation

The agent evaluates the strongest candidates and assigns a preliminary legal risk evaluation.

The evaluation should consider:

- similarity of marks
- relatedness of goods/services
- overlap of countries/regions
- status of marks
- owner strength/fame
- market presence
- web/common-law evidence
- limitations or source failures

The agent should provide balanced legal analysis based on the findings, with fixed disclaimer text.

### Stage 8 — Adversarial review

Before finalizing the report, the agent performs an adversarial review of its own analysis.

The review should check that:

- all required countries or regional systems were searched, or source failures were documented
- all required classes/goods/services were considered
- high-risk conclusions are supported by evidence
- low-risk conclusions do not ignore relevant conflicting results
- web/common-law findings are not overstated
- inactive/dead marks are not treated as equivalent to active rights
- famous owner or famous mark considerations are not missed
- assumptions and limitations are explicit
- the report follows the predefined template

### Stage 9 — Report generation

The agent writes the final report in markdown using the predefined template.

The report should be generated from structured artifacts rather than only from free-form model memory.

---

## 6. Human Confirmation Gates

The default mode should require no human intervention once the minimum required criteria are present.

The only required human interaction in v1 is clarification when the user has not provided enough information to run the search.

### 6.1 No confirmation before search

If the user provides:

- brand name
- countries or regional systems
- classes and/or goods/services

then the agent should proceed directly to search.

### 6.2 Clarification required

The agent must ask for clarification if:

- brand name is missing
- countries/regional systems are missing
- both classes and goods/services are missing
- country/region input is ambiguous, e.g. `Europe`
- the request includes multiple brand names in v1

### 6.3 Evaluation mode

The default behavior should be compatible with end-to-end evaluation mode.

If minimum criteria are present, the agent should complete the workflow without requiring human confirmation.

---

## 7. Search Sources to Use

### 7.1 v1 sources

The v1 agent should use:

1. CompuMark trademark API
2. Web search

### 7.2 Future extension

A litigation API may be added later.

Litigation search is not required for v1.

### 7.3 CompuMark API

CompuMark is the primary trademark registry source.

The repository does not currently contain the CompuMark integration. A new CompuMark client and tool layer must be added.

The user has:

- CompuMark API Swagger
- CompuMark API key

The agent should not reuse patent-specific search tools from `novelty_checker` for trademark searching.

### 7.4 Web search

Web search should be used to supplement trademark registry results by identifying:

- unregistered/common-law use
- commercial use
- owner/fame signals
- domain or social-media signals, where relevant
- real-world marketplace context

### 7.5 Tooling principle

The new agent should have its own curated tool registry.

Recommended structure:

```text
src/tm_knockout_search_agent/tools/registry.py
src/tm_knockout_search_agent/tools/compumark.py
src/tm_knockout_search_agent/tools/web_search.py
```

The new agent may reuse generic shared infrastructure from `src/tools/` if doing so has no drawbacks, but v1 should avoid modifying existing shared tools unless necessary.

---

## 8. Definition of a Knockout Candidate

A knockout candidate is a result that creates a significant obstacle to shortlisting the proposed brand for deeper legal review.

A high-risk candidate may include:

- identical or nearly identical trademark
- highly similar mark
- active registration or application
- same or closely related goods/services
- same target country or regional system
- ownership by a famous, large, or commercially significant company
- evidence of active marketplace use
- strong web/common-law presence

A candidate is especially important if it combines:

```text
similar mark + same/related goods + relevant jurisdiction + active status
```

### 8.1 Famous marks and large company owners

Marks owned by famous, large, or commercially significant companies should receive elevated risk treatment, even if the goods/services are not identical, because enforcement risk may be higher.

### 8.2 Goods/services relatedness

The agent should reason about relatedness between goods/services, not merely exact Nice class overlap.

Examples:

- Class 3 cosmetics may be related to Class 35 retail services for cosmetics
- Class 3 skincare may be related to Class 5 medicated dermatological preparations
- Software-related classes may be related when the use case, customers, or functionality overlaps

For v1, the agent may use LLM reasoning for goods/services relatedness. Later versions may add deterministic class-relatedness rules.

### 8.3 Active and inactive marks

Active marks are primary.

Inactive, dead, abandoned, or cancelled marks may be included as contextual results, especially in later progressive search stages, but should not be treated as equivalent to active rights.

---

## 9. Stop Conditions

The agent should not stop at the first relevant result.

The agent should perform a broad enough search to identify and rank the most relevant conflicts.

The exact search budget will be defined later, but the v1 design should support configurable limits such as:

- maximum search stages
- maximum results retrieved per source
- maximum candidates normalized
- maximum candidates deeply reviewed
- maximum final candidates surfaced in the report

### 9.1 Stop when search is sufficiently complete

The agent may stop when:

- all planned search stages have completed
- enough high-relevance candidates have been reviewed
- no relevant candidates are found after planned progressive search stages
- source failures prevent reliable evaluation
- configured budget limits are reached

### 9.2 No relevant results found

If no relevant marks or uses are found, this is a meaningful outcome.

The report should state that no knockout or material blocker was identified in the searched sources and that the brand may be shortlisted for deeper legal review, subject to limitations and the fixed disclaimer.

Suggested wording:

```text
No knockout or material blocker was identified in the searched sources. On the basis of this first-pass search, the brand may be considered for shortlisting for deeper legal review, subject to the limitations described below.
```

### 9.3 Source failure

If a required source fails, the agent should not hide the failure.

If CompuMark fails for a required country or regional system, the relevant portion of the evaluation should be marked `SEARCH_FAILED`, and the overall result may be `SEARCH_FAILED` if the failure prevents a reliable evaluation.

---

## 10. Session Artifacts to Write

The new agent should write independent session artifacts.

Recommended session path:

```text
sessions/tm_knockout_search_agent/<session_id>/
```

JSON should be the source of truth. Markdown should be generated for human readability.

Recommended artifacts:

```text
sessions/tm_knockout_search_agent/<session_id>/
├── manifest.json
├── request.json
├── search_criteria.json
├── search_criteria.md
├── query_plan.json
├── compumark_results.json
├── web_results.json
├── normalized_candidates.json
├── ranked_findings.json
├── risk_assessment.json
├── adversarial_review.json
├── final_report.md
└── telemetry.json
```

### 10.1 `manifest.json`

Tracks session metadata:

- session id
- agent name
- current stage
- created timestamp
- updated timestamp
- artifact paths
- completion status
- source failure status

### 10.2 `request.json`

Stores the original user request.

### 10.3 `search_criteria.json`

Stores normalized structured criteria:

- brand name
- countries/regional systems
- classes
- inferred classes
- goods/services
- context
- assumptions

### 10.4 `search_criteria.md`

Human-readable version of the search criteria.

### 10.5 `query_plan.json`

Stores the progressive search plan.

### 10.6 `compumark_results.json`

Raw or lightly normalized CompuMark results.

### 10.7 `web_results.json`

Raw or lightly normalized web search results.

### 10.8 `normalized_candidates.json`

Unified candidate records across CompuMark and web search.

### 10.9 `ranked_findings.json`

Ranked list of strongest candidate conflicts and relevant no-hit observations.

### 10.10 `risk_assessment.json`

Structured legal risk evaluation.

### 10.11 `adversarial_review.json`

Structured review of the agent's own analysis before report finalization.

### 10.12 `final_report.md`

The final human-readable report in the predefined template.

### 10.13 `telemetry.json`

Operational telemetry such as tool calls, search stages, timing, model calls, and failures.

---

## 11. Non-Goals for v1

The following are out of scope for v1:

- full global trademark clearance opinion
- final attorney-grade clearance opinion
- filing strategy
- automated trademark filing
- domain name availability search as a primary feature
- social handle availability search as a primary feature
- logo/device mark similarity
- image/logo search
- translation screening across all languages
- name suggestion generation
- multi-name batch clearance
- full litigation history analysis
- trademark watch/monitoring over time
- automatic legal status monitoring
- full opposition/cancellation risk analysis
- comprehensive commercial marketplace investigation
- automatic report export to `.docx` or `.pdf`

### 11.1 Future extensions

Possible later phases:

- multi-name search
- name suggestions when a proposed name fails knockout screening
- litigation API integration
- logo/device mark screening
- deeper multilingual/transliteration analysis
- deterministic goods/services relatedness rules
- domain/social handle availability modules
- report export to `.docx` or `.pdf`

---

## 12. Open Questions and Assumptions

### 12.1 Open questions

1. Exact report template is not yet included in this spec.
2. Exact CompuMark API contract will be defined after reviewing the Swagger.
3. Exact progressive search stages will be defined in a later implementation step.
4. Exact search budgets will be defined later.
5. Exact fixed disclaimer text will be provided later.
6. Exact web search provider/tooling is not yet defined.
7. Exact risk scoring method is not yet defined.
8. Litigation search API is a future extension and not part of v1.
9. Exact handling of non-Latin scripts, transliteration, and translation is not part of v1 and will be defined later if needed.
10. Exact support for inactive/dead marks will be defined as part of the progressive search strategy.

### 12.2 Assumptions

1. The user-facing agent name is `TM Knockout Search Agent`.
2. The LangGraph assistant id will be `tm_knockout_search_agent`.
3. The Python package will be `src/tm_knockout_search_agent/`.
4. The agent defaults to English unless the user asks for another language.
5. The agent handles one brand name at a time in v1.
6. If the user provides free-text goods/services, the agent may infer Nice classes.
7. If the user provides only Nice classes, the agent may proceed.
8. If the user says `EUIPO` or `European Union`, the agent searches EUIPO only.
9. If the user says `Europe`, the agent asks for clarification.
10. CompuMark is the primary trademark source.
11. Web search is supplementary but required for common-law and market-use context.
12. JSON artifacts are the source of truth.
13. Markdown report is the only final export format in v1.
14. The agent should avoid modifying `novelty_checker`.
15. The agent should avoid modifying shared code unless there is a clear benefit and no drawback.
16. The agent should have its own curated tool registry.
17. The agent provides a preliminary legal risk evaluation using balanced language and fixed disclaimer text.
18. The agent should be compatible with an end-to-end evaluation mode in which no user confirmation is required once minimum input criteria are provided.

---

## 13. Initial Implementation Guardrails

The following guardrails should guide early implementation steps:

1. Do not modify `novelty_checker`.
2. Do not modify `langgraph.json` during the spec-only phase.
3. Do not implement production code during the spec-only phase.
4. Keep the new agent independent under `src/tm_knockout_search_agent/`.
5. Create a new curated tool registry for the trademark clearance agent.
6. Do not reuse patent-specific tools for trademark searching.
7. Use JSON as the source of truth for agent state and report generation.
8. Treat markdown as a human-readable output layer.
9. Keep CompuMark integration separate from patent/NPL/semantic patent tooling.
10. Make workflow stages and source failures explicit.
11. Make the adversarial review step mandatory before final report generation.
12. Prefer deterministic validation for required inputs, session artifacts, and report structure.
13. Allow the LLM to reason about trademark similarity and goods/services relatedness, but require that its conclusions be supported by surfaced evidence.
14. Keep v1 focused on one brand name, CompuMark search, web/common-law search, risk evaluation, and markdown report generation.

---

## 14. Draft Report Template Placeholder

The final report must eventually conform to the user-provided predefined template.

Until that template is supplied, v1 implementation may use the following placeholder structure for development and testing:

```markdown
# Trademark Knockout Search Report

## 1. Executive Summary

- Proposed brand:
- Countries / regional systems:
- Goods/services:
- Overall risk: LOW / MEDIUM / HIGH / SEARCH_FAILED
- Recommendation:

## 2. Search Criteria

- Brand name searched:
- Jurisdictions searched:
- Classes provided:
- Classes inferred:
- Goods/services:
- Assumptions:

## 3. Sources Searched

- CompuMark:
- Web search:
- Sources not searched:
- Source failures:

## 4. Key Findings

### Finding 1

- Mark:
- Owner:
- Jurisdiction:
- Status:
- Goods/services:
- Similarity:
- Risk relevance:

### Finding 2

- Mark:
- Owner:
- Jurisdiction:
- Status:
- Goods/services:
- Similarity:
- Risk relevance:

## 5. Similarity and Relatedness Analysis

- Mark similarity:
- Goods/services relatedness:
- Jurisdictional relevance:
- Owner/fame considerations:
- Web/common-law considerations:

## 6. Risk Evaluation

- Overall risk:
- Country-specific notes:
- Rationale:

## 7. Recommendation

- Shortlist for deeper legal review:
- Recommended next steps:

## 8. Limitations and Disclaimer

[Fixed disclaimer text to be inserted.]
```

This placeholder must be replaced or adapted once the final report template is provided.
