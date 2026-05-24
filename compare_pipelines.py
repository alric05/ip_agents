"""Compare baseline vs deep-agent scoring results with visualizations.

Reads the consolidated `all_cases_scores.json` produced by
`run_all_cases_pipeline.py` and generates comparison charts grouped by
case difficulty (Easy / Medium / Hard).

Output:
    evals/results/comparison_report.html  — self-contained HTML dashboard
    evals/results/charts/                 — individual PNG charts (if matplotlib available)
    evals/results/comparison_summary.json — machine-readable comparison data

Usage:
    python compare_pipelines.py
    python compare_pipelines.py --input evals/results/all_cases_scores.json
    python compare_pipelines.py --output-dir evals/results/comparison
    python compare_pipelines.py --metrics verdict_accuracy prior_art_recall feature_recall
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_INPUT = Path(__file__).parent / "evals" / "results" / "all_cases_scores.json"
DEFAULT_OUTPUT_DIR = Path(__file__).parent / "evals" / "results"

TIER1_METRICS = [
    "verdict_accuracy",
    "prior_art_hit_rate",
    "prior_art_recall",
    "feature_precision",
    "feature_recall",
]

TIER2_METRICS = [
    "report_section_completeness",
    "search_strategy",
    "triage_agreement",
    "feature_coverage_accuracy",
]

TIER3_METRICS = [
    "cost_per_run",
    "latency",
    "token_efficiency",
    "tool_error_rate",
    "search_reproducibility",
    "research_rounds",
    "tool_invocations",
]

ALL_KEY_METRICS = TIER1_METRICS + TIER2_METRICS

DIFFICULTY_ORDER = ["Easy", "Medium", "Hard"]
RUNNER_LABELS = {"baseline": "Baseline (Single-LLM)", "deepagent": "Deep Agent (Multi-Agent)"}
RUNNER_COLORS = {"baseline": "#6366f1", "deepagent": "#10b981"}


# ---------------------------------------------------------------------------
# Data loading & aggregation
# ---------------------------------------------------------------------------

@dataclass
class MetricAgg:
    """Aggregated metric stats for a group."""
    mean: float = 0.0
    median: float = 0.0
    std: float = 0.0
    min_val: float = 0.0
    max_val: float = 0.0
    count: int = 0
    pass_rate: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "mean": round(self.mean, 4),
            "median": round(self.median, 4),
            "std": round(self.std, 4),
            "min": round(self.min_val, 4),
            "max": round(self.max_val, 4),
            "count": self.count,
            "pass_rate": round(self.pass_rate, 4),
        }


def load_scores(input_path: Path) -> list[dict[str, Any]]:
    """Load the all_cases_scores.json report."""
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)
    results = data.get("results", [])
    # Filter only completed runs
    return [r for r in results if r.get("status") == "completed"]


def aggregate_metrics(
    results: list[dict[str, Any]],
    metrics: list[str] | None = None,
) -> dict[str, dict[str, dict[str, MetricAgg]]]:
    """Aggregate scores by (runner, difficulty, metric).

    Returns:
        {runner: {difficulty: {metric: MetricAgg}}}
    """
    if metrics is None:
        metrics = ALL_KEY_METRICS

    # Group results: runner -> difficulty -> list of score dicts
    grouped: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in results:
        runner = r["runner"]
        difficulty = r.get("difficulty", "Unknown")
        grouped[runner][difficulty].append(r)

    # Also add "All" difficulty group
    for r in results:
        grouped[r["runner"]]["All"].append(r)

    aggregated: dict[str, dict[str, dict[str, MetricAgg]]] = {}

    for runner, diff_groups in grouped.items():
        aggregated[runner] = {}
        for difficulty, cases in diff_groups.items():
            aggregated[runner][difficulty] = {}
            for metric in metrics:
                scores = [c["scores"].get(metric, 0.0) for c in cases if metric in c.get("scores", {})]
                passed = [c["passed"].get(metric, False) for c in cases if metric in c.get("passed", {})]

                if not scores:
                    aggregated[runner][difficulty][metric] = MetricAgg()
                    continue

                agg = MetricAgg(
                    mean=statistics.mean(scores),
                    median=statistics.median(scores),
                    std=statistics.stdev(scores) if len(scores) > 1 else 0.0,
                    min_val=min(scores),
                    max_val=max(scores),
                    count=len(scores),
                    pass_rate=sum(passed) / len(passed) if passed else 0.0,
                )
                aggregated[runner][difficulty][metric] = agg

    return aggregated


def compute_operational_summary(results: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Compute operational summaries (duration, tokens, turns) per runner + difficulty."""
    grouped: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in results:
        grouped[r["runner"]][r.get("difficulty", "Unknown")].append(r)
        grouped[r["runner"]]["All"].append(r)

    summary: dict[str, dict[str, Any]] = {}
    for runner, diff_groups in grouped.items():
        summary[runner] = {}
        for difficulty, cases in diff_groups.items():
            durations = [c.get("duration_seconds", 0) for c in cases]
            tokens = [c.get("total_tokens", 0) for c in cases]
            turns = [c.get("total_turns", 0) for c in cases]
            summary[runner][difficulty] = {
                "count": len(cases),
                "avg_duration_s": round(statistics.mean(durations), 1) if durations else 0,
                "avg_tokens": round(statistics.mean(tokens)) if tokens else 0,
                "avg_turns": round(statistics.mean(turns), 1) if turns else 0,
                "total_duration_s": round(sum(durations), 1),
            }
    return summary


