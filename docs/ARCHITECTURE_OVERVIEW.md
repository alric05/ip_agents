# Novelty Checker — Architecture Overview

> **Visual architecture guide for the dev team.** For detailed implementation reference, see [ARCHITECTURE.md](./ARCHITECTURE.md).

The Novelty Checker is a **hierarchical multi-agent system** that automates patent novelty assessment. It orchestrates parallel searches across patent databases (Innography), academic literature (Web of Science), and semantic indices (NGSP), then synthesizes a comprehensive 11-section novelty report.

---

## 1. System Overview

```mermaid
flowchart LR
    subgraph Entry Points
        S[studio.py<br/>LangGraph Studio]
        A[server.py<br/>FastAPI REST API]
        C[main.py<br/>CLI]
    end

    subgraph Graph Factory
        F["create_deep_agent()<br/><i>deep_agent.py</i>"]
    end

    subgraph Compiled Graph
        O[Orchestrator Agent]
        MW[7-Layer Middleware Stack]
        SA[Subagent Pool]
    end

    subgraph External APIs
        INN[Innography<br/>Patent Search]
        WOS[Web of Science<br/>NPL Search]
        NGSP[NGSP<br/>Semantic Search]
        LLM[Azure OpenAI<br/>GPT-5 via LiteLLM]
    end

    subgraph Storage
        FS[FilesystemBackend<br/>sessions/thread_id/]
    end

    S --> F
    A --> F
    C --> F
    F --> O
    O <--> MW
    O --> SA
    SA --> INN
    SA --> WOS
    SA --> NGSP
    O <--> LLM
    SA <--> LLM
    O <--> FS
    SA <--> FS
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Orchestration | **LangGraph** — state machine graph, checkpointing |
| Agent Framework | **deepagents** — `create_deep_agent()`, middleware, subagent delegation |
| LLM Access | **LiteLLM** via `langchain_litellm` — Azure OpenAI (GPT-5) |
| REST API | **FastAPI** — structured JSON responses |
| Persistence | **FilesystemBackend** — session-isolated virtual filesystem |
| Search APIs | **Innography** (patent), **Web of Science** (NPL), **NGSP** (semantic) |

---

## 2. Agent Topology

```mermaid
flowchart TB
    subgraph Orchestrator
        ORCH["Orchestrator Agent<br/><b>Coordinator</b><br/><i>Plans, delegates, reflects, decides</i>"]
    end

    subgraph "Primary Research Subagents (Parallel)"
        PR["patent-researcher<br/>──────────────<br/>Innography API<br/>@(field) DWPI syntax<br/>Max 10 searches"]
        NR["npl-researcher<br/>──────────────<br/>Web of Science API<br/>TS=, TI= syntax<br/>Max 8 searches"]
        SR["semantic-researcher<br/>──────────────<br/>NGSP API<br/>Natural language gists<br/>Max 7 searches"]
        CR["citation-researcher<br/>──────────────<br/>Innography Citations<br/>Forward + backward<br/>Round 2+ only"]
    end

    subgraph "Analysis & Synthesis"
        CA["coverage-analyst<br/><i>Internal coverage assessment</i>"]
        RW["report-writer<br/><i>11-section report synthesis</i>"]
    end

    ORCH -- "task() in ONE message" --> PR
    ORCH -- "task() in ONE message" --> NR
    ORCH -- "task() in ONE message" --> SR
    ORCH -- "task() in ONE message" --> CR
    ORCH -.-> CA
    ORCH -.-> RW

    PR -- "findings" --> ORCH
    NR -- "findings" --> ORCH
    SR -- "findings + vocabulary" --> ORCH
    CR -- "citation findings" --> ORCH

    style ORCH fill:#4A90D9,stroke:#2C5F8A,color:#fff
    style PR fill:#7CB342,stroke:#558B2F,color:#fff
    style NR fill:#7CB342,stroke:#558B2F,color:#fff
    style SR fill:#7CB342,stroke:#558B2F,color:#fff
    style CR fill:#FFA726,stroke:#E65100,color:#fff
    style CA fill:#90A4AE,stroke:#546E7A,color:#fff
    style RW fill:#90A4AE,stroke:#546E7A,color:#fff
```

**Key rule:** All `task()` calls MUST appear in a **single AI message** for parallel execution. Sequential dispatch is 3-4x slower.

Each subagent follows the **Recall → Search → Reflect → Decide** loop:

```mermaid
flowchart LR
    A["RECALL<br/>get_all_findings()"] --> B["SEARCH<br/>API-specific query"]
    B --> C["REFLECT<br/>think_tool ⚡ MANDATORY"]
    C --> D{Coverage met?}
    D -- "Gaps remain" --> B
    D -- "Done / Hit limit" --> E["PERSIST<br/>write findings to /findings/"]
