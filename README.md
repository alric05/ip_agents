# 🔬 Novelty Checker - Multi-Agent Prior Art Search System

A sophisticated multi-agent system built on **LangGraph** and **DeepAgents** framework for comprehensive novelty assessment and prior art search. The system uses an iterative research approach with specialized sub-agents for patent, non-patent literature (NPL), and semantic search.

## 📑 Table of Contents

- [Overview](#overview)
- [Design Documentation](#design-documentation)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Agent](#running-the-agent)
  - [Option 1: With Deep Agents UI (Recommended)](#option-1-with-deep-agents-ui-recommended)
  - [Option 2: With LangGraph Studio](#option-2-with-langgraph-studio)
  - [Option 3: Command Line Interface](#option-3-command-line-interface)
  - [Option 4: Programmatic Usage](#option-4-programmatic-usage)
  - [Option 5: End-to-End Evaluation (No Human Approval)](#option-5-end-to-end-evaluation-no-human-approval)
  - [Option 6: FastAPI Server (REST + SSE Streaming)](#option-6-fastapi-server-rest--sse-streaming)
- [Agent Workflow](#agent-workflow)
- [Tools & Search Capabilities](#tools--search-capabilities)
- [Sub-Agents](#sub-agents)
- [Session Management](#session-management)
- [Logging & Observability](#logging--observability)
- [Development](#development)
- [Testing](#testing)

---

## Overview

The Novelty Checker is designed to systematically evaluate whether a customer's invention idea is novel by:

1. **Scoping** - Extract invention scope with clarifying questions
2. **Feature Definition** - Decompose invention into 3-7 searchable features
3. **Research Loop** - Iterative "Search → Reflect → Decide" with specialized sub-agents
4. **Screening** - Triage references (A/B/C labels) and map features
5. **Report Generation** - Comprehensive 11-section novelty report

### Key Features

- 🔄 **Iterative Research Loop** - Coverage-based adaptive stopping (70% target)
- 🤖 **Specialized Sub-Agents** - Patent, NPL, and Semantic search specialists
- 💾 **Findings Persistence** - Automatic capture to prevent memory loss
- 🎯 **Multi-Database Search** - Innography (patents), Web of Science (NPL), NGSP (semantic)
- 📊 **Feature Matrix** - Structured coverage tracking per feature
- 🔌 **Flexible LLM Support** - Azure OpenAI, GPT-4o, GPT-5 via LiteLLM

---

## Design Documentation

- [Latest Agentic System Architecture](https://clarivate.atlassian.net/wiki/spaces/DRND/pages/187635502/Latest+Agentic+system+Architecture) (Confluence)

### Project Documentation

| Document | Description |
|----------|-------------|
| [Agent Performance Baselines (ADR)](docs/adr/agent-performance-baselines.md) | Performance targets (P50/P80/P95/P99) per operation category, measured baselines from session telemetry, and optimization roadmap |
| [GDPR Data Flow Summary](docs/gdpr/data_flow_summary.md) | Data flow analysis for GDPR compliance |
| [Architecture Overview](docs/ARCHITECTURE_OVERVIEW.md) | System architecture overview |
| [Architecture Details](docs/ARCHITECTURE.md) | Detailed architecture documentation |
| [Evaluation Plan](docs/EVALUATION_PLAN.md) | Agent evaluation strategy |
| [Failure Scenarios](docs/FAILURE_SCENARIOS.md) | Known failure modes and mitigations |
| [Roadmap](docs/ROADMAP.md) | Development roadmap |

---

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                    NOVELTY CHECKER SYSTEM                      │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │               ORCHESTRATOR AGENT                          │ │
│  │  (AGENTS.md + prompts.py instructions)                   │ │
│  │                                                          │ │
│  │  Middleware Stack:                                       │ │
│  │  • MemoryMiddleware (AGENTS.md system prompt)            │ │
│  │  • TodoListMiddleware (write_todos planning)             │ │
│  │  • SkillsMiddleware (progressive skill disclosure)       │ │
│  │  • SubAgentMiddleware (task delegation)                  │ │
│  │  • FindingsPersistenceMiddleware (auto-save results)     │ │
│  └──────────────────────────────────────────────────────────┘ │
│                           │                                    │
│              ┌────────────┼────────────┐                      │
│              ↓            ↓            ↓                      │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐          │
│  │   patent-    │ │    npl-      │ │  semantic-   │          │
│  │  researcher  │ │  researcher  │ │  researcher  │          │
│  │              │ │              │ │              │          │
│  │ Innography   │ │ Web of Sci.  │ │    NGSP      │          │
│  └──────────────┘ └──────────────┘ └──────────────┘          │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
dw-rnd-unified-agent/           # Repository name
├── langgraph.json              # LangGraph Studio configuration
├── studio.py                   # LangGraph Studio entry point
├── pyproject.toml              # Python package configuration
├── requirements.txt            # Python dependencies
├── README.md                   # This documentation
├── CODE_REVIEW.md              # Architecture review & recommendations
├── .env                        # Environment variables (create this)
│
├── src/                        # Main source code
│   ├── config/                 # Configuration modules
│   │   ├── llm.py              # LLM provider configuration (Azure OpenAI)
│   │   └── settings.py         # Application settings from .env
│   │
│   ├── novelty_checker/        # Core agent module
│   │   ├── AGENTS.md           # System prompt (loaded by MemoryMiddleware)
│   │   ├── deep_agent.py       # Main agent factory (create_deep_agent)
│   │   ├── main.py             # CLI entry point
│   │   ├── prompts.py          # Modular prompt templates
│   │   ├── state.py            # State type definitions (20+ fields)
│   │   ├── subagents.yaml      # Sub-agent specifications
│   │   ├── skills/             # SKILL.md files for progressive disclosure
│   │   │   ├── scoping/
│   │   │   ├── feature-definition/
│   │   │   ├── patent-search/
│   │   │   ├── npl-search/
│   │   │   ├── semantic-search/
│   │   │   ├── parallel-search/
│   │   │   ├── screening/
│   │   │   └── report/
│   │   ├── middleware/         # Custom middleware
│   │   │   └── findings.py     # Auto-capture search results
│   │   └── utils/              # Utility functions
│   │       └── feature_matrix.py
│   │
│   └── tools/                  # Agent tools
│       ├── registry.py         # Tool registry (get_all_tools, etc.)
│       ├── search.py           # Search tools (patent, NPL, semantic)
│       ├── analysis.py         # Analysis tools (coverage, triage)
│       ├── aggregation.py      # Result aggregation
│       ├── findings.py         # Findings persistence tools
│       ├── reflection.py       # think_tool for structured reasoning
│       └── clients/            # API clients
│           ├── innography.py   # Innography (patent database)
│           ├── wos.py          # Web of Science (NPL)
│           ├── ngsp.py         # NGSP (semantic search)
│           └── schemas.py      # Shared data schemas
│
├── deep-agents-ui/             # Web UI for interacting with the agent
│   ├── package.json            # Node.js dependencies
│   ├── yarn.lock               # Yarn lockfile
│   └── src/                    # Next.js application
│       ├── app/                # App router pages & components
│       ├── components/ui/      # Reusable UI components
│       ├── lib/                # Utility libraries
│       └── providers/          # React context providers
│
├── sessions/                   # Session workspaces (auto-generated, gitignored)
│   └── <session_id>/           # Per-session isolated storage
│       ├── scope.md            # Invention scope
│       ├── features.md         # Feature definitions
│       ├── references.md       # Running reference list
│       └── findings/           # Research round findings
│
└── tests/                      # Test suite
    ├── test_novelty_agent.py   # Main agent integration tests
    ├── test_search_phase.py    # Search functionality tests
    ├── test_apis.py            # API client tests
    ├── test_parallel_search.py # Parallel search tests
    ├── test_feature_matrix_e2e.py  # Feature matrix E2E tests
    ├── test_phase1_quick.py    # Quick phase 1 tests
    └── test_phase3.py          # Phase 3 tests
```

---

## Prerequisites

- **Python** 3.10+ (3.12 recommended)
- **Node.js** 18+ (for deep-agents-ui)
- **uv** (optional, recommended for faster installation) - [Install uv](https://docs.astral.sh/uv/getting-started/installation/)
- **API Keys** (see Configuration section)

---

## Installation

### 1. Clone and Setup Python Environment

```bash
# Clone the repository
git clone https://github.com/clarivate-prod/dw-rnd-unified-agent.git
cd dpa-ai-agent-base
```

#### Option A: Using uv (Recommended - Much Faster)

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install project with all dependencies
uv pip install -e .
```

#### Option B: Using pip (Traditional)

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install Python dependencies
pip install -e .
# OR
pip install -r requirements.txt
```

### 2. Setup Deep Agents UI (Optional but Recommended)

```bash
cd deep-agents-ui
yarn install
# OR
npm install
```

---

## Configuration

Create a `.env` file in the project root with the following variables:

```env
# ═══════════════════════════════════════════════════════════════════════════════
# Azure OpenAI (Required for LLM)
# ═══════════════════════════════════════════════════════════════════════════════
AZURE_OPENAI_API_KEY=your-azure-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-08-01-preview
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-5  # or gpt-4o

# ═══════════════════════════════════════════════════════════════════════════════
# Patent Search - Innography (Required for patent search)
# ═══════════════════════════════════════════════════════════════════════════════
INNOGRAPHY_USER_NAME=your-username
INNOGRAPHY_USER_SECRET=your-secret
INNOGRAPHY_USER_TOKEN=your-token
INNOGRAPHY_TOKEN_URL=https://staging-api.innography.com/tokens
INNOGRAPHY_SERVICES_URL=https://staging.innography.com/innoservices

# ═══════════════════════════════════════════════════════════════════════════════
# NPL Search - Web of Science (Required for academic literature)
# ═══════════════════════════════════════════════════════════════════════════════
WOS_API_KEY=your-wos-key
WOS_ENDPOINT=https://wos-api.clarivate.com/api/wos

# ═══════════════════════════════════════════════════════════════════════════════
# Semantic Search - NGSP (Required for semantic patent search)
# ═══════════════════════════════════════════════════════════════════════════════
CLARIVATE_NGSP_API_KEY=your-ngsp-key

# ═══════════════════════════════════════════════════════════════════════════════
# Optional: Google Gemini (Alternative LLM)
# ═══════════════════════════════════════════════════════════════════════════════
# GOOGLE_API_KEY=your-google-key

# ═══════════════════════════════════════════════════════════════════════════════
# Optional: LangSmith Tracing
# ═══════════════════════════════════════════════════════════════════════════════
# LANGCHAIN_TRACING_V2=true
# LANGCHAIN_API_KEY=your-langsmith-key
# LANGCHAIN_PROJECT=novelty-checker
```

---

## Running the Agent

### Option 1: With Deep Agents UI (Recommended)

The Deep Agents UI provides a visual interface for interacting with the agent, viewing files, and monitoring progress.

**Step 1: Start the LangGraph Backend**

```bash
# In the project root directory
cd /path/to/dpa-ai-agent-base
source .venv/bin/activate

# Start LangGraph dev server
langgraph dev
```

You will see output like:
```
╦  ┌─┐┌┐┌┌─┐╔═╗┬─┐┌─┐┌─┐┬ ┬
║  ├─┤││││ ┬║ ╦├┬┘├─┤├─┘├─┤
╩═╝┴ ┴┘└┘└─┘╚═╝┴└─┴ ┴┴  ┴ ┴

- 🚀 API: http://127.0.0.1:2024
- 🎨 Studio UI: https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
- 📚 API Docs: http://127.0.0.1:2024/docs
```

**Step 2: Start Deep Agents UI**

```bash
# In a new terminal
cd /path/to/dpa-ai-agent-base/deep-agents-ui
yarn dev
```

**Step 3: Open the UI**

1. Open your browser to [http://localhost:3000](http://localhost:3000)
2. Configure the settings:
   - **Deployment URL**: `http://127.0.0.1:2024`
   - **Assistant ID**: `novelty_checker` (from `langgraph.json`)
   - **LangSmith API Key**: (optional) Your `lsv2_pt_...` key

3. Start chatting with the agent!

**Example Input:**
```
Please check the novelty of this invention:

A hydraulic valve with a variable orifice mechanism that automatically 
adjusts flow rate based on pressure differential, featuring a spring-loaded 
piston with magnetic damping for smooth transitions.
```

---

### Option 2: With LangGraph Studio

LangGraph Studio provides a built-in visual debugger.

```bash
# Start the backend
langgraph dev
```

Open the Studio UI link shown in the terminal output:
```
https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024
```

---

### Option 3: Command Line Interface

Run the agent directly from the command line:

```bash
# Activate virtual environment
source .venv/bin/activate

# Interactive mode (recommended for multi-turn conversation)
python -m src.novelty_checker.main --interactive

# Single idea check
python -m src.novelty_checker.main --idea "Your invention description here"

# With specific model
python -m src.novelty_checker.main --model gpt-4o --interactive

# Verbose output
python -m src.novelty_checker.main -v --interactive
```

**CLI Commands during interactive mode:**
- `quit` / `exit` - End the session
- `todos` - Show current task list
- `confirm` - Confirm current stage
- `help` - Show available commands

---

### Option 4: Programmatic Usage

Use the agent directly in your Python code:

```python
from src.novelty_checker.deep_agent import create_deep_agent, check_novelty
from langchain_core.messages import HumanMessage

# Simple single-check usage
result = check_novelty(
    idea="A hydraulic valve with variable orifice mechanism...",
    model=None,  # Uses default (GPT-5)
    thread_id="my-thread",
)
print(f"Session: {result['session_id']}")

# Advanced: Create and run agent manually
graph, session_id = create_deep_agent(
    model=None,  # Uses default
    max_research_iterations=5,
    max_concurrent_research_units=3,
)

# Run with custom state
initial_state = {
    "messages": [HumanMessage(content="Check novelty of: ...")],
}
config = {"configurable": {"thread_id": "my-thread"}}

result = graph.invoke(initial_state, config=config)
```

---

### Option 5: End-to-End Evaluation (No Human Approval)

For testing and evaluation, use the `run_novelty_check_e2e` runner which automatically confirms both gates (Scope and Features) and runs the full pipeline without human intervention.

```python
from src.novelty_checker.eval_runner import run_novelty_check_e2e, RunPhase

result = run_novelty_check_e2e(
    idea="A hydraulic valve with variable orifice mechanism...",
    max_turns=30,               # Max invoke() calls (safety limit)
    max_duration_seconds=3600,  # 1 hour timeout
    progress_callback=lambda turn, phase, gate, preview: print(
        f"[Turn {turn}] {phase.name} | {preview[:80]}..."
    ),
)

# Check result
if result.final_phase == RunPhase.COMPLETED:
    print(f"Done in {result.total_turns} turns, {result.total_duration_seconds:.0f}s")
    print(f"Session: {result.session_path}")
    print(result.final_report[:500])
else:
    print(f"Run ended: {result.final_phase.name} - {result.error}")

# Access all session artifacts
for name, content in result.artifacts.items():
    print(f"  {name}: {len(content)} bytes")
```

**How it works:** The runner wraps the standard agent in a multi-turn loop. After each `invoke()` call it inspects the AI response for gate markers (`"Scope Summary"`, `"Feature Matrix"`) and auto-injects `HumanMessage("confirm")`. Once Gate 2 is confirmed the agent runs its autonomous research loop, and the runner waits until the final report is generated.

**Parameters:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| `idea` | (required) | Invention description to evaluate |
| `model` | Project default | LLM model string or `BaseChatModel` instance |
| `thread_id` | Auto-generated | Thread ID for conversation state |
| `session_id` | Auto-generated | Session workspace ID |
| `max_turns` | `30` | Maximum number of `invoke()` calls |
| `max_duration_seconds` | `3600` | Maximum wall-clock time (seconds) |
| `auto_scope_prompt` | Built-in | Custom prefix for the initial prompt |
| `progress_callback` | `None` | `(turn, phase, gate, preview) -> None` |

**Return value (`EvalRunResult`):**

| Field | Type | Description |
|-------|------|-------------|
| `final_phase` | `RunPhase` | `COMPLETED` or `ERROR` |
| `final_report` | `str \| None` | Content of `final_report.md` |
| `session_id` | `str` | Session workspace ID |
| `session_path` | `Path` | Full path to session directory |
| `total_turns` | `int` | Number of invoke() calls |
| `total_duration_seconds` | `float` | Wall-clock duration |
| `turns` | `list[TurnRecord]` | Per-turn metadata (phase, gate, duration, tool calls) |
| `messages` | `list[BaseMessage]` | Full message history |
| `artifacts` | `dict[str, str]` | Session files: scope.md, features.md, findings/, etc. |
| `error` | `str \| None` | Error message if run failed |

---

### Option 6: FastAPI Server (REST + SSE Streaming)

Run the standalone FastAPI server which exposes both structured REST endpoints and an SSE streaming endpoint.

**Step 1: Start the server**

```bash
source .venv/bin/activate
uvicorn server:api --host 0.0.0.0 --port 8000 --reload
```

The server runs at `http://localhost:8000`. Verify with:

```bash
curl http://localhost:8000/health
# {"ok": true}
```

**Step 2: Test the SSE streaming endpoint**

**Using curl:**

```bash
curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "Check the novelty of a hydraulic valve with a variable orifice mechanism that automatically adjusts flow rate based on pressure differential."}'
```

The `-N` flag disables buffering so you see events in real time. You will receive Server-Sent Events like:

```
event: metadata
data: {"thread_id": "some-uuid"}

event: message
data: {"node": "agent", "content": "I'd like to ask a few clarifying...", "type": "ai"}

event: tool_call
data: {"node": "agent", "tool": "think_tool"}

event: done
data: {"thread_id": "some-uuid"}
```

To continue the conversation on the same thread, pass the `thread_id` from the first response:

```bash
curl -N -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "confirm", "thread_id": "the-thread-id-from-above"}'
```

**Using Postman:**

1. Create a new request: `POST http://localhost:8000/chat/stream`
2. Set header: `Content-Type: application/json`
3. Set body (raw JSON):
   ```json
   {
     "message": "Check the novelty of a hydraulic valve with a variable orifice mechanism.",
     "thread_id": null
   }
   ```
4. Click **Send**
5. Postman will show SSE events streaming in the response body in real time
6. Copy the `thread_id` from the `metadata` event and use it in subsequent requests to continue the conversation

> **Note:** Postman versions 10+ support SSE responses natively. If you are on an older version, use curl instead.

**Using Python:**

```python
import httpx

with httpx.stream(
    "POST",
    "http://localhost:8000/chat/stream",
    json={"message": "Check the novelty of a hydraulic valve with variable orifice."},
    timeout=300,
) as response:
    for line in response.iter_lines():
        if line:
            print(line)
```

**Available Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/chat` | Structured response with stage detection (`APIResponse` envelope) |
| `POST` | `/chat/stream` | SSE streaming (real-time token-by-token output) |
| `GET` | `/threads/{id}/state` | Poll thread state without invoking the agent |
| `GET` | `/threads/{id}/report` | Download final report markdown |
| `GET` | `/threads/{id}/token-usage` | Token usage breakdown |

---

## Agent Workflow

The Novelty Checker follows a structured workflow with user gates:

```
┌─────────────────────────────────────────────────────────────────┐
│ Stage 1: SCOPING                                                │
│ • Extract invention scope                                       │
│ • Ask clarifying questions                                      │
│ → Gate 1: User confirms scope (saves /scope.md)                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Stage 2: FEATURE DEFINITION                                     │
│ • Decompose into 3-7 features (F1...Fn)                         │
│ • Identify core vs. peripheral features                         │
│ → Gate 2: User confirms features (saves /features.md)           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Stage 3: RESEARCH LOOP (Max 5 iterations)                       │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ 0. RECALL - Load prior findings from /findings/           │ │
│  │ 1. DELEGATE - Send tasks to sub-agents in parallel        │ │
│  │ 2. RECEIVE - Collect findings from all sub-agents         │ │
│  │ 3. PERSIST - Save round findings to /findings/round_X.md  │ │
│  │ 4. REFLECT - Use think_tool to analyze coverage           │ │
│  │ 5. DECIDE - Continue if gaps remain, else exit            │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│ Stop conditions:                                                │
│ • Coverage >= 70% AND core features STRONG                      │
│ • Max iterations reached                                        │
│ • Diminishing returns                                           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Stage 4: SYNTHESIS & REPORT                                     │
│ • Consolidate all references                                    │
│ • Build feature coverage matrix                                 │
│ • Generate 11-section novelty report                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tools & Search Capabilities

### Search Tools

| Tool | Source | Description |
|------|--------|-------------|
| `patent_keyword_search` | Innography | Keyword search with @(field) syntax |
| `npl_search` | Web of Science | Academic literature search |
| `semantic_patent_search` | NGSP | Semantic similarity search |
| `get_patent_citations` | Innography | Forward/backward citation lookup |
| `batch_patent_search` | Innography | Execute multiple queries in parallel |
| `batch_npl_search` | WOS | Batch NPL queries |
| `batch_semantic_search` | NGSP | Batch semantic queries |
| `batch_unified_search` | All | Cross-database unified batch |

### Analysis Tools

| Tool | Description |
|------|-------------|
| `evaluate_coverage` | Assess feature coverage level (NONE/WEAK/MODERATE/STRONG) |
| `triage_reference` | Assign A/B/C labels to references |
| `map_features_to_reference` | Map Y/Y1/N coverage per feature |
| `generate_search_strategy` | Recommend search queries for gaps |
| `build_feature_matrix` | Build coverage matrix visualization |

### Persistence Tools

| Tool | Description |
|------|-------------|
| `save_round_findings` | Persist findings after each research round |
| `get_all_findings` | Retrieve all accumulated findings |
| `get_coverage_gaps` | Identify features needing more coverage |
| `think_tool` | Structured reasoning (scratchpad) |

---

## Sub-Agents

Defined in `src/novelty_checker/subagents.yaml`:

| Sub-Agent | Database | Specialization |
|-----------|----------|----------------|
| `patent-researcher` | Innography | Patent keyword search with @(field) syntax |
| `npl-researcher` | Web of Science | Academic literature search |
| `semantic-researcher` | NGSP | Semantic similarity & GIST search |

Each sub-agent follows the "Search → Reflect → Decide" loop with mandatory `think_tool` reflection after each search.

---

## Session Management

Each novelty check runs in an isolated session workspace:

```
sessions/
└── 20260206_133550_2ea803d9/    # Timestamp + UUID
    ├── scope.md                 # Gate 1 output
    ├── features.md              # Gate 2 output
    ├── references.md            # Running reference list
    └── findings/
        ├── round_1.md           # First research round
        ├── round_2.md           # Second research round
        ├── patent_round_1.md    # Patent-specific findings
        ├── npl_round_1.md       # NPL-specific findings
        └── semantic_round_1.md  # Semantic-specific findings
```

Sessions are automatically cleaned up after 24 hours (configurable).

---

## Logging & Observability

The system includes a comprehensive telemetry and observability layer for tracking token usage, costs, tool calls, and research progress.

### Logging Configuration

Standard Python `logging` at **INFO** level. Each module creates its own logger:

```python
import logging
_logger = logging.getLogger(__name__)
```

- Entry points (`studio.py`, `server.py`) call `logging.basicConfig(level=logging.INFO)`
- CLI verbose mode: `python -m src.novelty_checker.main -v` sets DEBUG level
- All output goes to **stdout/stderr** (no file-based logging configured)

### Telemetry System

The `ResearchTelemetry` class (`src/novelty_checker/observability/telemetry.py`) collects structured metrics throughout a session:

| Metric | What It Tracks |
|--------|----------------|
| `ToolCallMetric` | Tool name, duration (ms), success/failure, agent name, arguments |
| `ModelCallMetric` | Input/output tokens, duration, model name, estimated cost, agent name |
| `RoundMetric` | Round number, duration, new/total references, coverage % |
| `ExecutionSpan` | Timing traces for agent lifecycle and model calls |

**Key methods:**

| Method | Purpose |
|--------|---------|
| `start_round()` / `end_round()` | Track research iteration timing |
| `log_tool_call()` | Record tool execution with timing and status |
| `log_model_call()` | Thread-safe LLM call tracking with tokens and cost |
| `start_span()` / `end_span()` | Execution tracing |
| `get_token_summary()` | By-agent, by-stage, and cumulative token breakdowns |
| `log_session_summary()` | Human-readable session summary to logger |

**Integration:** The `TelemetryMiddleware` hooks into `wrap_tool_call()` and `wrap_model_call()` for automatic collection. It supports two modes:

- **Static mode** (CLI): Single `ResearchTelemetry` instance per session
- **Factory mode** (Studio/API): Per-thread instances via `telemetry_factory` callable

### Token Usage & Cost Estimation

Token usage is tracked per-agent and per-stage with automatic cost estimation:

- **Workflow stages:** `stage_1_scoping`, `stage_2_features`, `stage_3_research`, `stage_4_report`
- **Default pricing:** Built-in rates for `gpt-5` and `gpt-4o` (Azure variants included)
- **Custom pricing:** Set `TOKEN_PRICING_JSON` environment variable to a JSON file path:

```json
{
  "gpt-5": {"input": 3.00, "output": 12.00},
  "gpt-4o": {"input": 2.50, "output": 10.00}
}
```

Prices are per 1M tokens. Fallback: $3.00 input / $12.00 output.

**REST API access:**

```bash
# Get token usage for a thread
GET /threads/{thread_id}/token-usage

# Included in chat response
POST /chat  →  response.token_usage
```

### Subagent Message Tracing

Each subagent's full message history is persisted for debugging:

```
sessions/{thread_id}/traces/
├── patent-researcher_messages.json
├── npl-researcher_messages.json
└── semantic-researcher_messages.json
```

Each trace captures: message type, content, tool calls, and tool call IDs.

### Telemetry Output

Telemetry is automatically written to `sessions/{thread_id}/telemetry.json`:

```json
{
  "session_id": "20260206_133550_2ea803d9",
  "start_time": "2026-02-06T13:35:50Z",
  "rounds": [],
  "tool_calls": [],
  "model_calls": [],
  "token_usage": {
    "by_agent": {"orchestrator": {"input_tokens": 5000, "output_tokens": 2000}},
    "by_stage": {"stage_3_research": {"input_tokens": 15000, "output_tokens": 8000}},
    "cumulative": {"total_input_tokens": 20000, "total_output_tokens": 10000}
  },
  "execution_trace": [],
  "summary": {}
}
```

### Performance Baseline Analysis

The script `scripts/compute_perf_baselines.py` reads `telemetry.json` from all complete sessions and computes P50/P80/P95/P99 latency percentiles per operation category (LLM decisions, single API calls, batch tools, citation chains, round completion).

```bash
# Compute performance baselines from session telemetry
python scripts/compute_perf_baselines.py
```

Only complete sessions (with `final_report.md` and >5 tool calls) are included. Results are used to validate the targets defined in the [Agent Performance Baselines ADR](docs/adr/agent-performance-baselines.md).

### Middleware Logging

The following middleware emit log messages during execution:

| Middleware | What It Logs |
|------------|--------------|
| `TelemetryMiddleware` | Token usage, model calls, tool calls, session summaries |
| `FindingsPersistenceMiddleware` | Auto-captured findings count, persistence events |
| `ContentFilterMiddleware` | Content filtering decisions |
| `CitationEnforcementMiddleware` | Citation validation results |
| `FeatureConfirmationMiddleware` | Feature gate transitions |
| `AutonomousResearchMiddleware` | Research enforcement events |
| `ResearchContinuationMiddleware` | Continuation logic decisions |
| `PatentTrackingMiddleware` | Patent lifecycle events |

---

## Development

### Project Setup for Development

```bash
# Using uv (recommended)
uv pip install -e ".[dev]"

# OR using pip
pip install -e ".[dev]"

# Install pre-commit hooks (optional)
pip install pre-commit
pre-commit install
```

### Adding New Tools

1. Create tool function in `src/tools/` with `@tool` decorator
2. Add to appropriate category in `src/tools/registry.py`
3. Update `subagents.yaml` if tool should be available to sub-agents

### Adding New Sub-Agents

Edit `src/novelty_checker/subagents.yaml`:

```yaml
new-researcher:
  description: "Brief description of what this agent does"
  system_prompt: |
    Detailed instructions for the sub-agent...
  tools:
    - tool_name_1
    - tool_name_2
```

---

## Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_novelty_agent.py

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test
pytest tests/test_search_phase.py -k "test_patent_search"
```

---

## Troubleshooting

### Port 2024 Already in Use

```bash
# Kill existing process
kill -9 $(lsof -t -i:2024)
```

### Clear LangGraph Cache

```bash
rm -rf ~/.langgraph
rm -rf /tmp/langgraph*
```

### API Client Issues

Check that all required environment variables are set:

```bash
python -c "from src.config.settings import get_settings; s = get_settings(); print(f'Innography: {bool(s.innography_user_name)}, WOS: {bool(s.wos_api_key)}, NGSP: {bool(s.clarivate_ngsp_api_key)}')"
```

---

## License

[]

---

## Contributing

[]
