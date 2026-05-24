# Novelty Checker — System Architecture

## 1. System Overview

The Novelty Checker is a **hierarchical multi-agent system** that automates patent novelty assessment. Given a customer's invention description, it orchestrates parallel searches across patent databases, academic literature, and semantic indices, then synthesizes a comprehensive 11-section novelty report.

### Technology Stack

| Layer | Technology | Role |
|-------|-----------|------|
| Orchestration | **LangGraph** | State machine graph, checkpointing, message passing |
| Agent Framework | **deepagents** (pip-installed) | `create_deep_agent()`, middleware protocol, subagent delegation |
| LLM Access | **LiteLLM** via `langchain_litellm` | Unified interface for 100+ LLM providers (OpenAI, Anthropic, Google, Bedrock) |
| Persistence | **FilesystemBackend** | Session-isolated virtual filesystem for artifacts |
| Search APIs | Innography, Web of Science, NGSP | Patent keyword, academic literature, semantic patent search |

### Entry Points

| Entry Point | File | Mode | Use Case |
|-------------|------|------|----------|
| LangGraph Studio | `studio.py` | Factory (per-thread isolation) | Interactive UI, multiple concurrent conversations |
| CLI | `src/novelty_checker/main.py` | Static (single session) | Command-line single invention check |
| Python API | `deep_agent.py::check_novelty()` | Static | Programmatic integration |
| E2E Evaluation | `src/novelty_checker/eval_runner.py` | Static | Automated test runs with gate auto-approval |

---

## 2. Component Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            ENTRY POINTS                                         │
│  studio.py (LangGraph Studio)  │  main.py (CLI)  │  check_novelty() (API)      │
└────────────────────────────────┬────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      create_deep_agent()  [deep_agent.py]                       │
│                                                                                 │
│  Inputs:                                                                        │
│  ├── model (LiteLLM)          ├── memory: [AGENTS.md]                           │
│  ├── system_prompt (prompts.py: NOVELTY_WORKFLOW + SEARCH_DELEGATION)           │
│  ├── skills: [skills/]        ├── subagents: (subagents.yaml)                   │
│  ├── backend (FilesystemBackend or ThreadAwareBackendFactory)                   │
│  ├── middleware: [7 layers]   └── checkpointer (MemorySaver or platform)        │
│                                                                                 │
└────────────────────────────────┬────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         COMPILED LANGGRAPH                                      │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐    │
│  │                    ORCHESTRATOR AGENT (Coordinator)                      │    │
│  │                                                                         │    │
│  │  System Prompt:                                                         │    │
│  │  ├── AGENTS.md (base: mission, stages, gates, coverage targets)         │    │
│  │  ├── NOVELTY_WORKFLOW_INSTRUCTIONS (research loop, stopping logic)      │    │
│  │  ├── SEARCH_DELEGATION_INSTRUCTIONS (parallel dispatch, context rules)  │    │
│  │  └── skills/*/SKILL.md (progressive disclosure per stage)               │    │
│  │                                                                         │    │
│  │  Tools: patent_keyword_search, npl_search, semantic_patent_search,      │    │
│  │         batch_*, triage_reference, map_features_to_reference,           │    │
│  │         save_round_findings, get_all_findings, get_coverage_gaps,       │    │
│  │         think_tool, read_file, write_file, edit_file, write_todos       │    │
│  │                                                                         │    │
│  │  Delegation: task(subagent_type="...", description="...")               │    │
│  └─────────────────────────────────────────────────────────────────────────┘    │
│       │                                                                         │
│       │  task() calls (parallel dispatch in ONE AI message)                     │
│       ▼                                                                         │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐       │
│  │   patent-     │ │    npl-      │ │  semantic-   │ │   citation-      │       │
│  │  researcher   │ │  researcher  │ │  researcher  │ │   researcher     │       │
│  │              │ │              │ │              │ │  (Round 2+ only) │       │
│  │  Innography  │ │ Web of Sci.  │ │    NGSP      │ │  Citation nets   │       │
│  │  @(field)    │ │ TS=, TI=     │ │  NL gists    │ │  fwd + backward  │       │
│  │  max 10 srch │ │ max 8 srch   │ │  max 7 srch  │ │  max 5 A-refs    │       │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────────┘       │
│       │                                                                         │
│       │  Also available (alternative parallel paths):                           │
│       │                                                                         │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                            │
│  │   keyword-   │ │  semantic-   │ │  structural- │                            │
│  │  precision   │ │   recall     │ │    combo     │                            │
│  │  searcher    │ │  searcher    │ │   searcher   │                            │
│  └──────────────┘ └──────────────┘ └──────────────┘                            │
│       │                                                                         │
│       │  Post-research:                                                         │
│       │                                                                         │
│  ┌──────────────┐ ┌──────────────┐                                             │
│  │  coverage-   │ │   report-    │                                             │
│  │   analyst    │ │    writer    │                                             │
│  │  (internal)  │ │ (11-section) │                                             │
│  └──────────────┘ └──────────────┘                                             │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                      MIDDLEWARE STACK (7 layers)                                 │
│                                                                                 │
│  ① FindingsPersistenceMiddleware  — auto-capture search results                 │
│  ② PatentTrackingMiddleware       — passive patent lifecycle observer            │
│  ③ FeatureConfirmationMiddleware  — Gate 2 enforcement                          │
│  ④ AutonomousResearchMiddleware   — block user prompts post-Gate 2              │
│  ⑤ ResearchContinuationMiddleware — enforce loop continuation                   │
│  ⑥ CitationEnforcementMiddleware  — inject citation-researcher directives       │
│  ⑦ TelemetryMiddleware            — tool call metrics                           │
│                                                                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                      SESSION STORAGE                                            │
│                                                                                 │
│  FilesystemBackend (virtual_mode=True)                                          │
│  └── sessions/{session_id}/                                                     │
│      ├── scope.md              ├── features.md                                  │
│      ├── findings/             ├── references.md                                │
│      ├── report.md             ├── telemetry.json                               │
│      └── patent_statistics.md                                                   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Graph Construction

### `create_deep_agent()` — The Factory Function

**Location:** `src/novelty_checker/deep_agent.py:361`

This function assembles all components and returns a compiled LangGraph `StateGraph`:

```python
graph = _create_deep_agent(
    model=model,                          # LiteLLM ChatModel
    memory=[agents_md_path],              # AGENTS.md → base system prompt (MemoryMiddleware)
    system_prompt=orchestrator_instructions,  # Workflow + delegation prompts
    skills=[skills_path],                 # skills/*/SKILL.md (SkillsMiddleware)
    tools=tools,                          # 40+ tools from registry
    subagents=subagents,                  # 9 agents from subagents.yaml (SubAgentMiddleware)
    backend=backend,                      # FilesystemBackend or factory callable
    middleware=[...],                     # 7 custom middleware
    checkpointer=checkpointer,           # MemorySaver or platform-provided
    context_schema=context_schema,        # Optional DeepAgentState TypedDict
)
```

### Prompt Composition

The orchestrator's system prompt is assembled from multiple sources:

```
AGENTS.md                              ← Base: mission, stage pipeline, gate rules,
                                          coverage targets, triage labels, report schema
    +
