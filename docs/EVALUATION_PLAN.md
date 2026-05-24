# Evaluation Plan — Novelty Checker Agent

> **Goal**: Systematically evaluate each stage of the multi-agent novelty/prior-art search system and the end-to-end pipeline using [`agentevals`](https://github.com/langchain-ai/agentevals) (LangChain's agent evaluation framework).

---

## Table of Contents

1. [Overview & Evaluation Strategy](#1-overview--evaluation-strategy)
2. [Phase 0 — Infrastructure & Golden Dataset Curation](#phase-0--infrastructure--golden-dataset-curation)
3. [Phase 1 — Tool-Level Unit Evaluations](#phase-1--tool-level-unit-evaluations)
4. [Phase 2 — Sub-Agent Trajectory Evaluations](#phase-2--sub-agent-trajectory-evaluations)
5. [Phase 3 — Stage-by-Stage Orchestrator Evaluations](#phase-3--stage-by-stage-orchestrator-evaluations)
6. [Phase 4 — Graph Trajectory Evaluation (LangGraph-native)](#phase-4--graph-trajectory-evaluation-langgraph-native)
7. [Phase 5 — End-to-End Pipeline Evaluation](#phase-5--end-to-end-pipeline-evaluation)
8. [Phase 6 — Custom Domain-Specific Evaluators](#phase-6--custom-domain-specific-evaluators)
9. [Phase 7 — LangSmith CI/CD Integration](#phase-7--langsmith-cicd-integration)
10. [Appendix — Metrics Summary & Scoring Rubrics](#appendix--metrics-summary--scoring-rubrics)

---

## 1. Overview & Evaluation Strategy

### Agent Pipeline Stages

The Novelty Checker follows a multi-stage pipeline:

```
Scope (Gate 1) → Feature Extraction (Gate 2) → Parallel Research Rounds → Reflection → Report
                                                    ↑         ↓
                                              patent-researcher
                                              npl-researcher
                                              semantic-researcher
```

### Evaluation Layers

We evaluate at **four distinct layers**, from inner to outer:

| Layer | What | Evaluator Type | `agentevals` API |
|-------|------|----------------|------------------|
| **L1 — Tools** | Individual tool call correctness | Deterministic assertions + LLM judge | `openevals` LLM-as-judge |
| **L2 — Sub-Agents** | Single sub-agent message trajectory | `create_trajectory_llm_as_judge` | Trajectory LLM-as-judge |
| **L3 — Stages** | Orchestrator behaviour within one stage | `create_trajectory_llm_as_judge` + custom prompts | Trajectory LLM-as-judge with domain rubrics |
| **L4 — Graph / E2E** | Full graph node traversal path + final report quality | `create_graph_trajectory_llm_as_judge` + `extract_langgraph_trajectory_from_thread` | Graph Trajectory LLM-as-judge |

### Evaluation Modes

| Mode | Description | When to Use |
|------|-------------|-------------|
| **Deterministic** | `trajectory_match` (strict/subset/superset/unordered) | Tool call sequence correctness — reproducible, fast, cheap |
| **LLM-as-Judge** | `trajectory_llm_as_judge` / `graph_trajectory_llm_as_judge` | Semantic correctness where exact match is too rigid |
| **Hybrid** | Deterministic for structure + LLM for content quality | Best of both: validate tools were called, then judge output quality |

---

## Phase 0 — Infrastructure & Golden Dataset Curation

> **Objective**: Install dependencies, create the evaluation test harness, and curate golden datasets from existing session data.

### 0.1 Dependencies

```bash
pip install agentevals openevals langsmith
```

Add to `requirements.txt`:
```
agentevals>=0.1.0
openevals>=0.1.0
langsmith>=0.3.0
```

### 0.2 Project Structure

```
evals/
├── __init__.py
├── conftest.py                   # Shared pytest fixtures (LLM judge, agent factory)
├── golden_datasets/
│   ├── README.md                 # How to curate / update golden data
│   ├── inventions.json           # Input invention descriptions
│   ├── scopes.json               # Expected scope outputs (Gate 1)
│   ├── features.json             # Expected feature extractions (Gate 2)
│   ├── trajectories/
│   │   ├── patent_researcher.json    # Reference sub-agent trajectories
│   │   ├── npl_researcher.json
│   │   ├── semantic_researcher.json
│   │   └── orchestrator_e2e.json     # Full orchestrator graph trajectories
│   └── reports/
│       ├── dual_worm_gear.md     # Known-good final reports
│       └── micro_led_display.md
├── test_tools.py                 # Phase 1: Tool-level evaluations
├── test_subagents.py             # Phase 2: Sub-agent trajectory evals
├── test_stages.py                # Phase 3: Stage-by-stage evals
├── test_graph_trajectory.py      # Phase 4: Graph trajectory evals
├── test_e2e.py                   # Phase 5: End-to-end pipeline evals
├── custom_evaluators.py          # Phase 6: Domain-specific evaluators
├── prompts/
│   ├── scope_rubric.py           # Custom LLM judge rubric for scope stage
│   ├── feature_rubric.py         # Custom LLM judge rubric for feature extraction
│   ├── search_rubric.py          # Custom LLM judge rubric for search quality
│   ├── coverage_rubric.py        # Custom LLM judge rubric for coverage assessment
│   └── report_rubric.py          # Custom LLM judge rubric for final report
└── utils.py                      # Helper functions (trajectory extraction, formatting)
```

### 0.3 Golden Dataset Curation

**Source**: Use existing session data from `sessions/d0a73b55-*/` as the first golden dataset.

**Tasks**:
1. Extract the full message history from a successful run using `eval_runner.py`
2. Manually annotate each stage transition (scope confirmed, features confirmed, research rounds)
3. For each sub-agent delegation, extract the sub-agent's message trajectory
4. Capture the final report and annotate expected feature coverage

**Golden dataset schema** (`evals/golden_datasets/inventions.json`):
```json
[
  {
    "id": "dual_worm_gear",
    "description": "A dual-worm gear transmission for smartphone cameras...",
    "expected_feature_count": [4, 6],
    "expected_core_features": ["dual worm gear", "miniaturized transmission"],
    "expected_min_a_refs": 2,
    "expected_coverage_pct": 70,
    "domain_keywords": ["worm gear", "camera actuator", "optical image stabilization"]
  }
]
```

### 0.4 Shared Test Fixtures (`evals/conftest.py`)

```python
import pytest
from agentevals.trajectory.llm import create_trajectory_llm_as_judge
from agentevals.graph_trajectory.llm import create_graph_trajectory_llm_as_judge
from agentevals.trajectory.match import create_trajectory_match_evaluator

@pytest.fixture
def trajectory_judge():
    """LLM-as-judge for message trajectories."""
    return create_trajectory_llm_as_judge(
        model="openai:o3-mini",
        continuous=True,  # Return float 0-1 for nuanced scoring
    )

@pytest.fixture
def graph_trajectory_judge():
    """LLM-as-judge for graph node trajectories."""
    return create_graph_trajectory_llm_as_judge(
        model="openai:o3-mini",
        continuous=True,
    )

@pytest.fixture
def strict_match_evaluator():
    """Deterministic trajectory match (exact tool call sequence)."""
    return create_trajectory_match_evaluator(
        trajectory_match_mode="strict",
        tool_args_match_mode="ignore",  # Only check tool names, not args
    )

@pytest.fixture
def subset_match_evaluator():
    """Check that expected tools were called (may have extras)."""
    return create_trajectory_match_evaluator(
        trajectory_match_mode="superset",
        tool_args_match_mode="ignore",
    )
```

### Deliverables
- [x] `evals/` directory structure created
- [x] `agentevals`, `openevals`, `langsmith` installed
- [x] At least 1 golden invention dataset curated from existing session (1 session available)
- [x] `conftest.py` with shared evaluator fixtures
- [x] CI-compatible `pytest` configuration in `pyproject.toml`

---

## Phase 1 — Tool-Level Unit Evaluations

> **Objective**: Validate that individual tools return correct, well-formatted results when called with known inputs.

### What We Evaluate

| Tool | Evaluation Type | Key Assertions |
|------|----------------|----------------|
| `patent_keyword_search` | Deterministic + LLM | Returns valid patent records, proper `ref_id` format, non-empty abstracts |
| `npl_search` | Deterministic + LLM | Returns WOS IDs, valid DOIs, non-empty titles |
| `semantic_patent_search` | Deterministic + LLM | Returns scored results, proper ranking |
| `batch_patent_search` | Deterministic | All queries executed, aggregated correctly |
| `get_patent_citations` | Deterministic | Returns forward + backward citations |
| `evaluate_coverage` | LLM-as-judge | Coverage percentages are reasonable given inputs |
| `build_feature_matrix` | Deterministic | Matrix has correct headers, no query IDs, valid Y/Y1/N values |
| `think_tool` | LLM-as-judge | Reflection follows structured template |
| `triage_reference` | LLM-as-judge | Triage labels (A/B/C) are consistent with feature overlap |

### Implementation Pattern

```python
# evals/test_tools.py
import pytest
from openevals.llm import create_llm_as_judge

class TestSearchToolOutputQuality:
    """Evaluate search tool output quality with LLM judge."""

    @pytest.fixture
    def output_quality_judge(self):
        return create_llm_as_judge(
            prompt="""Evaluate the quality of this patent search result.
            
            <Rubric>
            A good result:
            - Contains valid patent publication numbers (format: CC + number + kind code)
            - Has non-empty titles and abstracts
            - Includes priority dates in YYYY-MM-DD format
            - Has no duplicate entries
            - Returns results relevant to the query
            </Rubric>
            
            Search query: {inputs}
            Search results: {outputs}
            """,
            model="openai:o3-mini",
            continuous=True,
        )

    def test_patent_search_returns_valid_format(self, output_quality_judge):
        # Call tool with known query
        result = patent_keyword_search.invoke({
            "query": '@(dwpi_title,dwpi_abstract) (worm NEAR/3 gear)',
            "max_results": 5,
        })
        
        eval_result = output_quality_judge(
            inputs="worm gear patent search",
            outputs=result,
        )
        assert eval_result["score"] >= 0.7


class TestFeatureMatrixTool:
    """Deterministic validation of feature matrix output."""

    def test_matrix_has_correct_structure(self):
        result = build_feature_matrix.invoke({...})
        assert "| Ref ID |" in result or "| Publication Number |" in result
        assert "query_" not in result.lower()  # No query IDs allowed
```

### Deliverables
- [ ] `evals/test_tools.py` — test suite for all tool categories
- [ ] LLM-as-judge rubrics for search quality, triage accuracy, coverage assessment
- [ ] Deterministic validators for feature matrix format
- [ ] Mock/fixture data for offline testing (avoid hitting live APIs in CI)

---

## Phase 2 — Sub-Agent Trajectory Evaluations

> **Objective**: Evaluate each sub-agent's (patent-researcher, npl-researcher, semantic-researcher) message trajectory — are they following the prescribed `Search → Reflect → Decide` loop?

### What We Evaluate

Each sub-agent should follow this trajectory pattern:

```
User → [task delegation message]
Assistant → [calls get_all_findings]
Tool → [existing findings]
Assistant → [calls search tool]
Tool → [search results]
Assistant → [calls think_tool for reflection]
Tool → [reflection output]
Assistant → [decides: search more or return]
... (repeat if searching more) ...
Assistant → [returns consolidated findings]
```

### 2.1 Trajectory Match — Structural Correctness

Verify the tool call sequence is correct using deterministic match:

```python
# evals/test_subagents.py
from agentevals.trajectory.match import create_trajectory_match_evaluator

def test_patent_researcher_follows_search_reflect_loop():
    evaluator = create_trajectory_match_evaluator(
        trajectory_match_mode="subset",   # Must contain these tools
        tool_args_match_mode="ignore",
    )
    
    # Reference: expected tool call pattern
    reference_outputs = [
        {"role": "user", "content": "Search for patents related to..."},
        {"role": "assistant", "tool_calls": [
            {"function": {"name": "get_all_findings", "arguments": "{}"}}
        ]},
        {"role": "tool", "content": "..."},
        {"role": "assistant", "tool_calls": [
            {"function": {"name": "patent_keyword_search", "arguments": "..."}}
        ]},
        {"role": "tool", "content": "..."},
        {"role": "assistant", "tool_calls": [
            {"function": {"name": "think_tool", "arguments": "..."}}
        ]},
        {"role": "tool", "content": "..."},
        {"role": "assistant", "content": "Here are my findings..."},
    ]
    
    # Actual: captured from a real run
    actual_outputs = load_golden_trajectory("patent_researcher_run_1")
    
    result = evaluator(
        outputs=actual_outputs,
        reference_outputs=reference_outputs,
    )
    assert result["score"] == True
```

### 2.2 Trajectory LLM-as-Judge — Semantic Quality

Evaluate whether the sub-agent's reasoning and decisions are sound:

```python
from agentevals.trajectory.llm import create_trajectory_llm_as_judge

PATENT_RESEARCHER_RUBRIC = """You are evaluating a patent search sub-agent's trajectory.

<Rubric>
An excellent patent researcher trajectory:
- Starts by recalling prior findings (calls get_all_findings)
- Uses properly formatted Innography queries with @(field) syntax
- Reflects after EACH search using think_tool (MANDATORY)
- Tracks feature coverage progression in reflections
- Stops when core features have adequate coverage OR diminishing returns
- Does NOT exceed 10 searches
- Returns consolidated findings with triage labels (A/B/C)
- Persists findings to files before returning

A poor trajectory:
- Skips the recall step
- Uses malformed queries
- Never reflects (no think_tool calls)
- Runs too many redundant searches
- Returns raw results without triage
</Rubric>

Grade this patent researcher trajectory:

<trajectory>
{outputs}
</trajectory>
"""

def test_patent_researcher_quality():
    evaluator = create_trajectory_llm_as_judge(
        prompt=PATENT_RESEARCHER_RUBRIC,
        model="openai:o3-mini",
        continuous=True,
    )
    
    trajectory = load_golden_trajectory("patent_researcher_run_1")
    result = evaluator(outputs=trajectory)
    
    assert result["score"] >= 0.7, f"Patent researcher quality too low: {result['comment']}"
```

### 2.3 Per-Sub-Agent Rubrics

Create specific rubrics for each sub-agent type:

| Sub-Agent | Key Evaluation Criteria |
|-----------|----------------------|
| `patent-researcher` | Query syntax correctness (`@(field)` format), feature targeting, reflection quality, dedup awareness |
| `npl-researcher` | Query diversity (topic + fieldcode), Web of Science ID extraction, academic relevance |
| `semantic-researcher` | Concept vector usage, vocabulary discovery, embedding-based ranking quality |
| `citation-researcher` | Forward/backward citation traversal, chain depth, source patent tracking |

### Deliverables
- [x] `evals/test_subagents.py` — trajectory evaluations for all 4 sub-agent types (56 deterministic + 4 LLM-as-judge)
- [x] Custom rubric prompts in `evals/prompts/trajectory_rubric.py` (4 per-sub-agent rubrics)
- [x] Golden reference trajectories in `evals/golden_datasets/trajectories/` (4 files)
- [x] Both deterministic (structure + ordering) and LLM (quality) evaluators per sub-agent

---

## Phase 3 — Stage-by-Stage Orchestrator Evaluations

> **Objective**: Evaluate the orchestrator's behaviour at each stage of the pipeline independently.

### 3.1 Scope Stage (Gate 1)

**What to evaluate**: Given an invention description, does the orchestrator produce a clear, complete scope summary?

```python
SCOPE_RUBRIC = """You are evaluating the Scope stage of a novelty assessment agent.

<Rubric>
A good scope output:
- Accurately captures the core invention concept
- Identifies the technical field/domain
- Notes key distinguishing features
- Asks minimal clarifying questions (ideally zero)
- Presents a clear "Scope Summary" for user confirmation
- Writes scope.md to the filesystem

A poor scope output:
- Misunderstands the invention
- Asks too many unnecessary clarifying questions
- Omits critical technical aspects
- Doesn't present a structured summary for confirmation
</Rubric>

Invention input: {inputs}
Agent trajectory: {outputs}
Reference scope: {reference_outputs}
"""
```

**Test pattern**: Run the agent with `max_turns=5` (stop after Gate 1), evaluate the scope output.

### 3.2 Feature Extraction Stage (Gate 2)

**What to evaluate**: Does the orchestrator decompose the invention into the right number and type of features?

```python
FEATURE_RUBRIC = """You are evaluating the Feature Extraction stage of a novelty assessment agent.

<Rubric>
A good feature extraction:
- Produces 3-7 features (not too few, not too many)
- Correctly identifies core vs. non-core features
- Each feature has a clear name, description, and search keywords
- Features are mutually exclusive (minimal overlap)
- Core features capture the inventive step
- Presents a Feature Matrix TABLE for user confirmation
- Writes features.md to the filesystem

A poor feature extraction:
- Too few features (misses key aspects) or too many (over-decomposed)
- Misidentifies core features
- Features overlap significantly
- Keywords are too generic or too narrow
</Rubric>

Invention scope: {inputs}
Agent trajectory: {outputs}
Expected features: {reference_outputs}
"""
```

**Deterministic checks**:
```python
def test_feature_count_in_range(features_output):
    feature_ids = re.findall(r'F\d+', features_output)
    assert 3 <= len(feature_ids) <= 7

def test_core_features_identified(features_output):
    assert features_output.count("is_core: true") >= 1 or features_output.count("Core? | Y") >= 1
```

### 3.3 Research Round Stage

**What to evaluate**: Does the orchestrator properly delegate to sub-agents and maintain coverage tracking?

```python
RESEARCH_RUBRIC = """You are evaluating a single Research Round of the novelty assessment orchestrator.

<Rubric>
A good research round:
- Delegates to multiple sub-agents in parallel (patent + npl + semantic)
- Provides each sub-agent with feature-specific search context
- After receiving results, reflects on coverage gaps
- Persists round findings to filesystem
- Makes a sound CONTINUE/STOP decision based on coverage status
- If continuing, targets specific gap features in next round

A poor research round:
- Only delegates to one search type
- Provides vague/generic search instructions
- Doesn't reflect on coverage after receiving results
- Loses findings (doesn't persist)
- Makes arbitrary CONTINUE/STOP decisions
</Rubric>

Features: {features}
Prior coverage: {prior_coverage}
Round trajectory: {outputs}
"""
```

### 3.4 Report Generation Stage

**What to evaluate**: Does the final report follow the 11-section template and include all required data?

```python
REPORT_RUBRIC = """You are evaluating the Final Report of a novelty assessment.

<Rubric>
A good final report:
- Contains all 11 required sections
- Executive Summary accurately reflects findings
- Feature Matrix uses publication numbers (NOT query IDs)
- All A-refs and B-refs have pin-cites
- Coverage percentages match the actual reference data
- Prior art analysis is technically sound
- Recommendations are actionable

A poor final report:
- Missing sections
- Feature Matrix contains query IDs instead of publication numbers
- Missing pin-cites for key references
- Coverage numbers don't match actual data
- Vague or unsupported conclusions
</Rubric>

Features: {features}
References found: {references}
Report: {outputs}
Expected report structure: {reference_outputs}
"""
```

### Deliverables
- [ ] `evals/test_stages.py` — stage-isolated evaluations
- [ ] Custom rubric prompts in `evals/prompts/{scope,feature,search,coverage,report}_rubric.py`
- [ ] Stage-isolation helpers (run agent up to specific gate, then stop)
- [ ] Deterministic + LLM evaluators for each of the 4 stages

---

## Phase 4 — Graph Trajectory Evaluation (LangGraph-native)

> **Objective**: Use `agentevals`' graph trajectory evaluator to validate the node traversal path of the full LangGraph graph.

### 4.1 Extract Graph Trajectory

Since our agent uses LangGraph with a checkpointer, we can extract the full graph trajectory:

```python
from agentevals.graph_trajectory.utils import extract_langgraph_trajectory_from_thread
from agentevals.graph_trajectory.llm import create_graph_trajectory_llm_as_judge

# After running the agent
extracted = extract_langgraph_trajectory_from_thread(
    graph=agent,  # CompiledStateGraph from create_deep_agent()
    config={"configurable": {"thread_id": thread_id}},
)

# extracted["outputs"]["steps"] will show node traversal:
# [["__start__", "orchestrator", "patent-researcher", "npl-researcher", ...], ...]
```

### 4.2 Graph Trajectory LLM-as-Judge

```python
NOVELTY_GRAPH_RUBRIC = """You are evaluating the graph trajectory of a multi-agent novelty assessment system.

<Rubric>
An accurate graph trajectory:
- Starts with the orchestrator processing user input
- Delegates to sub-agents (patent-researcher, npl-researcher, semantic-researcher) in parallel
- Shows iterative research rounds (multiple delegation cycles)
- Includes reflection/analysis steps between rounds
- Ends with report generation
- Is reasonably efficient (no excessive re-delegation to the same sub-agent)

Expected high-level pattern:
  __start__ → orchestrator → [sub-agent delegations] → orchestrator (reflect) → 
  [more delegations if needed] → orchestrator (report) → END
</Rubric>

<Instructions>
Grade the following thread. "__start__" = entrypoint, each step list = one turn of the conversation.
</Instructions>

<thread>
{thread}
</thread>

{reference_outputs}
"""

def test_graph_trajectory_follows_expected_pattern():
    evaluator = create_graph_trajectory_llm_as_judge(
        prompt=NOVELTY_GRAPH_RUBRIC,
        model="openai:o3-mini",
        continuous=True,
    )
    
    result = evaluator(
        inputs=extracted["inputs"],
        outputs=extracted["outputs"],
    )
    assert result["score"] >= 0.7
```

### 4.3 Graph Trajectory Strict Match (Deterministic)

For regression testing, compare against a known-good trajectory:

```python
from agentevals.graph_trajectory.strict import graph_trajectory_strict_match

def test_graph_trajectory_matches_reference():
    reference_trajectory = load_golden_graph_trajectory("dual_worm_gear")
    
    result = graph_trajectory_strict_match(
        outputs=actual_trajectory,
        reference_outputs=reference_trajectory,
    )
    # Note: strict match may be too rigid for a stochastic system.
    # Use LLM-as-judge for primary evaluation; strict match for regression only.
```

### Deliverables
- [ ] `evals/test_graph_trajectory.py` — graph trajectory evaluations
- [ ] Trajectory extraction utility in `evals/utils.py`
- [ ] At least 2 golden graph trajectories from successful runs
- [ ] Custom rubric for the novelty assessment graph pattern

---

## Phase 5 — End-to-End Pipeline Evaluation

> **Objective**: Run the full pipeline from invention input to final report and evaluate overall quality.

### 5.1 Integration with `eval_runner.py`

Leverage the existing `run_novelty_check_e2e()` function:

```python
# evals/test_e2e.py
import pytest
from src.novelty_checker.eval_runner import run_novelty_check_e2e, RunPhase
from agentevals.trajectory.llm import create_trajectory_llm_as_judge

@pytest.mark.slow  # These are expensive/long-running tests
class TestEndToEndPipeline:
    
    @pytest.fixture
    def e2e_result(self):
        return run_novelty_check_e2e(
            idea="A dual-worm gear transmission system for miniaturized smartphone camera modules...",
            max_turns=25,
            max_duration_seconds=1800,
        )
    
    def test_pipeline_completes(self, e2e_result):
        assert e2e_result.final_phase == RunPhase.COMPLETED
        assert e2e_result.error is None
    
    def test_final_report_exists(self, e2e_result):
        assert e2e_result.final_report is not None
        assert len(e2e_result.final_report) > 500
    
    def test_all_artifacts_produced(self, e2e_result):
        assert "scope.md" in e2e_result.artifacts
        assert "features.md" in e2e_result.artifacts
        assert "references.md" in e2e_result.artifacts
        assert "final_report.md" in e2e_result.artifacts
    
    def test_report_has_all_sections(self, e2e_result):
        report = e2e_result.final_report
        required_sections = [
            "Executive Summary",
            "Feature Matrix",
            "Prior Art",
        ]
        for section in required_sections:
            assert section in report, f"Missing section: {section}"
    
    def test_report_quality_llm_judge(self, e2e_result):
        evaluator = create_trajectory_llm_as_judge(
            prompt=REPORT_QUALITY_PROMPT,
            model="openai:o3-mini",
            continuous=True,
        )
        # Format the full message history as trajectory
        trajectory = format_messages_as_trajectory(e2e_result.messages)
        result = evaluator(outputs=trajectory)
        assert result["score"] >= 0.6
```

### 5.2 Multi-Invention Evaluation Suite

Run across multiple inventions and aggregate scores:

```python
INVENTION_SUITE = [
    {
        "id": "dual_worm_gear",
        "description": "A dual-worm gear transmission for smartphone cameras...",
        "expected_min_refs": 5,
    },
    {
        "id": "micro_led_display",
        "description": "A micro-LED display with quantum dot color conversion...",
        "expected_min_refs": 4,
    },
    {
        "id": "solid_state_battery",
        "description": "A solid-state lithium battery with ceramic electrolyte...",
        "expected_min_refs": 6,
    },
]

@pytest.mark.parametrize("invention", INVENTION_SUITE, ids=[i["id"] for i in INVENTION_SUITE])
def test_e2e_per_invention(invention):
    result = run_novelty_check_e2e(
        idea=invention["description"],
        max_turns=25,
    )
    assert result.final_phase == RunPhase.COMPLETED
    # Check minimum reference count
    ref_count = result.final_report.count("| US") + result.final_report.count("| WOS:")
    assert ref_count >= invention["expected_min_refs"]
```

### 5.3 Few-Shot Examples for E2E Evaluation

```python
from agentevals.types import FewShotExample

e2e_few_shot = [
    {
        "inputs": "Evaluate novelty of a worm gear for cameras",
        "outputs": "The agent completed a full search with 3 rounds, found 8 A-refs...",
        "reasoning": "The pipeline completed all stages, found relevant prior art, and produced a comprehensive report with proper feature coverage.",
        "score": 1,
    },
    {
        "inputs": "Evaluate novelty of a bicycle pedal",
        "outputs": "The agent only ran 1 search round and produced a report with 1 reference...",
        "reasoning": "Insufficient research depth — only 1 round, 1 reference for a broad topic.",
        "score": 0,
    },
]
```

### Deliverables
- [ ] `evals/test_e2e.py` — full pipeline evaluation tests
- [ ] Multi-invention parametrized test suite (3+ inventions)
- [ ] Report quality evaluator with custom rubric
- [ ] Artifact completeness checks (scope, features, references, report)
- [ ] Aggregated scoring across inventions

---

## Phase 6 — Custom Domain-Specific Evaluators

> **Objective**: Build evaluators that capture patent-search-specific quality dimensions not covered by generic trajectory evaluation.

### 6.1 Coverage Completeness Evaluator

Check whether the claimed coverage percentage matches the actual reference data:

```python
# evals/custom_evaluators.py
from openevals.llm import create_llm_as_judge

def create_coverage_accuracy_evaluator():
    """Evaluates whether coverage claims match actual reference data."""
    return create_llm_as_judge(
        prompt="""You are a patent analysis expert evaluating coverage accuracy.

        Given the features and references found, evaluate whether the agent's
        coverage claims are accurate.

        Features: {features}
        References with feature_coverage: {references}
        Agent's coverage claims: {outputs}

        <Rubric>
        Score 1.0: Coverage percentages within 5% of actual data
        Score 0.7: Coverage percentages within 15% of actual data  
        Score 0.3: Major discrepancies (>25% off)
        Score 0.0: Completely fabricated coverage numbers
        </Rubric>
        """,
        model="openai:o3-mini",
        continuous=True,
    )
```

### 6.2 Pin-Cite Verification Evaluator

Verify that pin-cites (claim numbers, paragraphs) are present for A-refs:

```python
def create_pin_cite_evaluator():
    """Evaluates whether A-refs have proper pin-cites."""
    return create_llm_as_judge(
        prompt="""Evaluate pin-cite quality in this novelty report.

        For each A-level reference (highest relevance), check:
        1. Does it have specific claim numbers cited?
        2. Does it reference specific paragraphs or figures?
        3. Are the citations plausible (not fabricated)?

        Report excerpt: {outputs}

        <Rubric>
        Score 1.0: All A-refs have specific, plausible pin-cites
        Score 0.5: Most A-refs have pin-cites but some are vague
        Score 0.0: No pin-cites or clearly fabricated citations
        </Rubric>
        """,
        model="openai:o3-mini",
        continuous=True,
    )
```

### 6.3 Feature Matrix Integrity Evaluator

Programmatic evaluation (no LLM needed):

```python
def evaluate_feature_matrix_integrity(report: str, features: list, references: list) -> dict:
    """Deterministic evaluation of feature matrix correctness."""
    issues = []
    
    # Check 1: No query IDs in matrix
    if re.search(r'query_\w+', report):
        issues.append("Feature matrix contains query IDs instead of publication numbers")
    
    # Check 2: All features represented
    for feature in features:
        if feature["id"] not in report:
            issues.append(f"Feature {feature['id']} missing from matrix")
    
    # Check 3: Only A/B refs in matrix (not C)
    # Check 4: Valid coverage values (Y, Y1, N only)
    
    return {
        "key": "feature_matrix_integrity",
        "score": 1.0 if not issues else max(0, 1 - len(issues) * 0.2),
        "comment": "; ".join(issues) if issues else "Feature matrix is well-formed",
    }
```

### 6.4 Search Diversity Evaluator

Verify the agent used diverse search strategies:

```python
def evaluate_search_diversity(artifacts: dict) -> dict:
    """Check that multiple search types and strategies were used."""
    findings_files = [k for k in artifacts if k.startswith("findings/")]
    
    has_patent = any("patent_" in f for f in findings_files)
    has_npl = any("npl_" in f for f in findings_files)
    has_semantic = any("semantic_" in f for f in findings_files)
    has_citation = any("citation" in f for f in findings_files)
    
    diversity_score = sum([has_patent, has_npl, has_semantic, has_citation]) / 4.0
    
    return {
        "key": "search_diversity",
        "score": diversity_score,
        "comment": f"Patent={has_patent}, NPL={has_npl}, Semantic={has_semantic}, Citation={has_citation}",
    }
```

### Deliverables
- [ ] `evals/custom_evaluators.py` — all domain-specific evaluators
- [ ] Coverage accuracy evaluator
- [ ] Pin-cite verification evaluator
- [ ] Feature matrix integrity evaluator (deterministic)
- [ ] Search diversity evaluator (deterministic)
- [ ] Reference deduplication evaluator

---

## Phase 7 — LangSmith CI/CD Integration

> **Objective**: Integrate evaluations with LangSmith for tracking over time, and set up CI pipelines.

### 7.1 LangSmith Dataset Creation

```python
from langsmith import Client

client = Client()

# Create dataset from golden data
dataset = client.create_dataset("novelty-checker-eval-v1")
for invention in INVENTION_SUITE:
    client.create_example(
        inputs={"idea": invention["description"]},
        outputs={"expected_refs": invention["expected_min_refs"]},
        dataset_id=dataset.id,
    )
```

### 7.2 LangSmith `evaluate()` Integration

```python
from langsmith import Client
from agentevals.trajectory.llm import create_trajectory_llm_as_judge

client = Client()

trajectory_evaluator = create_trajectory_llm_as_judge(
    model="openai:o3-mini",
    continuous=True,
)

def target_function(inputs: dict) -> list:
    """Run the agent and return message trajectory."""
    result = run_novelty_check_e2e(idea=inputs["idea"], max_turns=20)
    return format_messages_as_trajectory(result.messages)

experiment_results = client.evaluate(
    target_function,
    data="novelty-checker-eval-v1",
    evaluators=[
        trajectory_evaluator,
        create_coverage_accuracy_evaluator(),
        create_pin_cite_evaluator(),
    ],
    experiment_prefix="novelty-checker",
)
```

### 7.3 CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/eval.yml
name: Agent Evaluations

on:
  push:
    branches: [main]
  schedule:
    - cron: '0 6 * * 1'  # Weekly Monday 6am

jobs:
  eval-unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r requirements.txt && pip install agentevals openevals langsmith
      - run: pytest evals/test_tools.py evals/test_subagents.py -v --tb=short
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          LANGSMITH_API_KEY: ${{ secrets.LANGSMITH_API_KEY }}
          LANGSMITH_TRACING: "true"

  eval-e2e:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - run: pip install -r requirements.txt && pip install agentevals openevals langsmith
      - run: pytest evals/test_e2e.py -v -m slow --tb=short
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          AZURE_OPENAI_API_KEY: ${{ secrets.AZURE_OPENAI_API_KEY }}
          INNOGRAPHY_USER_TOKEN: ${{ secrets.INNOGRAPHY_USER_TOKEN }}
          WOS_API_KEY: ${{ secrets.WOS_API_KEY }}
          LANGSMITH_API_KEY: ${{ secrets.LANGSMITH_API_KEY }}
          LANGSMITH_TRACING: "true"
```

### 7.4 pytest Configuration

Add to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "slow: marks tests as slow/expensive (E2E runs)",
    "eval: marks evaluation tests",
    "langsmith: marks tests that push results to LangSmith",
]
```

### Deliverables
- [ ] LangSmith datasets created from golden data
- [ ] `evaluate()` integration for batch experiments
- [ ] GitHub Actions workflow for CI/CD
- [ ] pytest markers for eval test categorization
- [ ] Dashboard/tracking for evaluation scores over time

---

## Appendix — Metrics Summary & Scoring Rubrics

### Metrics Per Layer

| Layer | Metric | Type | Target | Tool |
|-------|--------|------|--------|------|
| **L1 — Tools** | Output format validity | Deterministic | 100% pass | pytest assertions |
| **L1 — Tools** | Search result relevance | LLM (0-1) | ≥ 0.7 | `openevals` LLM-as-judge |
| **L2 — Sub-Agents** | Tool call sequence correctness | Deterministic | Match reference | `create_trajectory_match_evaluator(subset)` |
| **L2 — Sub-Agents** | Search-Reflect-Decide loop adherence | LLM (0-1) | ≥ 0.7 | `create_trajectory_llm_as_judge` |
| **L3 — Stages** | Scope accuracy | LLM (0-1) | ≥ 0.8 | Custom rubric judge |
| **L3 — Stages** | Feature extraction quality | LLM (0-1) | ≥ 0.7 | Custom rubric judge |
| **L3 — Stages** | Coverage progression per round | LLM (0-1) | ≥ 0.6 | Custom rubric judge |
| **L3 — Stages** | Report completeness | Deterministic | 11/11 sections | pytest + regex |
| **L4 — Graph** | Graph node traversal accuracy | LLM (0-1) | ≥ 0.7 | `create_graph_trajectory_llm_as_judge` |
| **L4 — Graph** | Graph trajectory efficiency | LLM (0-1) | ≥ 0.5 | Custom rubric |
| **E2E** | Pipeline completion rate | Deterministic | 100% | `RunPhase.COMPLETED` |
| **E2E** | Final report quality | LLM (0-1) | ≥ 0.7 | Custom rubric judge |
| **E2E** | Coverage target hit (≥70%) | Deterministic | ≥ 70% | Coverage evaluator |
| **Domain** | Feature matrix integrity | Deterministic | 100% valid | `evaluate_feature_matrix_integrity()` |
| **Domain** | Pin-cite presence for A-refs | LLM (0-1) | ≥ 0.8 | Custom evaluator |
| **Domain** | Search diversity | Deterministic | ≥ 3/4 types | `evaluate_search_diversity()` |

### `agentevals` API Quick Reference

```python
# 1. Deterministic trajectory match
from agentevals.trajectory.match import create_trajectory_match_evaluator
evaluator = create_trajectory_match_evaluator(
    trajectory_match_mode="strict"|"unordered"|"subset"|"superset",
    tool_args_match_mode="exact"|"ignore"|"subset"|"superset",
    tool_args_match_overrides={"tool_name": lambda x, y: ...},
)
result = evaluator(outputs=[...], reference_outputs=[...])

# 2. LLM-as-judge trajectory
from agentevals.trajectory.llm import create_trajectory_llm_as_judge
evaluator = create_trajectory_llm_as_judge(
    prompt="...",             # Custom rubric with {outputs}, {reference_outputs}
    model="openai:o3-mini",
    continuous=True,          # Float 0-1 instead of binary
    few_shot_examples=[...],
)
result = evaluator(outputs=[...], reference_outputs=[...])

# 3. Graph trajectory (LangGraph-native)
from agentevals.graph_trajectory.utils import extract_langgraph_trajectory_from_thread
from agentevals.graph_trajectory.llm import create_graph_trajectory_llm_as_judge
extracted = extract_langgraph_trajectory_from_thread(graph, config)
evaluator = create_graph_trajectory_llm_as_judge(model="openai:o3-mini")
result = evaluator(inputs=extracted["inputs"], outputs=extracted["outputs"])
```

### Implementation Priority

| Priority | Phase | Effort | Impact | Dependency |
|----------|-------|--------|--------|------------|
| 🔴 P0 | Phase 0 — Infrastructure | 2 days | Foundation | None |
| 🔴 P0 | Phase 1 — Tool evals | 2 days | High | Phase 0 |
| 🟡 P1 | Phase 2 — Sub-agent evals | 3 days | High | Phase 0 |
| 🟡 P1 | Phase 3 — Stage evals | 3 days | High | Phase 0, 2 |
| 🟢 P2 | Phase 4 — Graph trajectory | 2 days | Medium | Phase 0 |
| 🟢 P2 | Phase 5 — E2E evals | 3 days | Very High | Phase 0-4 |
| 🔵 P3 | Phase 6 — Custom evals | 2 days | Medium | Phase 0 |
| 🔵 P3 | Phase 7 — LangSmith CI/CD | 2 days | High | Phase 0-6 |

**Total estimated effort**: ~19 days