def build_comparison_summary(
    aggregated: dict[str, dict[str, dict[str, MetricAgg]]],
    operational: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Build a machine-readable comparison summary."""
    summary: dict[str, Any] = {
        "runners": list(aggregated.keys()),
        "difficulties": DIFFICULTY_ORDER + ["All"],
        "metrics": {},
        "operational": operational,
        "winner_by_difficulty": {},
    }

    # Per-metric comparison
    for metric in ALL_KEY_METRICS:
        metric_data: dict[str, Any] = {}
        for difficulty in DIFFICULTY_ORDER + ["All"]:
            diff_data = {}
            for runner in aggregated:
                agg = aggregated.get(runner, {}).get(difficulty, {}).get(metric)
                if agg:
                    diff_data[runner] = agg.to_dict()
            metric_data[difficulty] = diff_data
        summary["metrics"][metric] = metric_data

    # Determine winner per difficulty
    for difficulty in DIFFICULTY_ORDER + ["All"]:
        wins: dict[str, int] = defaultdict(int)
        for metric in TIER1_METRICS:
            best_runner = None
            best_score = -1.0
            for runner in aggregated:
                agg = aggregated.get(runner, {}).get(difficulty, {}).get(metric)
                if agg and agg.mean > best_score:
                    best_score = agg.mean
                    best_runner = runner
            if best_runner:
                wins[best_runner] += 1
        summary["winner_by_difficulty"][difficulty] = dict(wins)

    return summary


# ---------------------------------------------------------------------------
# HTML report generation
# ---------------------------------------------------------------------------

def _generate_html_report(
    aggregated: dict[str, dict[str, dict[str, MetricAgg]]],
    operational: dict[str, dict[str, Any]],
    results: list[dict[str, Any]],
) -> str:
    """Generate a self-contained interactive HTML comparison dashboard."""

    # Prepare chart data as JSON for embedding
    chart_data = _prepare_chart_data(aggregated, operational, results)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pipeline Comparison: Baseline vs Deep Agent</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; line-height: 1.6; }}
.container {{ max-width: 1400px; margin: 0 auto; padding: 32px 24px; }}
h1 {{ font-size: 32px; font-weight: 700; margin-bottom: 8px; background: linear-gradient(135deg, #6366f1, #10b981); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
h2 {{ font-size: 20px; font-weight: 600; margin: 32px 0 16px; color: #94a3b8; }}
h3 {{ font-size: 16px; font-weight: 600; margin: 16px 0 8px; color: #cbd5e1; }}
.subtitle {{ font-size: 14px; color: #64748b; margin-bottom: 32px; }}
.summary-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 32px; }}
.card {{ background: #1e293b; border-radius: 12px; padding: 20px; border: 1px solid #334155; text-align: center; }}
.card-label {{ font-size: 12px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }}
.card-value {{ font-size: 28px; font-weight: 700; font-family: 'JetBrains Mono', monospace; }}
.card-value.baseline {{ color: #6366f1; }}
.card-value.deepagent {{ color: #10b981; }}
.card-value.neutral {{ color: #e2e8f0; }}
.chart-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 32px; }}
.chart-panel {{ background: #1e293b; border-radius: 12px; padding: 24px; border: 1px solid #334155; }}
.chart-panel.full-width {{ grid-column: 1 / -1; }}
.chart-container {{ position: relative; height: 350px; }}
.table-panel {{ background: #1e293b; border-radius: 12px; padding: 24px; border: 1px solid #334155; margin-bottom: 24px; overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th {{ padding: 10px 12px; text-align: left; border-bottom: 2px solid #334155; color: #94a3b8; font-weight: 600; white-space: nowrap; }}
td {{ padding: 8px 12px; border-bottom: 1px solid #1e293b; }}
tr:hover td {{ background: #334155; }}
.score-cell {{ font-family: 'JetBrains Mono', monospace; font-weight: 500; }}
.winner {{ color: #10b981; font-weight: 700; }}
.loser {{ color: #94a3b8; }}
.tie {{ color: #f59e0b; }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 600; }}
.badge-easy {{ background: #065f46; color: #6ee7b7; }}
.badge-medium {{ background: #92400e; color: #fcd34d; }}
.badge-hard {{ background: #7f1d1d; color: #fca5a5; }}
.legend {{ display: flex; gap: 24px; justify-content: center; margin: 16px 0; }}
.legend-item {{ display: flex; align-items: center; gap: 6px; font-size: 13px; }}
.legend-dot {{ width: 12px; height: 12px; border-radius: 50%; }}
.improvement {{ color: #10b981; }}
.degradation {{ color: #ef4444; }}
</style>
</head>
<body>
<div class="container">
<h1>Baseline vs Deep Agent — Pipeline Comparison</h1>
<p class="subtitle">Evaluation across all fixtures grouped by difficulty (Easy / Medium / Hard)</p>

<div id="summaryCards"></div>

<h2>Tier-1 Metrics by Difficulty</h2>
<div class="legend">
    <div class="legend-item"><div class="legend-dot" style="background:#6366f1"></div>Baseline</div>
    <div class="legend-item"><div class="legend-dot" style="background:#10b981"></div>Deep Agent</div>
</div>
<div class="chart-grid" id="tier1Charts"></div>

<h2>Tier-2 Metrics by Difficulty</h2>
<div class="chart-grid" id="tier2Charts"></div>

<h2>Operational Metrics</h2>
<div class="chart-grid" id="operationalCharts"></div>

<h2>Per-Case Score Comparison</h2>
<div class="table-panel" id="perCaseTable"></div>

<h2>Difficulty Breakdown Summary</h2>
<div class="chart-grid">
    <div class="chart-panel full-width">
        <h3>Average Tier-1 Score by Difficulty</h3>
        <div class="chart-container"><canvas id="difficultyRadar"></canvas></div>
    </div>
</div>

<h2>Improvement Analysis</h2>
<div class="table-panel" id="improvementTable"></div>

</div>

<script>
const DATA = {json.dumps(chart_data)};

// --- Summary Cards ---
function renderSummaryCards() {{
    const container = document.getElementById('summaryCards');
    const cards = DATA.summary_cards;
    let html = '<div class="summary-cards">';
    for (const card of cards) {{
        const cls = card.highlight || 'neutral';
        html += `<div class="card"><div class="card-label">${{card.label}}</div><div class="card-value ${{cls}}">${{card.value}}</div></div>`;
    }}
    html += '</div>';
    container.innerHTML = html;
}}

// --- Bar Charts ---
function createGroupedBarChart(canvasId, metric, data) {{
    const ctx = document.getElementById(canvasId).getContext('2d');
    const difficulties = ['Easy', 'Medium', 'Hard', 'All'];
    const baselineScores = difficulties.map(d => data.baseline?.[d]?.[metric]?.mean || 0);
    const deepagentScores = difficulties.map(d => data.deepagent?.[d]?.[metric]?.mean || 0);

    new Chart(ctx, {{
        type: 'bar',
        data: {{
            labels: difficulties,
            datasets: [
                {{ label: 'Baseline', data: baselineScores, backgroundColor: '#6366f1cc', borderColor: '#6366f1', borderWidth: 1 }},
                {{ label: 'Deep Agent', data: deepagentScores, backgroundColor: '#10b981cc', borderColor: '#10b981', borderWidth: 1 }},
            ]
        }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{ legend: {{ display: false }}, title: {{ display: true, text: metric.replace(/_/g, ' ').replace(/\\b\\w/g, l => l.toUpperCase()), color: '#e2e8f0', font: {{ size: 14 }} }} }},
            scales: {{
                y: {{ beginAtZero: true, max: 1.0, ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#334155' }} }},
                x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ display: false }} }}
            }}
        }}
    }});
}}

function renderMetricCharts(containerId, metrics) {{
    const container = document.getElementById(containerId);
    let html = '';
    for (const metric of metrics) {{
        const id = 'chart_' + metric;
        html += `<div class="chart-panel"><div class="chart-container"><canvas id="${{id}}"></canvas></div></div>`;
    }}
    container.innerHTML = html;
    for (const metric of metrics) {{
        createGroupedBarChart('chart_' + metric, metric, DATA.aggregated);
    }}
}}

// --- Operational Charts ---
function renderOperationalCharts() {{
    const container = document.getElementById('operationalCharts');
    const ops = ['duration', 'tokens', 'turns'];
    const labels = {{ duration: 'Avg Duration (seconds)', tokens: 'Avg Tokens', turns: 'Avg Turns' }};
    let html = '';
    for (const op of ops) {{
        html += `<div class="chart-panel"><div class="chart-container"><canvas id="op_${{op}}"></canvas></div></div>`;
    }}
    container.innerHTML = html;

    const difficulties = ['Easy', 'Medium', 'Hard', 'All'];
    for (const op of ops) {{
        const ctx = document.getElementById('op_' + op).getContext('2d');
        const field = op === 'duration' ? 'avg_duration_s' : op === 'tokens' ? 'avg_tokens' : 'avg_turns';
        const baselineData = difficulties.map(d => DATA.operational?.baseline?.[d]?.[field] || 0);
        const deepagentData = difficulties.map(d => DATA.operational?.deepagent?.[d]?.[field] || 0);

        new Chart(ctx, {{
            type: 'bar',
            data: {{
                labels: difficulties,
                datasets: [
                    {{ label: 'Baseline', data: baselineData, backgroundColor: '#6366f1cc', borderColor: '#6366f1', borderWidth: 1 }},
                    {{ label: 'Deep Agent', data: deepagentData, backgroundColor: '#10b981cc', borderColor: '#10b981', borderWidth: 1 }},
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{ legend: {{ display: false }}, title: {{ display: true, text: labels[op], color: '#e2e8f0', font: {{ size: 14 }} }} }},
                scales: {{
                    y: {{ beginAtZero: true, ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#334155' }} }},
                    x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ display: false }} }}
                }}
            }}
        }});
    }}
}}

// --- Per-case table ---
function renderPerCaseTable() {{
    const container = document.getElementById('perCaseTable');
    const cases = DATA.per_case;
    const metrics = DATA.tier1_metrics;

    let html = '<table><thead><tr><th>Case</th><th>Difficulty</th><th>Runner</th>';
    for (const m of metrics) {{ html += `<th>${{m.replace(/_/g, ' ')}}</th>`; }}
    html += '<th>Avg T1</th></tr></thead><tbody>';

    // Sort by difficulty then case_id
    const diffOrder = {{'Easy': 0, 'Medium': 1, 'Hard': 2}};
    cases.sort((a, b) => (diffOrder[a.difficulty] || 9) - (diffOrder[b.difficulty] || 9) || a.case_id.localeCompare(b.case_id));

    for (const c of cases) {{
        const badgeCls = 'badge-' + (c.difficulty || 'medium').toLowerCase();
        const scores = metrics.map(m => c.scores[m] ?? '-');
        const avg = scores.filter(s => typeof s === 'number').reduce((a, b) => a + b, 0) / Math.max(scores.filter(s => typeof s === 'number').length, 1);
        const runnerCls = c.runner === 'deepagent' ? 'style="color:#10b981"' : 'style="color:#6366f1"';

        html += `<tr><td>${{c.case_id}}</td><td><span class="badge ${{badgeCls}}">${{c.difficulty}}</span></td><td ${{runnerCls}}>${{c.runner}}</td>`;
        for (const s of scores) {{
            const val = typeof s === 'number' ? s.toFixed(3) : s;
            html += `<td class="score-cell">${{val}}</td>`;
        }}
        html += `<td class="score-cell">${{avg.toFixed(3)}}</td></tr>`;
    }}
    html += '</tbody></table>';
    container.innerHTML = html;
}}

// --- Radar chart for difficulty breakdown ---
function renderDifficultyRadar() {{
    const ctx = document.getElementById('difficultyRadar').getContext('2d');
    const metrics = DATA.tier1_metrics;
    const labels = metrics.map(m => m.replace(/_/g, ' '));

    const datasets = [];
    const runners = ['baseline', 'deepagent'];
    const colors = {{ baseline: '#6366f1', deepagent: '#10b981' }};

    for (const runner of runners) {{
        for (const diff of ['Easy', 'Medium', 'Hard']) {{
            const scores = metrics.map(m => DATA.aggregated[runner]?.[diff]?.[m]?.mean || 0);
            datasets.push({{
                label: `${{runner}} (${{diff}})`,
                data: scores,
                borderColor: colors[runner],
                backgroundColor: colors[runner] + '22',
                borderWidth: diff === 'Hard' ? 3 : diff === 'Medium' ? 2 : 1,
                borderDash: diff === 'Easy' ? [5, 5] : diff === 'Medium' ? [10, 5] : [],
                pointRadius: 3,
            }});
        }}
    }}

    new Chart(ctx, {{
        type: 'radar',
        data: {{ labels, datasets }},
        options: {{
            responsive: true,
            maintainAspectRatio: false,
            plugins: {{ legend: {{ position: 'right', labels: {{ color: '#94a3b8', font: {{ size: 11 }} }} }} }},
            scales: {{ r: {{ beginAtZero: true, max: 1.0, ticks: {{ color: '#94a3b8', backdropColor: 'transparent' }}, grid: {{ color: '#334155' }}, pointLabels: {{ color: '#cbd5e1', font: {{ size: 11 }} }} }} }}
        }}
    }});
}}

// --- Improvement table ---
function renderImprovementTable() {{
    const container = document.getElementById('improvementTable');
    const metrics = [...DATA.tier1_metrics, ...DATA.tier2_metrics];
    const difficulties = ['Easy', 'Medium', 'Hard', 'All'];

    let html = '<table><thead><tr><th>Metric</th>';
    for (const d of difficulties) {{ html += `<th>${{d}}</th>`; }}
    html += '</tr></thead><tbody>';

    for (const metric of metrics) {{
        html += `<tr><td>${{metric.replace(/_/g, ' ')}}</td>`;
        for (const diff of difficulties) {{
            const bl = DATA.aggregated?.baseline?.[diff]?.[metric]?.mean || 0;
            const da = DATA.aggregated?.deepagent?.[diff]?.[metric]?.mean || 0;
            const delta = da - bl;
            const pct = bl > 0 ? ((delta / bl) * 100).toFixed(1) : (da > 0 ? '+100' : '0.0');
            const cls = delta > 0.01 ? 'improvement' : delta < -0.01 ? 'degradation' : '';
            const sign = delta > 0 ? '+' : '';
            html += `<td class="score-cell ${{cls}}">${{sign}}${{pct}}%</td>`;
        }}
        html += '</tr>';
    }}
    html += '</tbody></table>';
    html += '<p style="margin-top:12px;font-size:12px;color:#64748b">Positive = Deep Agent outperforms Baseline. Negative = Baseline outperforms Deep Agent.</p>';
    container.innerHTML = html;
}}

// --- Init ---
renderSummaryCards();
renderMetricCharts('tier1Charts', DATA.tier1_metrics);
renderMetricCharts('tier2Charts', DATA.tier2_metrics);
renderOperationalCharts();
renderPerCaseTable();
renderDifficultyRadar();
renderImprovementTable();
</script>
</body>
</html>"""
    return html


def _prepare_chart_data(
    aggregated: dict[str, dict[str, dict[str, MetricAgg]]],
    operational: dict[str, dict[str, Any]],
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Prepare data structure for embedding in HTML."""

    # Convert MetricAgg -> dicts
    agg_dict: dict[str, Any] = {}
    for runner, diffs in aggregated.items():
        agg_dict[runner] = {}
        for diff, metrics in diffs.items():
            agg_dict[runner][diff] = {}
            for metric, agg in metrics.items():
                agg_dict[runner][diff][metric] = agg.to_dict()

    # Per-case flat list
    per_case = []
    for r in results:
        per_case.append({
            "case_id": r["case_id"],
            "runner": r["runner"],
            "difficulty": r.get("difficulty", "Unknown"),
            "scores": r.get("scores", {}),
            "duration_seconds": r.get("duration_seconds", 0),
            "total_tokens": r.get("total_tokens", 0),
        })

    # Summary cards
    baseline_results = [r for r in results if r["runner"] == "baseline"]
    deepagent_results = [r for r in results if r["runner"] == "deepagent"]

    def _avg_tier1(runner_results: list[dict]) -> float:
        if not runner_results:
            return 0.0
        scores = []
        for r in runner_results:
            tier1_scores = [r["scores"].get(m, 0.0) for m in TIER1_METRICS if m in r.get("scores", {})]
            if tier1_scores:
                scores.append(statistics.mean(tier1_scores))
        return statistics.mean(scores) if scores else 0.0

    bl_avg = _avg_tier1(baseline_results)
    da_avg = _avg_tier1(deepagent_results)
    lift = ((da_avg - bl_avg) / bl_avg * 100) if bl_avg > 0 else 0

    summary_cards = [
        {"label": "Cases Evaluated", "value": str(len(set(r["case_id"] for r in results))), "highlight": "neutral"},
        {"label": "Baseline Avg T1", "value": f"{bl_avg:.3f}", "highlight": "baseline"},
        {"label": "Deep Agent Avg T1", "value": f"{da_avg:.3f}", "highlight": "deepagent"},
        {"label": "Deep Agent Lift", "value": f"{lift:+.1f}%", "highlight": "deepagent" if lift > 0 else "baseline"},
        {"label": "Baseline Runs", "value": str(len(baseline_results)), "highlight": "baseline"},
        {"label": "Deep Agent Runs", "value": str(len(deepagent_results)), "highlight": "deepagent"},
    ]

    return {
        "aggregated": agg_dict,
        "operational": operational,
        "per_case": per_case,
        "tier1_metrics": TIER1_METRICS,
        "tier2_metrics": TIER2_METRICS,
        "summary_cards": summary_cards,
    }


# ---------------------------------------------------------------------------
# PNG chart generation (optional, requires matplotlib)
# ---------------------------------------------------------------------------

def generate_png_charts(
    aggregated: dict[str, dict[str, dict[str, MetricAgg]]],
    output_dir: Path,
) -> list[Path]:
    """Generate PNG comparison charts using matplotlib (optional dependency)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print("  [SKIP] matplotlib not installed — PNG charts not generated.")
        print("         Install with: pip install matplotlib")
        return []

    charts_dir = output_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []

    runners = list(aggregated.keys())
    difficulties = DIFFICULTY_ORDER + ["All"]
    colors = {"baseline": "#6366f1", "deepagent": "#10b981"}

    # --- Grouped bar charts for each Tier-1 metric ---
    for metric in TIER1_METRICS:
        fig, ax = plt.subplots(figsize=(8, 5))
        x = np.arange(len(difficulties))
        width = 0.35

        for i, runner in enumerate(runners):
            scores = [
                aggregated.get(runner, {}).get(d, {}).get(metric, MetricAgg()).mean
                for d in difficulties
            ]
            offset = (i - 0.5) * width + width / 2
            bars = ax.bar(x + offset, scores, width, label=RUNNER_LABELS.get(runner, runner),
                         color=colors.get(runner, "#888"), alpha=0.85)
            # Add value labels
            for bar, score in zip(bars, scores):
                if score > 0:
                    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
                           f"{score:.3f}", ha="center", va="bottom", fontsize=8)

        ax.set_ylabel("Score")
        ax.set_title(metric.replace("_", " ").title())
        ax.set_xticks(x)
        ax.set_xticklabels(difficulties)
        ax.set_ylim(0, 1.1)
        ax.legend()
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()

        path = charts_dir / f"{metric}.png"
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        generated.append(path)

    # --- Radar chart: overall comparison ---
    fig, axes = plt.subplots(1, 3, figsize=(18, 6), subplot_kw=dict(polar=True))
    for idx, diff in enumerate(DIFFICULTY_ORDER):
        ax = axes[idx]
        metrics = TIER1_METRICS
        angles = np.linspace(0, 2 * np.pi, len(metrics), endpoint=False).tolist()
        angles += angles[:1]

        for runner in runners:
            values = [
                aggregated.get(runner, {}).get(diff, {}).get(m, MetricAgg()).mean
                for m in metrics
            ]
            values += values[:1]
            ax.plot(angles, values, "o-", label=RUNNER_LABELS.get(runner, runner),
                   color=colors.get(runner, "#888"), linewidth=2)
            ax.fill(angles, values, alpha=0.1, color=colors.get(runner, "#888"))

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels([m.replace("_", "\n") for m in metrics], fontsize=8)
        ax.set_ylim(0, 1.0)
        ax.set_title(f"{diff} Cases", fontsize=12, fontweight="bold", pad=20)
        ax.legend(loc="upper right", fontsize=8)

    fig.suptitle("Tier-1 Metrics: Baseline vs Deep Agent by Difficulty", fontsize=14, fontweight="bold")
    fig.tight_layout()
    path = charts_dir / "radar_by_difficulty.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    generated.append(path)

    # --- Heatmap: improvement delta ---
    fig, ax = plt.subplots(figsize=(10, 6))
    metrics_all = TIER1_METRICS + TIER2_METRICS
    delta_matrix = []
    for metric in metrics_all:
        row = []
        for diff in difficulties:
            bl = aggregated.get("baseline", {}).get(diff, {}).get(metric, MetricAgg()).mean
            da = aggregated.get("deepagent", {}).get(diff, {}).get(metric, MetricAgg()).mean
            row.append(da - bl)
        delta_matrix.append(row)

    delta_arr = np.array(delta_matrix)
    im = ax.imshow(delta_arr, cmap="RdYlGn", aspect="auto", vmin=-0.5, vmax=0.5)
    ax.set_xticks(range(len(difficulties)))
    ax.set_xticklabels(difficulties)
    ax.set_yticks(range(len(metrics_all)))
    ax.set_yticklabels([m.replace("_", " ") for m in metrics_all], fontsize=9)
    ax.set_title("Deep Agent Improvement over Baseline (score delta)")
    fig.colorbar(im, ax=ax, label="Score Delta (green = DA better)")

    # Add text annotations
    for i in range(len(metrics_all)):
        for j in range(len(difficulties)):
            val = delta_arr[i, j]
            color = "white" if abs(val) > 0.25 else "black"
            ax.text(j, i, f"{val:+.3f}", ha="center", va="center", fontsize=8, color=color)

    fig.tight_layout()
    path = charts_dir / "improvement_heatmap.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    generated.append(path)

    return generated


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Path to all_cases_scores.json")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Output directory")
    parser.add_argument("--metrics", nargs="*", default=None, help="Specific metrics to analyze")
    parser.add_argument("--no-png", action="store_true", help="Skip PNG chart generation")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"ERROR: Input file not found: {args.input}")
        print("Run `python run_all_cases_pipeline.py` first to generate scoring data.")
        raise SystemExit(1)

    print(f"Loading scores from: {args.input}")
    results = load_scores(args.input)
    print(f"  Loaded {len(results)} completed runs")

    if not results:
        print("ERROR: No completed runs found in the input file.")
        raise SystemExit(1)

    metrics = args.metrics or ALL_KEY_METRICS
    print(f"  Analyzing {len(metrics)} metrics")

    # Aggregate
    print("\nAggregating scores by runner and difficulty...")
    aggregated = aggregate_metrics(results, metrics)
    operational = compute_operational_summary(results)

    # Print quick console summary
    print("\n" + "=" * 80)
    print("COMPARISON SUMMARY")
    print("=" * 80)
    for difficulty in DIFFICULTY_ORDER + ["All"]:
        print(f"\n  [{difficulty.upper()}]")
        for metric in TIER1_METRICS:
            bl = aggregated.get("baseline", {}).get(difficulty, {}).get(metric, MetricAgg())
            da = aggregated.get("deepagent", {}).get(difficulty, {}).get(metric, MetricAgg())
            delta = da.mean - bl.mean
            arrow = "+" if delta > 0 else "" if delta == 0 else ""
            print(f"    {metric:30s}  BL={bl.mean:.3f}  DA={da.mean:.3f}  delta={arrow}{delta:.3f}")
    print("=" * 80)

    # Generate outputs
    args.output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Comparison summary JSON
    summary = build_comparison_summary(aggregated, operational)
    summary_path = args.output_dir / "comparison_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    print(f"\nComparison summary: {summary_path}")

    # 2. HTML dashboard
    html = _generate_html_report(aggregated, operational, results)
    html_path = args.output_dir / "comparison_report.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"HTML dashboard:     {html_path}")

    # 3. PNG charts (optional)
    if not args.no_png:
        print("\nGenerating PNG charts...")
        charts = generate_png_charts(aggregated, args.output_dir)
        if charts:
            print(f"  Generated {len(charts)} charts in {args.output_dir / 'charts'}")

    print("\nDone.")


if __name__ == "__main__":
    main()