```

---

## 3. Workflow Pipeline & Gates

```mermaid
flowchart TD
    START([User submits invention idea]) --> S1

    subgraph "Interactive Phase"
        S1["Stage 1: Scoping<br/><i>Clarifying questions + scope definition</i>"]
        G1{"Gate 1<br/>Scope Confirmation"}
        S2["Stage 2: Feature Definition<br/><i>Decompose into 3-7 searchable features</i>"]
        G2{"Gate 2<br/>Feature Confirmation<br/><i>⚙ FeatureConfirmationMiddleware</i>"}
    end

    subgraph "Autonomous Phase"
        S3["Stage 3: Research Loop<br/><i>1-5 rounds of parallel search</i>"]
        S4["Stage 4: Report Synthesis<br/><i>11-section novelty report</i>"]
    end

    S1 --> G1
    G1 -- "Confirm" --> S2
    G1 -- "Edit" --> S1
    S2 --> G2
    G2 -- "Confirm" --> S3
    G2 -- "Edit" --> S2
    S3 --> S4
    S4 --> DONE([Final Report Delivered])

    style S1 fill:#42A5F5,stroke:#1E88E5,color:#fff
    style S2 fill:#42A5F5,stroke:#1E88E5,color:#fff
    style G1 fill:#FF7043,stroke:#E64A19,color:#fff
    style G2 fill:#FF7043,stroke:#E64A19,color:#fff
    style S3 fill:#66BB6A,stroke:#388E3C,color:#fff
    style S4 fill:#66BB6A,stroke:#388E3C,color:#fff
```

### Research Loop Detail

```mermaid
flowchart LR
    R["RECALL<br/>get_all_findings()"] --> D["DELEGATE<br/>Parallel task() to<br/>3-4 subagents"]
    D --> W["RECEIVE<br/>Wait for all subagents"]
    W --> P["PERSIST<br/>save_round_findings()"]
    P --> T["REFLECT<br/>think_tool:<br/>Coverage Analysis"]
    T --> DEC{DECIDE}
    DEC -- "Coverage < 70%<br/>Core features not STRONG<br/>Round < 5" --> R
    DEC -- "Coverage ≥ 70%<br/>OR max rounds<br/>OR diminishing returns" --> STOP["STOP → Report"]
```

### Stopping Criteria

| Signal | Threshold |
|--------|-----------|
| Coverage target met | All core features STRONG + overall ≥ 70% |
| Diminishing returns | < 2 new refs for 2 consecutive rounds |
| Feature saturation | All features at SATURATED |
| Max iterations | 5 rounds (hard limit) |

---

## 4. Middleware Stack

Seven middleware layers intercept every LLM and tool call:

```mermaid
flowchart TD
    subgraph "Middleware Stack (top → bottom)"
        M1["① FindingsPersistenceMiddleware<br/><code>wrap_tool_call</code><br/><i>Auto-captures search results → accumulator</i>"]
        M2["② PatentTrackingMiddleware<br/><code>wrap_tool_call</code><br/><i>Tracks patent lifecycle: DISCOVERED → REPORTED</i>"]
        M3["③ FeatureConfirmationMiddleware<br/><code>modify_prompt</code><br/><i>Blocks research until Gate 2 confirmed</i>"]
        M4["④ AutonomousResearchMiddleware<br/><code>modify_prompt</code><br/><i>Prevents user questions after Gate 2</i>"]
        M5["⑤ ResearchContinuationMiddleware<br/><code>modify_prompt</code><br/><i>Enforces PERSIST → REFLECT → DECIDE cycle</i>"]
        M6["⑥ CitationEnforcementMiddleware<br/><code>modify_prompt</code><br/><i>Triggers citation-researcher when A-refs + gaps exist</i>"]
        M7["⑦ TelemetryMiddleware<br/><code>wrap_tool_call</code> + <code>wrap_model_call</code><br/><i>Per-agent token usage + tool timing</i>"]
    end

    M1 --> M2 --> M3 --> M4 --> M5 --> M6 --> M7

    style M1 fill:#C8E6C9,stroke:#388E3C
    style M2 fill:#C8E6C9,stroke:#388E3C
    style M3 fill:#FFCDD2,stroke:#C62828
    style M4 fill:#FFCDD2,stroke:#C62828
    style M5 fill:#FFF9C4,stroke:#F57F17
    style M6 fill:#FFF9C4,stroke:#F57F17
    style M7 fill:#BBDEFB,stroke:#1565C0
```

| # | Middleware | Active During | Purpose |
|---|-----------|---------------|---------|
| ① | FindingsPersistence | Research | Safety net: auto-captures every search result |
| ② | PatentTracking | Research | QA: tracks patent loss funnel |
| ③ | FeatureConfirmation | Pre-research | **Gate 2 enforcement** |
| ④ | AutonomousResearch | Post-Gate 2 | Silences user-facing questions |
| ⑤ | ResearchContinuation | Research loop | Forces proper loop processing |
| ⑥ | CitationEnforcement | Round 2+ | Triggers citation network analysis |
| ⑦ | Telemetry | Always | Token/cost/timing metrics |

---

## 5. Data Flow & Findings Persistence

```mermaid
sequenceDiagram
    participant O as Orchestrator
    participant SA as Subagents (parallel)
    participant API as Search APIs
    participant MW as FindingsPersistence MW
    participant FS as FilesystemBackend

    Note over O: Round N begins
    O->>O: get_all_findings()
    O->>SA: task() × 3-4 (parallel)

    SA->>API: search queries
    API-->>SA: results
    MW-->>FS: Auto-capture → /findings/auto/
    SA->>SA: think_tool (REFLECT)
    SA->>FS: write_file → /findings/{type}_round_N.md

    SA-->>O: findings returned

    O->>FS: save_round_findings()
    O->>O: think_tool (Coverage Analysis)
    O->>O: DECIDE: CONTINUE or STOP

    Note over FS: Three persistence layers:<br/>1. Auto-capture (middleware)<br/>2. Subagent writes (explicit)<br/>3. Orchestrator consolidation