NOVELTY_WORKFLOW_INSTRUCTIONS          ← Research loop structure, adaptive stopping,
                                          semantic search emphasis, diminishing returns
    +
SEARCH_DELEGATION_INSTRUCTIONS         ← Coordinator pattern, parallel dispatch rule,
                                          context isolation warning, gap-filling
    +
skills/*/SKILL.md                      ← Progressive disclosure per stage
                                          (scoping, feature-definition, patent-search,
                                           npl-search, semantic-search, citation-search,
                                           screening, parallel-search, report)
```

### Two Operational Modes

| Mode | Flag | Backend | Session Isolation | Use Case |
|------|------|---------|-------------------|----------|
| **Factory** | `use_backend_factory=True` | `ThreadAwareBackendFactory` | Per-thread directories under `sessions/{thread_id}/` | LangGraph Studio (multiple concurrent threads) |
| **Static** | `use_backend_factory=False` | `FilesystemBackend` | Single `sessions/{session_id}/` directory | CLI, Python API, evaluation runner |

In Factory mode, the `ThreadAwareBackendFactory` (`backend_factory.py`) is a callable matching `BackendFactory = Callable[[ToolRuntime], BackendProtocol]`. When any tool or middleware calls it, it extracts `thread_id` from `ToolRuntime.config["configurable"]["thread_id"]` and returns a `FilesystemBackend` scoped to that thread's session directory.

### Subagent Recursion Limit Patch

LangGraph Studio sends `recursion_limit=100` in run config, which propagates to subagents. This is too low for researchers doing 5-10 searches with think_tool reflections. A monkey-patch at module load (`deep_agent.py:64-75`) wraps every subagent graph with `.with_config({"recursion_limit": 500})`.

---

## 4. Middleware Stack

Middleware execute as hooks on every LLM call and tool call. They are listed in the order passed to `create_deep_agent()`:

### ① FindingsPersistenceMiddleware
**File:** `middleware/findings.py` | **Hook:** `wrap_tool_call`

Auto-captures results from search tools (patent_keyword_search, npl_search, semantic_patent_search, batch_*, citation tools). Extracts references, normalizes fields, and writes to:
- `/findings/auto/{source}_capture_{N}.json` — individual captures
- `/findings_auto_accumulator.json` — deduplicated master accumulator

**Why:** Safety net against context truncation. Even if a subagent forgets to call `save_round_findings`, the middleware captures results automatically.

### ② PatentTrackingMiddleware
**File:** `middleware/patent_tracking.py` | **Hook:** `wrap_tool_call`

Passive observer that tracks each patent through lifecycle checkpoints:
- DISCOVERED → PERSISTED → TRIAGED → FEATURE_MAPPED → REPORTED

At session end, backfills from filesystem artifacts and writes `/patent_statistics.md` with the full loss funnel (how many patents were found vs. how many made it into the final report).

### ③ FeatureConfirmationMiddleware
**File:** `middleware/feature_confirmation.py` | **Hook:** `modify_prompt` (system prompt injection)

**Enforces Gate 2.** Checks if `/features.md` exists (features defined) but user hasn't said "confirm" yet. If so, injects a STOP directive into the system prompt:

```
⛔ STOP: You MUST present the Feature Matrix and wait for user confirmation
BEFORE proceeding to research. DO NOT call task(). DO NOT delegate.
```

### ④ AutonomousResearchMiddleware
**File:** `middleware/autonomous_research.py` | **Hook:** `modify_prompt`

**Activates after Gate 2 confirmation.** Injects an autonomy directive that forbids the agent from asking the user any questions:

```
ABSOLUTE RULES:
1. Do NOT ask the user ANY questions
2. ALL CONTINUE/STOP decisions are YOURS ALONE
3. The ONLY thing the user sees next is the FINAL REPORT
```

### ⑤ ResearchContinuationMiddleware
**File:** `middleware/research_continuation.py` | **Hook:** `modify_prompt`

Detects when the orchestrator has received subagent results (ToolMessages from task() calls) but hasn't processed them (no think_tool or save_round_findings calls in between). If so, injects a mandatory next-steps directive:

```
MANDATORY NEXT STEPS:
1. PERSIST this round's findings (save_round_findings)
2. REFLECT using think_tool (Coverage Analysis)
3. DECIDE (CONTINUE or STOP)
4. IF CONTINUING — dispatch next round
```

Counts completed rounds from filesystem (`/findings/*_round_N.md` files) and message history. Respects `min_rounds` (2) and `max_rounds` (5).

### ⑥ CitationEnforcementMiddleware
**File:** `middleware/citation_enforcement.py` | **Hook:** `modify_prompt`

Reads `/findings_accumulator.json` to detect A-refs and coverage gaps. When both exist (Round 2+), and the orchestrator hasn't already delegated to citation-researcher, injects:

```
CITATION ANALYSIS REQUIRED:
A-refs available: [US10234567B2, EP9876543A1]
Features below STRONG: [F2, F3]
ACTION: Include citation-researcher in your parallel delegation
```

### ⑦ TelemetryMiddleware
**File:** `observability/telemetry.py` | **Hook:** `wrap_tool_call`

Measures every tool call: name, duration_ms, success/failure. Writes to `/telemetry.json`. In factory mode, creates per-thread `ResearchTelemetry` instances via `telemetry_factory`.

---

## 5. Subagent Specifications

All subagents are defined in `src/novelty_checker/subagents.yaml` and loaded by `load_subagents()`.

### Primary Research Subagents

| Subagent | Role | Search API | Query Syntax | Max Searches | Key Tools |
|----------|------|-----------|-------------|-------------|-----------|
| **patent-researcher** | Patent keyword search | Innography | `@(dwpi_title,dwpi_abstract) (term NEAR/5 term2)` | 10 | patent_keyword_search, batch_patent_search, batch_citation_search, think_tool, save_round_findings, get_all_findings, get_coverage_gaps |
| **npl-researcher** | Academic literature search | Web of Science | `TS=(topic) AND TI=(title)` | 8 | npl_search, batch_npl_search, think_tool, save_round_findings, get_all_findings, get_coverage_gaps |
| **semantic-researcher** | Concept-based semantic search | NGSP | Natural language gists (6 types: A-F) | 7 | semantic_patent_search, batch_semantic_search, think_tool, save_round_findings, get_all_findings, get_coverage_gaps |
| **citation-researcher** | Citation network expansion | Innography citations | Publication numbers of A-refs | 5 A-refs, 10 fetches | get_patent_citations, batch_citation_search, citation_chain_search, get_patent_details, triage_reference, map_features_to_reference, think_tool, save_round_findings, get_all_findings, get_coverage_gaps |

### Analysis & Synthesis Subagents

| Subagent | Role | Key Tools |
|----------|------|-----------|
| **coverage-analyst** | Post-round coverage assessment (INTERNAL only, never shown to user) | think_tool, aggregate_search_results, get_patent_details |
| **report-writer** | Final 11-section report synthesis | get_patent_details, get_all_findings, get_coverage_gaps, summarize_findings_for_report |

### Alternative Parallel Path Subagents

| Subagent | Strategy | Key Tools |
|----------|----------|-----------|
| **keyword-precision-searcher** | High-precision DWPI + tight proximity (ADJ/3-5) | patent_keyword_search, batch_patent_search, batch_unified_search, npl_search, think_tool |
| **semantic-recall-searcher** | High-recall via natural language gists | semantic_patent_search, batch_semantic_search, batch_unified_search, npl_search, think_tool |
| **structural-combo-searcher** | Multi-feature pairwise combination queries | patent_keyword_search, batch_patent_search, batch_unified_search, semantic_patent_search, npl_search, think_tool |

### Common Subagent Workflow

Every search subagent follows the **Recall → Search → Reflect → Decide** loop:

```
┌──────────────────────────────────────────┐
│ 0. RECALL: get_all_findings()            │  ← What's already found? What gaps?
│    Skip features already at STRONG       │
└──────────────────────┬───────────────────┘
                       ▼
┌──────────────────────────────────────────┐
│ 1. SEARCH: Execute query                 │  ← API-specific syntax
└──────────────────────┬───────────────────┘
                       ▼
┌──────────────────────────────────────────┐
│ 2. REFLECT: think_tool (MANDATORY)       │  ← Coverage update, gap analysis
│    "Search X of max N"                   │
└──────────────────────┬───────────────────┘
                       ▼
┌──────────────────────────────────────────┐
│ 3. DECIDE:                               │
│    Coverage met? → PERSIST + return       │
│    Gaps remain?  → back to step 1        │
│    Hit limit?    → PERSIST + return       │
└──────────────────────────────────────────┘
```

Before returning, every subagent **persists** findings to `/findings/{type}_round_{N}.md`.

---

## 6. Tool Ecosystem

### Search Tools (`src/tools/search.py`)

| Tool | API | Description |
|------|-----|-------------|
| `patent_keyword_search` | Innography | Single patent query with @(field) syntax |
| `batch_patent_search` | Innography | Multiple patent queries in parallel |
| `npl_search` | Web of Science | Single academic literature query |
| `batch_npl_search` | Web of Science | Multiple NPL queries in parallel |
| `semantic_patent_search` | NGSP | Single natural language semantic query |
| `batch_semantic_search` | NGSP | Multiple semantic queries in parallel |
| `batch_unified_search` | All three | Patent + NPL + semantic in ONE call (most efficient) |
| `get_patent_citations` | Innography | Forward + backward citations for a patent |
| `batch_citation_search` | Innography | Multiple citation lookups in parallel |
| `citation_chain_search` | Innography | Multi-hop citation chain expansion |
| `get_patent_details` | Innography | Full patent content (abstract, claims, DWPI) |

### Analysis Tools (`src/tools/analysis.py`)

| Tool | Description |
|------|-------------|
| `triage_reference` | Assign A/B/C relevance label to a reference |
| `map_features_to_reference` | Generate Y/Y1/N feature mapping for a reference |
| `aggregate_search_results` | Deduplicate and merge results from multiple sources |

### Findings Tools (`src/tools/findings.py`)

| Tool | Description |
|------|-------------|
| `save_round_findings` | Persist a round's findings to `/findings/` + accumulator JSON |
| `get_all_findings` | Retrieve all accumulated findings from all prior rounds |
| `get_coverage_gaps` | Identify features below target coverage with strategy suggestions |
| `summarize_findings_for_report` | Prepare consolidated findings for report synthesis |

### Reflection Tool (`src/tools/reflection.py`)

| Tool | Description |
|------|-------------|
| `think_tool` | Structured reasoning scratchpad. MANDATORY after every search. |

### Content Tools

| Tool | Description |
|------|-------------|
| `read_file` | Read from session filesystem |
| `write_file` | Write to session filesystem (creates parents automatically) |
| `edit_file` | Edit existing file in session filesystem |

---

## 7. Complete Data Flow Walkthrough

This section traces a single customer request from input to final report, showing every stage, middleware interaction, subagent delegation, and file write.

### The Customer's Request

> *"A dual-worm gear transmission for smartphone cameras that uses two worm gears in series with an intermediate adapter gear to achieve compact packaging within 10-13mm thickness."*

---

### Stage 1 — Scoping (Gate 1)

```
Customer ──── invention description ────▶ Orchestrator
```

**What happens:**

1. **Message enters the graph.** The customer's text arrives as a `HumanMessage` and is added to the LangGraph state's `messages` list.

2. **LLM call with full prompt.** The orchestrator LLM sees:
   - AGENTS.md (base system prompt with stage pipeline)
   - NOVELTY_WORKFLOW_INSTRUCTIONS
   - SEARCH_DELEGATION_INSTRUCTIONS
   - Any active skill (scoping/SKILL.md is loaded first)

3. **Middleware check (pre-LLM).** All 7 middleware run their `modify_prompt` hooks:
   - ③ FeatureConfirmationMiddleware: No `/features.md` exists yet → no action
   - ④ AutonomousResearchMiddleware: Gate 2 not confirmed → no action
   - ⑤⑥ Continuation/Citation: Research not active → no action

4. **Orchestrator responds.** Creates a todo list via `write_todos`, then asks clarifying questions:
   - What specific problem does the dual-worm gear solve vs. existing single-worm designs?
   - What are the target specs (gear ratio, torque, speed)?
   - Are both worm gears identical or different pitch/diameter?

5. **Customer answers.** Provides clarifications.

6. **Orchestrator writes scope.** Calls `write_file("/scope.md", ...)` with the confirmed scope:

   ```markdown
   # Invention Scope
   ## Customer Idea
   A dual-worm gear transmission for smartphone cameras...
   ## Clarifications
   - Series cascade (not parallel)
   - Intermediate adapter gear between the two worm stages
   - Target: 10-13mm total stack height
   ## Confirmed Scope
   [Final scoped description]
   ```

7. **Gate 1 presented.** Orchestrator outputs a Scope Summary table and asks: *"Does this accurately capture your invention? Reply 'confirm' to proceed."*

8. **Customer confirms.** Replies "confirm".

```
Session directory after Stage 1:
sessions/{id}/
└── scope.md              ← Scope definition
```

---

### Stage 2 — Feature Definition (Gate 2)

```
Customer ── "confirm" ──▶ Orchestrator ──▶ Feature decomposition
```

**What happens:**

1. **Orchestrator decomposes the invention** into 3-7 searchable features:

   | ID | Feature Name | Core? | Keywords |
   |----|-------------|-------|----------|
   | F1 | Dual Worm Gear Cascade | Y | worm gear, dual worm, series worm, cascade gear |
   | F2 | Intermediate Adapter Gear | Y | adapter gear, intermediate gear, coupling gear |
   | F3 | Compact Packaging (10-13mm) | Y | compact, miniature, thin profile, smartphone thickness |
   | F4 | Camera Lens Actuation | Y | lens actuator, autofocus, camera module |
   | F5 | Gear Ratio Optimization | N | gear ratio, transmission ratio, speed reduction |

2. **Orchestrator writes features.** Calls `write_file("/features.md", ...)`:

   ```markdown
   # Features Definition
   | ID | Name | Description | Core? | Keywords |
   |----|------|-------------|-------|----------|
   | F1 | Dual Worm Gear Cascade | Two worm gears in series | Y | worm gear, dual worm... |
   ...
   ```

3. **Gate 2 presented.** Orchestrator outputs the Feature Matrix table followed by:

   ```
   🛑 CONFIRMATION REQUIRED — Stage 2 Gate
   Please reply "Confirm" to proceed or "Edit: [changes]" to revise.
   ```

4. **Middleware enforcement.** On the next LLM call (before customer responds), if the orchestrator tries to proceed:
   - ③ **FeatureConfirmationMiddleware** detects `/features.md` exists but no "confirm" in message history → injects STOP directive → orchestrator cannot call task()

5. **Customer confirms.** Replies "Confirm".

6. **Post-confirmation middleware activation:**
   - ③ FeatureConfirmationMiddleware: Sees "confirm" in messages → gate passes, no injection
   - ④ **AutonomousResearchMiddleware**: Detects `/features.md` + confirmed → **activates** → injects autonomy directive on every subsequent LLM call

```
Session directory after Stage 2:
sessions/{id}/
├── scope.md
└── features.md           ← Feature definitions
```

---

### Stage 3 — Research Loop (Fully Autonomous)

After Gate 2 confirmation, the orchestrator enters a fully autonomous research loop. No further user interaction occurs until the final report.

#### Round 1: Initial Comprehensive Search

```
Orchestrator (ONE AI message)
    │
    ├── get_all_findings()                    ← RECALL (no prior findings)
    ├── task(patent-researcher, "...")         ← DELEGATE
    ├── task(npl-researcher, "...")            ← DELEGATE
    └── task(semantic-researcher, "...")       ← DELEGATE
```

**Step 0+1 — RECALL & DELEGATE (single response):**

The orchestrator emits `get_all_findings()` and all three `task()` calls in ONE AI message. This is critical — the deepagents framework only runs subagents concurrently when task() calls appear in the same message.

Each task description includes FULL feature context (IDs, names, keywords, descriptions, coverage status = "all at NONE"), because subagents have NO access to conversation history.

**Middleware during delegation:**
- ④ AutonomousResearchMiddleware: Active — prevents any user-facing questions
- ⑤ ResearchContinuationMiddleware: Not triggered yet (no received results)
- ⑥ CitationEnforcementMiddleware: No A-refs exist → no citation directive

**Subagent execution (parallel):**

Each subagent runs independently with its own tools:

```
┌─────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────────┐
│   patent-researcher     │  │    npl-researcher       │  │  semantic-researcher    │
│                         │  │                         │  │                         │
│ 1. get_all_findings()   │  │ 1. get_all_findings()   │  │ 1. get_all_findings()   │
│ 2. batch_patent_search  │  │ 2. batch_npl_search     │  │ 2. batch_semantic_search│
│    @(dwpi_title) worm   │  │    TS=(worm gear AND    │  │    "A dual worm gear    │
│    NEAR/5 gear          │  │    camera)              │  │    transmission for     │
│ 3. think_tool           │  │ 3. think_tool           │  │    compact cameras"     │
│    [Coverage Analysis]  │  │    [Coverage Analysis]  │  │ 3. think_tool           │
│ 4. patent_keyword_search│  │ 4. npl_search           │  │    [Vocab Discovery]    │
│    @(dwpi_novelty) dual │  │    TI=(miniature AND    │  │ 4. semantic_patent_srch │
│    worm                 │  │    actuator)            │  │    "compact gear train  │
│ 5. think_tool           │  │ 5. think_tool           │  │    for mobile lens"     │
│    [Decide: return]     │  │    [Decide: return]     │  │ 5. think_tool           │
│ 6. write_file           │  │ 6. write_file           │  │    [Decide: return]     │
│    /findings/patent_    │  │    /findings/npl_       │  │ 6. write_file           │
│    round_1.md           │  │    round_1.md           │  │    /findings/semantic_  │
│                         │  │                         │  │    round_1.md           │
└─────────────────────────┘  └─────────────────────────┘  └─────────────────────────┘
```

**Middleware during subagent tool calls:**
- ① FindingsPersistenceMiddleware: Intercepts each search tool result → extracts references → writes to `/findings_auto_accumulator.json`
- ② PatentTrackingMiddleware: Records DISCOVERED checkpoint for each patent found
- ⑦ TelemetryMiddleware: Logs tool name, duration, success for each call

**Step 2 — RECEIVE:**

All three subagents return their findings as ToolMessages. The orchestrator sees structured markdown summaries with reference tables, coverage status, and gap recommendations.

**Step 3 — PERSIST:**

The orchestrator calls `save_round_findings(round_number=1, ...)` to persist the consolidated round findings to the accumulator.

**Step 4 — REFLECT:**

The orchestrator calls `think_tool` with the Coverage Analysis template:

```markdown
### Coverage Analysis (Round 1 of 5)

| Feature | Core? | A-Refs | B-Refs | Coverage Level | Gap? |
|---------|-------|--------|--------|----------------|------|
| F1 | Y | 1 | 2 | MODERATE ⚠️ | YES |
| F2 | Y | 0 | 1 | WEAK ❌ | YES |
| F3 | Y | 0 | 2 | MODERATE ⚠️ | YES |
| F4 | Y | 1 | 3 | STRONG ✅ | NO |
| F5 | N | 0 | 1 | WEAK | YES |

Core at STRONG: 1/4 (25%) ← Target: 100%
Overall at STRONG: 1/5 (20%) ← Target: 70%

Decision: CONTINUE — F1, F2, F3 need more coverage
```

**Middleware after REFLECT:**
- ⑤ **ResearchContinuationMiddleware**: Detects task results were received AND processing happened (think_tool called) → satisfied, no injection needed

**Step 5 — DECIDE:**

Coverage is below target → CONTINUE to Round 2.

```
Session directory after Round 1:
sessions/{id}/
├── scope.md
├── features.md
├── findings/
│   ├── patent_round_1.md         ← Patent researcher output
│   ├── npl_round_1.md            ← NPL researcher output
│   └── semantic_round_1.md       ← Semantic researcher output
├── findings_auto_accumulator.json ← Auto-captured by middleware
└── telemetry.json                ← Tool call metrics
```

#### Round 2: Gap-Filling + Citation Analysis

```
Orchestrator (ONE AI message)
    │
    ├── get_all_findings()                         ← RECALL (Round 1 findings)
    ├── task(patent-researcher, "Focus on F2...")   ← Gap-filling
    ├── task(npl-researcher, "Focus on F1,F3...")   ← Gap-filling
    ├── task(semantic-researcher, "Type F...")       ← Cross-pollination
    └── task(citation-researcher, "Analyze         ← NEW: citation network
    │        JP2007171504A forward/backward...")     analysis of A-refs
```

**Key difference in Round 2:**
- ⑥ **CitationEnforcementMiddleware**: Reads accumulator, finds A-refs + coverage gaps → injects directive: *"Include citation-researcher with A-ref JP2007171504A, focus on F2 and F3"*
- The orchestrator now dispatches 4 subagents (patent + NPL + semantic + citation)
- Semantic-researcher uses **Type F queries** (A-ref titles as search gists) for cross-pollination

**Citation-researcher workflow:**

```
1. RECALL:  get_all_findings() → see existing coverage
2. CITE:    get_patent_citations("JP2007171504A") → 15 forward + 22 backward
3. SCAN:    Review titles, shortlist 6 promising candidates
4. FETCH:   get_patent_details() for each → full abstract + claims
5. REFLECT: think_tool → which citations are A/B-level?
6. TRIAGE:  triage_reference() → assign A/B/C labels
            map_features_to_reference() → Y/Y1/N per feature
7. PERSIST: save_round_findings → /findings/citations_round_2.md
```

**After Round 2 REFLECT:**

```markdown
### Coverage Analysis (Round 2 of 5)

| Feature | Core? | A-Refs | B-Refs | Coverage Level | Gap? |
|---------|-------|--------|--------|----------------|------|
| F1 | Y | 2 | 3 | STRONG ✅ | NO |
| F2 | Y | 1 | 2 | STRONG ✅ | NO |
| F3 | Y | 1 | 3 | STRONG ✅ | NO |
| F4 | Y | 1 | 4 | STRONG ✅ | NO |
| F5 | N | 0 | 2 | MODERATE ⚠️ | NO (non-core) |

Core at STRONG: 4/4 (100%) ✅
Overall at STRONG: 4/5 (80%) ✅ (above 70% target)

Decision: STOP — All core features at STRONG, overall 80%
```

**DECIDE: STOP.** Coverage target met. Proceed to report synthesis.

```
Session directory after Round 2:
sessions/{id}/
├── scope.md
├── features.md
├── findings/
│   ├── patent_round_1.md
│   ├── npl_round_1.md
│   ├── semantic_round_1.md
│   ├── patent_round_2.md
│   ├── npl_round_2.md
│   ├── semantic_round_2.md
│   └── citations_round_2.md      ← Citation analysis
├── references.md                  ← Consolidated reference list
├── findings_auto_accumulator.json
├── patent_statistics.md           ← Loss funnel
└── telemetry.json
```

---

### Stage 4 — Report Synthesis

```
Orchestrator ── task(report-writer, "...") ──▶ report-writer subagent
```

**What happens:**

1. **Orchestrator delegates** to report-writer with full context: all features, coverage summary, and file paths.

2. **report-writer's first action:** `get_all_findings()` — loads ALL accumulated findings from every round. Verifies A/B reference counts match what the orchestrator reported.

3. **Content lookup:** For any references missing full bibliographic details, calls `get_patent_details(pub_number)` to fetch abstracts, claims, DWPI fields.

4. **Report generation.** Synthesizes the 11-section report:

   | # | Section | Content |
   |---|---------|---------|
   | 1 | Executive Summary | Key finding, risk assessment, gap analysis |
   | 2 | Scope | Table: objective, in-scope, out-of-scope |
   | 3 | Feature Plan | Confirmed features F1-F5 with descriptions |
   | 4 | **Feature Matrix** | ALL A/B refs as rows with Y/Y1/N per feature |
   | 5 | Peripherally Related | C-label references |
   | 6 | Patents Record View | Per-patent bibliographic tables with hyperlinks |
   | 7 | NPL Record View | Per-paper bibliographic tables |
   | 8 | Transactional Summary | Client-facing search overview |
   | 9 | Landscape Overview | Technology classes, assignees, density |
   | 10 | Search Traceability | Full results list + search log with Discovery Method |
   | 11 | Next Steps | Recommendations, monitoring, quality assessment |

5. **Output:** Report-writer returns the full report text to the orchestrator.

6. **Orchestrator writes and delivers:**
   - Calls `write_file("/report.md", full_report)` to persist
   - Outputs the ENTIRE report content in its response message to the user
   - Marks all todos as completed

```
Final session directory:
sessions/{id}/
├── scope.md
├── features.md
├── findings/
│   ├── patent_round_1.md
│   ├── npl_round_1.md
│   ├── semantic_round_1.md
│   ├── patent_round_2.md
│   ├── npl_round_2.md
│   ├── semantic_round_2.md
│   └── citations_round_2.md
├── references.md
├── findings_auto_accumulator.json
├── patent_statistics.md
├── telemetry.json
└── report.md                     ← Final 11-section report
```

---

## 8. Session Storage Layout

```
sessions/{session_id}/
│
├── scope.md                          # Gate 1 output: invention scope definition
├── features.md                       # Gate 2 output: feature decomposition table
│
├── findings/                         # Research round outputs
│   ├── patent_round_1.md             # Patent-researcher Round 1 findings
│   ├── npl_round_1.md                # NPL-researcher Round 1 findings
│   ├── semantic_round_1.md           # Semantic-researcher Round 1 findings
│   ├── patent_round_2.md             # Patent-researcher Round 2 (gap-filling)
│   ├── npl_round_2.md                # NPL-researcher Round 2
│   ├── semantic_round_2.md           # Semantic-researcher Round 2
│   ├── citations_round_2.md          # Citation-researcher Round 2
│   └── auto/                         # Auto-captured by FindingsPersistenceMiddleware
│       ├── patent_capture_1.json
│       ├── npl_capture_1.json
│       └── semantic_capture_1.json
│
├── findings_auto_accumulator.json    # Deduplicated master accumulator (auto)
├── references.md                     # Consolidated reference list
│
├── report.md                         # Final 11-section novelty report
├── patent_statistics.md              # Patent loss funnel (discovered→reported)
└── telemetry.json                    # Tool call metrics (name, duration, success)
```

---

## 9. Gate Mechanism Detail

The system has exactly **two mandatory user gates**. These are the only points where the agent pauses for human input.

### Gate 1: Scope Confirmation

| Aspect | Detail |
|--------|--------|
| **When** | After Stage 1 (scoping conversation complete) |
| **Trigger** | Orchestrator presents "Scope Summary" table |
| **User Action** | Reply "confirm" or provide corrections |
| **Artifact** | `/scope.md` written before gate presentation |
| **Middleware** | None enforces this gate (prompt-driven only) |
| **After Confirmation** | Orchestrator proceeds to Stage 2 (Feature Definition) |

### Gate 2: Feature Confirmation

| Aspect | Detail |
|--------|--------|
| **When** | After Stage 2 (features decomposed) |
| **Trigger** | Orchestrator presents Feature Matrix table + "CONFIRMATION REQUIRED" |
| **User Action** | Reply "Confirm" or "Edit: [changes]" |
| **Artifact** | `/features.md` written before gate presentation |
| **Middleware** | **FeatureConfirmationMiddleware** — blocks research if features exist but no confirmation |
| **After Confirmation** | **AutonomousResearchMiddleware** activates — agent enters fully autonomous mode. No further user interaction until final report. |

### Gate Transition Diagram

```
                    ┌──────────┐
                    │  START   │
                    └────┬─────┘
                         ▼
                 ┌───────────────┐
                 │  Stage 1:     │
                 │  Scoping      │
                 └───────┬───────┘
                         ▼
              ┌─────────────────────┐
              │  GATE 1: Scope      │◀─── "Edit" loops back
              │  Confirmation       │
              └─────────┬───────────┘
                        │ "Confirm"
                        ▼
                 ┌───────────────┐
                 │  Stage 2:     │
                 │  Features     │
                 └───────┬───────┘
                         ▼
              ┌─────────────────────┐
              │  GATE 2: Feature    │◀─── "Edit" loops back
              │  Confirmation       │
              │                     │
              │  ③ Middleware blocks │
              │  research until     │
              │  "Confirm" received │
              └─────────┬───────────┘
                        │ "Confirm"
                        ▼
              ┌─────────────────────┐
              │  ④ AUTONOMOUS MODE  │
              │  ACTIVATED          │
              │                     │
              │  No more user       │
              │  interaction until  │
              │  final report       │
              └─────────┬───────────┘
                        ▼
                 ┌───────────────┐
                 │  Stage 3:     │
                 │  Research     │──── ⑤⑥ Middleware enforce
                 │  Loop (1-5    │     loop continuation
                 │  rounds)      │     and citation analysis
                 └───────┬───────┘
                         ▼
                 ┌───────────────┐
                 │  Stage 4:     │
                 │  Report       │
                 │  Synthesis    │
                 └───────┬───────┘
                         ▼
                 ┌───────────────┐
                 │  FINAL REPORT │
                 │  delivered    │
                 │  to customer  │
                 └───────────────┘
```

---

## 10. Key Design Patterns

### Coordinator Pattern
The orchestrator never executes searches directly. It plans, delegates to specialized subagents, receives results, reflects on coverage, and decides whether to continue or stop. This separation allows domain-specific prompts and tools for each search API.

### Parallel Dispatch Rule
All `task()` calls MUST appear in a single AI message. The deepagents framework only runs subagents concurrently when they appear in the same response. Sequential dispatch (one task per turn) is 3-4x slower.

### Context Isolation
Subagents have NO access to the orchestrator's conversation history. Every task description must include: all feature definitions, current coverage status, gap-filling focus, and specific search guidance. Failing to provide full context produces poor search results.

### Vocabulary Feedback Loop
Semantic search discovers alternative terminology that keyword searches miss:

```
Round 1: Keyword finds "worm gear transmission"
         Semantic finds "helical drive mechanism" (same concept, different words)

Round 2: "helical drive mechanism" added to keyword queries
         → Finds patents invisible to original vocabulary
```

The semantic-researcher uses 6 query types (A-F) to maximize vocabulary discovery, with Type F (cross-pollination) using A-ref titles as new semantic queries.

### Findings Persistence (Memory Loss Prevention)
Long research sessions risk context truncation. The system uses a belt-and-suspenders approach:
1. **Subagent-level:** Each subagent writes findings to `/findings/{type}_round_{N}.md` before returning
2. **Middleware-level:** FindingsPersistenceMiddleware auto-captures every search tool result
3. **Orchestrator-level:** `save_round_findings()` persists consolidated data to the accumulator
4. **Recall step:** `get_all_findings()` called at the start of each round to reload all prior findings

### Coverage-Based Adaptive Stopping
The research loop doesn't blindly iterate to max rounds. It uses multi-signal stopping:

| Signal | Threshold | Action |
|--------|-----------|--------|
| Coverage target met | Core features STRONG + overall >=70% | STOP |
| Diminishing returns | <2 net new refs for 2 consecutive rounds | STOP |
| Feature saturation | All features at SATURATED | STOP |
| Query exhaustion | All query variations tried | STOP |
| Max iterations | 5 rounds | STOP (hard limit) |

---

## 11. REST API Layer

The system exposes a **FastAPI REST API** (`server.py`) for structured frontend integration. Every response uses the `APIResponse` envelope so the frontend always knows what stage the agent is in and what data to render.

### Entry Point: `server.py`

```python
graph, session_id = create_deep_agent(
    model=get_llm(),
    checkpointer=None,
    use_custom_state=True,       # Full state reducers for production
    use_backend_factory=True,    # Per-thread session isolation
    emit_structured_json=True,   # LLM emits json:questions/json:features blocks
)
```

Key differences from Studio mode:
- `use_custom_state=True` — enables parallel-safe reducers (Studio disables this due to MockValSer)
- `emit_structured_json=True` — appends instructions for the LLM to emit `json:questions` and `json:features` fenced blocks alongside natural text
- CORS middleware configurable via `CORS_ORIGINS` environment variable

### Endpoints

| Method | Path | Description | Blocking? |
|--------|------|-------------|-----------|
| `POST` | `/chat` | Send a message, receive structured response | Yes (5-15 min during research) |
| `GET` | `/threads/{thread_id}/state` | Poll current state without invoking agent | No |
| `GET` | `/threads/{thread_id}/report` | Download final report markdown | No |
| `GET` | `/threads/{thread_id}/token-usage` | Token usage breakdown by stage/agent | No |
| `GET` | `/health` | Health check | No |

### Response Envelope: `APIResponse`

```
┌──────────────────────────────────────────────┐
│ APIResponse                                  │
├──────────────────────────────────────────────┤
│ thread_id:    str                            │
│ stage:        "scoping"|"features"|          │
│               "researching"|"complete"       │
│ status:       "awaiting_input"|"processing"| │
│               "done"|"error"                 │
│ stage_data:   { ... }  ← stage-specific      │
│ raw_response: str      ← AI text fallback    │
│ token_usage:  { ... }  ← optional            │
│ error:        str|null                       │
└──────────────────────────────────────────────┘
```

### Stage-Specific Data Models

| Stage | Model | Key Fields |
|-------|-------|------------|
| `scoping` | `ScopingData` | `questions: list[ClarifyingQuestion]`, `scope_summary`, `is_confirmation_prompt` |
| `features` | `FeaturesData` | `features: list[FeatureItem]`, `is_confirmation_prompt` |
| `researching` | `ResearchingData` | `progress: ResearchProgress` (current_round, coverage_pct, references_found) |
| `complete` | `CompletionData` | `report_markdown`, `features`, `references`, `coverage_summary`, `overall_coverage_pct` |

### Response Parsing Pipeline

The `response_parser.py` module extracts structured data from the LLM's free-form text using a three-tier fallback strategy:

```
AI Text Response
       │
       ▼
┌──────────────────────────────────┐
│ 1. JSON Block Extraction         │  Parse ```json:questions``` and
│    (Primary)                     │  ```json:features``` fenced blocks
└──────────────┬───────────────────┘
               │ No blocks found?
               ▼
┌──────────────────────────────────┐
│ 2. Heuristic Regex Parsing       │  Numbered questions with defaults,
│    (Fallback)                    │  markdown feature tables
└──────────────┬───────────────────┘
               │ No matches?
               ▼
┌──────────────────────────────────┐
│ 3. Graph State Extraction        │  Read features/references from
│    (Last Resort)                 │  the LangGraph state snapshot
└──────────────────────────────────┘
```

### Stage Detection

The `stage_detector.py` module determines the current stage by probing the filesystem for artifacts:

| Artifact Present | Detected Stage |
|-----------------|----------------|
| Nothing | `scoping` |
| `/scope.md` | `scoping` (waiting for confirmation) or `features` |
| `/features.md` | `features` or `researching` |
| `/findings_accumulator.json` with rounds | `researching` |
| `/final_report.md` | `complete` |

Falls back to scanning the message history for key markers when filesystem detection is ambiguous.

### Module Structure

```
src/novelty_checker/api/
├── __init__.py
├── schemas.py           # Pydantic request/response models (APIResponse, stage data)
├── endpoints.py         # FastAPI router (POST /chat, GET /threads/*, GET /health)
├── response_parser.py   # JSON block + heuristic + state extraction
├── stage_detector.py    # Filesystem artifact probing + message scanning
└── telemetry_reader.py  # Concurrent-read-safe JSON telemetry parsing
```

---

## 12. State Management

### `DeepAgentState` (`state.py`)

The graph state is a `TypedDict` with channels grouped by workflow stage. Three channels use **state reducers** for safe parallel subagent updates:

```python
class DeepAgentState(TypedDict):
    # Core
    messages: Annotated[list[AnyMessage], add_messages]

    # Stage 1: Scoping
    customer_idea: NotRequired[str]
    scope_markdown: NotRequired[str]
    scope_confirmed: NotRequired[bool]

    # Stage 2: Features
    features: NotRequired[list[Feature]]
    features_confirmed: NotRequired[bool]

    # Stages 3-4: Search (with reducers)
    references: Annotated[list[Reference], merge_references]
    findings_accumulator: Annotated[FindingsAccumulator, merge_findings_accumulator]

    # Stage 5: Screening (with reducer)
    coverage: Annotated[list[CoverageStatus], merge_coverage]
    overall_coverage: NotRequired[float]

    # Stage 6: Report
    report_markdown: NotRequired[str]

    # Pipeline Control
    current_stage: NotRequired[Literal["scoping", "feature_definition", ...]]
    remaining_steps: NotRequired[int]
    is_last_step: NotRequired[bool]
```

### State Reducers

When multiple subagents complete concurrently, their state updates must be merged safely. Three custom reducers handle this:

| Reducer | Channel | Strategy |
|---------|---------|----------|
| `merge_references` | `references` | Deduplicates by `ref_id`; merges `discovery_method` (e.g., `"keyword,semantic"`) |
| `merge_findings_accumulator` | `findings_accumulator` | Appends rounds chronologically; deduplicates `all_references`; merges vocabulary by term |
| `merge_coverage` | `coverage` | Takes latest `CoverageStatus` per `feature_id` (new values override) |

### Two Operational State Modes

| Flag | Mode | Reducers | Use Case |
|------|------|----------|----------|
| `use_custom_state=True` | Full state | All reducers active | `server.py` (production API) |
| `use_custom_state=False` | Default state | Reducers disabled; channels stripped | `studio.py` (LangGraph Studio — avoids MockValSer/Pydantic schema errors) |

### Key Type Definitions

The state module also defines the core domain types used across the system:

| Type | Description |
|------|-------------|
| `Feature` | Extracted feature (id, name, description, keywords, is_core, priority) |
| `Reference` | Patent or NPL reference (ref_id, title, source, triage_label, feature_coverage, discovery_method, ...) |
| `CoverageStatus` | Per-feature coverage (feature_id, level, a_refs, b_refs, c_refs) |
| `FindingsAccumulator` | Master structure: rounds, all_references, all_vocabulary, final_coverage, stop_reason |
| `RoundFindings` | Single round: patent/npl/semantic findings, coverage snapshot, vocabulary, gap features |
| `VocabularyTerm` | Discovered term (term, source_ref, relevance, discovered_in_round) |
| `FeatureMatrixRow` | Report Section 4 row (publication_number, relevance, feature_coverage, ...) |

---

## 13. Observability & Telemetry

### ResearchTelemetry (`observability/telemetry.py`)

Tracks per-agent LLM token usage, per-stage cost estimation, tool call timing, and execution spans.

**Data Classes:**

| Class | Fields | Purpose |
|-------|--------|---------|
| `ToolCallMetric` | tool_name, timestamp, duration_ms, success, error | Individual tool call timing |
| `ModelCallMetric` | agent_name, input_tokens, output_tokens, cost_usd, stage | LLM call token tracking |
| `RoundMetric` | round_number, start_time, end_time, coverage_pct, new/total refs | Research iteration metrics |
| `AgentTokenSummary` | Cumulative tokens per agent + estimated cost | Cost attribution |
| `StageTokenSummary` | Cumulative tokens per stage | Stage-level cost breakdown |

**Workflow Stage Constants:**

```python
STAGE_SCOPING  = "stage_1_scoping"
STAGE_FEATURES = "stage_2_features"
STAGE_RESEARCH = "stage_3_research"
STAGE_REPORT   = "stage_4_report"

# Subagent → stage mapping
_SUBAGENT_STAGE_MAP = {
    "patent-researcher": STAGE_RESEARCH,
    "npl-researcher": STAGE_RESEARCH,
    "semantic-researcher": STAGE_RESEARCH,
    "citation-researcher": STAGE_RESEARCH,
    "report-writer": STAGE_REPORT,
    ...
}
```

**Model Pricing (per 1M tokens):**

| Model | Input | Output |
|-------|-------|--------|
| GPT-5 / azure/gpt-5 | $2.00 | $8.00 |
| GPT-4o / azure/gpt-4o | $2.50 | $10.00 |
| Fallback (any other) | $3.00 | $12.00 |

Overridable via `TOKEN_PRICING_JSON` environment variable.

### TelemetryMiddleware

Hooks into every LLM call (`wrap_model_call`) and tool call (`wrap_tool_call`) to collect metrics automatically.

**Dual-mode support:**
- **Static mode** (CLI): Single `ResearchTelemetry` instance passed at init
- **Factory mode** (Studio/API): `telemetry_factory(thread_id)` creates per-thread instances

**Output:** Writes `/telemetry.json` to the session directory with per-agent, per-stage, and per-tool breakdowns.

### PatentTracker (`observability/patent_tracker.py`)

Tracks every patent through a 5-checkpoint lifecycle funnel:

```
DISCOVERED ──▶ PERSISTED ──▶ TRIAGED ──▶ FEATURE_MAPPED ──▶ REPORTED
  (search)      (findings)    (A/B/C)      (Y/Y1/N)         (report)
```

**How events are recorded:**

| Checkpoint | Source |
|------------|--------|
| DISCOVERED | Search tool results (auto by middleware) |
| PERSISTED | `save_round_findings` calls |
| TRIAGED | `triage_reference` calls |
| FEATURE_MAPPED | `map_features_to_reference` calls |
| REPORTED | Backfilled from final report's Feature Matrix |

**Backfill at session end:** Since the orchestrator middleware cannot observe subagent tool calls directly, `PatentTrackingMiddleware` performs a filesystem backfill — parsing all findings markdown files, the accumulator JSON, and the final report to reconstruct the full funnel.

**Output:**
- `/patent_statistics.json` — structured funnel data
- `/patent_statistics.md` — human-readable loss funnel report

This is an **internal QA artifact** and does not appear in the client-facing report.

### ContentFilterMiddleware (`middleware/content_filter.py`)

Catches Azure OpenAI content policy violations (`ContentPolicyViolationError`). Returns a synthetic AIMessage (no tool_calls) causing the subagent to terminate gracefully rather than crash.

---

## 14. Configuration

### Settings (`src/config/settings.py`)

Uses `pydantic-settings` for type-safe environment variable loading from `.env`:

```python
class Settings(BaseSettings):
    # Innography (Patent Search)
    innography_user_name: Optional[str]
    innography_user_secret: Optional[str]
    innography_user_token: Optional[str]
    innography_token_url: str          # default: staging endpoint
    innography_services_url: str       # default: staging endpoint

    # Web of Science (NPL)
    wos_api_key: Optional[str]
    wos_endpoint: str                  # default: clarivate endpoint

    # NGSP (Semantic)
    clarivate_ngsp_api_key: Optional[str]

    # Azure OpenAI
    azure_openai_api_key: Optional[str]
    azure_openai_endpoint: Optional[str]
    azure_openai_api_version: str      # default: "2024-02-15-preview"
    azure_openai_deployment_name: str  # default: "gpt-4o"

    # Google Gemini
    google_api_key: Optional[str]

    # Query Refinement
    enable_query_refinement_agent: bool  # default: True
    auto_refine_on_zero_results: bool    # default: True
    max_refinement_attempts: int         # default: 2
```

**Helper functions:** `is_innography_configured()`, `is_wos_configured()`, `is_ngsp_configured()`, `get_config_status()`

### LLM Configuration (`src/config/llm.py`)

Azure OpenAI via LiteLLM with GPT-5 awareness:

| Setting | Default | GPT-5 Override |
|---------|---------|----------------|
| Timeout | 600s (10 min) | 900s (15 min) |
| Max retries | 3 | 3 |
| `litellm.drop_params` | `True` | `True` |
| Temperature override | None | Optional via `AZURE_FORCE_TEMPERATURE_1` |

Returns `ChatLiteLLM` instances compatible with LangChain and deepagents.

### Environment Variables

| Variable | Purpose | Required | Default |
|----------|---------|----------|---------|
| `AZURE_OPENAI_API_KEY` | Azure LLM authentication | Yes | — |
| `AZURE_OPENAI_ENDPOINT` | Azure API endpoint URL | Yes | — |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Model deployment name | No | `gpt-5` |
| `AZURE_OPENAI_API_VERSION` | Azure API version | No | `2024-02-15-preview` |
| `AZURE_FORCE_TEMPERATURE_1` | Force temperature=1 | No | `false` |
| `LLM_TIMEOUT` | Model call timeout (seconds) | No | `900` (GPT-5) / `600` |
| `LLM_MAX_RETRIES` | Retry count for transient errors | No | `3` |
| `TOKEN_PRICING_JSON` | Custom pricing file path | No | Uses defaults |
| `INNOGRAPHY_USER_NAME` | Innography API username | For patent search | — |
| `INNOGRAPHY_USER_SECRET` | Innography API secret | For patent search | — |
| `INNOGRAPHY_USER_TOKEN` | Innography API token | For patent search | — |
| `INNOGRAPHY_TOKEN_URL` | Innography token endpoint | No | Staging URL |
| `INNOGRAPHY_SERVICES_URL` | Innography services endpoint | No | Staging URL |
| `WOS_API_KEY` | Web of Science API key | For NPL search | — |
| `WOS_ENDPOINT` | Web of Science endpoint | No | Clarivate URL |
| `CLARIVATE_NGSP_API_KEY` | NGSP API key | For semantic search | — |
| `GOOGLE_API_KEY` | Google Gemini API key | No | — |
| `ENABLE_QUERY_REFINEMENT_AGENT` | Enable auto query refinement | No | `true` |
| `AUTO_REFINE_ON_ZERO_RESULTS` | Auto-refine on empty results | No | `true` |
| `MAX_REFINEMENT_ATTEMPTS` | Max refinement retries | No | `2` |
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated) | No | `http://localhost:3000` |

---

## 15. Project Structure

```
langgraph_agent/
│
├── studio.py                              # LangGraph Studio entry point (factory mode)
├── server.py                              # FastAPI REST API entry point
├── pyproject.toml                         # Dependencies and build config
├── .env                                   # API credentials (not committed)
│
├── src/
│   ├── config/
│   │   ├── settings.py                    # Pydantic BaseSettings (env var loading)
│   │   └── llm.py                         # Azure OpenAI + LiteLLM wrapper
│   │
│   ├── novelty_checker/
│   │   ├── deep_agent.py                  # Graph factory: create_deep_agent()
│   │   ├── state.py                       # DeepAgentState + reducers + domain types
│   │   ├── prompts.py                     # Orchestrator + subagent instructions
│   │   ├── backend_factory.py             # ThreadAwareBackendFactory (per-thread isolation)
│   │   ├── main.py                        # CLI entry point
│   │   ├── eval_runner.py                 # E2E evaluation runner
│   │   │
│   │   ├── api/                           # REST API layer
│   │   │   ├── schemas.py                 # APIResponse, ChatRequest, stage data models
│   │   │   ├── endpoints.py               # FastAPI router (POST /chat, GET /threads/*)
│   │   │   ├── response_parser.py         # JSON block + heuristic + state extraction
│   │   │   ├── stage_detector.py          # Filesystem artifact probing
│   │   │   └── telemetry_reader.py        # Concurrent-read-safe telemetry JSON parsing
│   │   │
│   │   ├── middleware/                    # 7-layer middleware stack
│   │   │   ├── findings.py                # Auto-capture search results
│   │   │   ├── patent_tracking.py         # 5-checkpoint patent lifecycle funnel
│   │   │   ├── feature_confirmation.py    # Gate 2 enforcement
│   │   │   ├── autonomous_research.py     # Post-Gate 2 autonomy enforcement
│   │   │   ├── research_continuation.py   # Research loop enforcement
│   │   │   ├── citation_enforcement.py    # Citation-researcher directive injection
│   │   │   └── content_filter.py          # Azure content policy guard
│   │   │
│   │   ├── observability/                 # Monitoring and analytics
│   │   │   ├── telemetry.py               # ResearchTelemetry + TelemetryMiddleware
│   │   │   └── patent_tracker.py          # PatentTracker + loss funnel statistics
│   │   │
│   │   ├── utils/
│   │   │   ├── feature_matrix.py          # Feature Matrix rendering utilities
│   │   │   └── report_coverage.py         # Coverage calculation helpers
│   │   │
│   │   └── skills/                        # Progressive skill disclosure (SKILL.md files)
│   │
│   └── tools/
│       ├── registry.py                    # Tool registration (get_all_tools)
│       ├── search.py                      # Patent, NPL, semantic search tools
│       ├── analysis.py                    # Triage, feature mapping, coverage tools
│       ├── findings.py                    # save_round_findings, get_all_findings
│       ├── reflection.py                  # think_tool (structured reasoning)
│       ├── aggregation.py                 # Result deduplication and merging
│       ├── resilience.py                  # Retry and error handling wrappers
│       └── clients/                       # External API clients
│           ├── innography.py              # Innography patent search client
│           ├── wos.py                     # Web of Science NPL client
│           ├── ngsp.py                    # NGSP semantic search client
│           └── schemas.py                 # Shared client data models
│
├── sessions/                              # Runtime: per-thread session workspaces
│   └── {thread_id}/
│       ├── scope.md
│       ├── features.md
│       ├── findings/
│       ├── findings_auto_accumulator.json
│       ├── final_report.md
│       ├── telemetry.json
│       └── patent_statistics.md
│
└── docs/
    ├── ARCHITECTURE.md                    # This file
    ├── ROADMAP.md                         # Project roadmap
    └── EVALUATION_PLAN.md                 # Evaluation methodology
```