```

### Session Directory

```
sessions/{thread_id}/
├── scope.md                          ← Gate 1 output
├── features.md                       ← Gate 2 output
├── findings/
│   ├── patent_round_1.md             ← Subagent writes
│   ├── npl_round_1.md
│   ├── semantic_round_1.md
│   ├── citations_round_2.md
│   └── auto/                         ← Middleware auto-captures
│       ├── patent_capture_1.json
│       └── ...
├── findings_auto_accumulator.json    ← Deduplicated master index
├── final_report.md                   ← 11-section report
├── telemetry.json                    ← Token usage metrics
└── patent_statistics.md              ← QA loss funnel
```

---

## 6. Session Isolation

```mermaid
flowchart TB
    subgraph "Factory Mode (Studio / API)"
        BF["ThreadAwareBackendFactory"]
        TA["Thread A"] --> BF
        TB["Thread B"] --> BF
        TC["Thread C"] --> BF
        BF --> DA["sessions/thread_A/"]
        BF --> DB["sessions/thread_B/"]
        BF --> DC["sessions/thread_C/"]
    end

    subgraph "Static Mode (CLI)"
        SM["FilesystemBackend"]
        SM --> SD["sessions/{timestamp}_{uuid}/"]
    end

    style BF fill:#E1BEE7,stroke:#7B1FA2
    style SM fill:#B3E5FC,stroke:#0277BD
```

| Mode | Flag | Backend | Isolation | Use Case |
|------|------|---------|-----------|----------|
| **Factory** | `use_backend_factory=True` | `ThreadAwareBackendFactory` | Per-thread directories | Studio, API server |
| **Static** | `use_backend_factory=False` | `FilesystemBackend` | Single session directory | CLI, eval runner |

The factory extracts `thread_id` from `ToolRuntime.config["configurable"]["thread_id"]` and caches one `FilesystemBackend` per thread.

---

## 7. API Layer

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as FastAPI (server.py)
    participant G as LangGraph Agent
    participant SD as Stage Detector
    participant RP as Response Parser

    FE->>API: POST /chat {message, thread_id}
    API->>G: graph.ainvoke(messages, config)
    Note over G: Agent processes...<br/>(instant for scoping,<br/>5-15 min for research)
    G-->>API: result (messages + state)
    API->>SD: detect_stage(backend, messages)
    SD-->>API: "scoping" | "features" | "researching" | "complete"
    API->>RP: build_stage_data(stage, ai_text, state, backend)
    Note over RP: 1. JSON blocks<br/>2. Heuristic regex<br/>3. Graph state fallback
    RP-->>API: stage_data
    API-->>FE: APIResponse envelope
```

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/chat` | Send message, receive structured response |
| `GET` | `/threads/{id}/state` | Poll current state (no agent invocation) |
| `GET` | `/threads/{id}/report` | Download final report markdown |
| `GET` | `/threads/{id}/token-usage` | Token usage by stage/agent |
| `GET` | `/health` | Health check |

### Response Envelope

```json
{
  "thread_id": "abc-123",
  "stage": "scoping | features | researching | complete",
  "status": "awaiting_input | processing | done | error",
  "stage_data": { "...stage-specific structured data..." },
  "raw_response": "AI text fallback",
  "token_usage": { "by_stage": {}, "by_agent": {} }
}
```

---

## 8. Quick Reference

### Key Source Files

| File | Purpose |
|------|---------|
| `studio.py` | LangGraph Studio entry point |
| `server.py` | FastAPI REST API entry point |
| `src/novelty_checker/deep_agent.py` | Graph factory (`create_deep_agent()`) |
| `src/novelty_checker/state.py` | State schema + reducers |
| `src/novelty_checker/prompts.py` | Agent instructions |
| `src/novelty_checker/backend_factory.py` | Per-thread session isolation |
| `src/novelty_checker/middleware/` | 7-layer middleware stack |
| `src/novelty_checker/api/` | REST API (schemas, endpoints, parsing) |
| `src/novelty_checker/observability/` | Telemetry + patent tracking |
| `src/tools/` | 20+ tools (search, analysis, findings, reflection) |

### Further Reading

- **[ARCHITECTURE.md](./ARCHITECTURE.md)** — Full implementation details (1300+ lines), including complete data flow walkthrough with examples, middleware internals, state reducer logic, and configuration reference
- **[ROADMAP.md](./ROADMAP.md)** — Project roadmap and planned features
