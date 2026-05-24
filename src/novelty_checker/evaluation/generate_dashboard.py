"""Generate interactive Alpha Gate Dashboard as a self-contained HTML file.

Reads scoring_results.json and batch_summary.json, embeds the data
into an interactive HTML dashboard with clickable heatmap rows.

Usage:
    python -m src.novelty_checker.evaluation.generate_dashboard
    python -m src.novelty_checker.evaluation.generate_dashboard --batch path/to/batch.json --scoring path/to/scoring.json
"""

import json
import argparse
from pathlib import Path

DEFAULT_BATCH = Path("src/novelty_checker/evaluation/results/batch_summary.json")
DEFAULT_SCORING = Path("src/novelty_checker/evaluation/results/scoring_results.json")
DEFAULT_OUTPUT = Path("src/novelty_checker/evaluation/results/alpha_dashboard.html")

TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Alpha Gate Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'DM Sans', sans-serif; background: #0f1117; color: #e1e4ea; }
  .dash { max-width: 1100px; margin: 0 auto; padding: 32px 24px; }
  .dash h1 { font-size: 28px; font-weight: 700; margin-bottom: 4px; }
  .dash h2 { font-size: 16px; font-weight: 600; margin: 0 0 16px; }
  .dash h3 { font-size: 14px; font-weight: 600; margin: 0 0 10px; color: #9ca3af; }
  .subtitle { font-size: 13px; color: #6b7280; margin-bottom: 24px; }
  .gate-banner { border-radius: 16px; padding: 28px 36px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px; }
  .gate-fail { background: linear-gradient(135deg, #450a0a, #7f1d1d); border: 1px solid #ef444433; }
  .gate-pass { background: linear-gradient(135deg, #064e3b, #065f46); border: 1px solid #22c55e33; }
  .gate-result { font-size: 44px; font-weight: 700; }
  .gate-sub { font-size: 14px; color: #9ca3af; margin-top: 4px; }
  .gate-right { text-align: right; }
  .gate-big { font-size: 36px; font-weight: 700; }
  .cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 20px; }
  .card { background: #1a1d27; border-radius: 10px; padding: 14px; text-align: center; border: 1px solid #2a2d3a; }
  .card-label { font-size: 12px; color: #9ca3af; margin-bottom: 3px; }
  .card-value { font-size: 22px; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }
  .panel { background: #1a1d27; border-radius: 12px; padding: 20px 24px; border: 1px solid #2a2d3a; margin-bottom: 20px; }
  .bar-row { margin-bottom: 12px; }
  .bar-header { display: flex; justify-content: space-between; margin-bottom: 3px; font-size: 13px; }
  .bar-val { font-family: 'JetBrains Mono', monospace; font-size: 12px; }
  .bar-track { position: relative; height: 7px; background: #2a2d3a; border-radius: 4px; }
  .bar-fill { height: 100%; border-radius: 4px; }
  .bar-thresh { position: absolute; top: -4px; bottom: -4px; width: 2px; background: #fff; opacity: 0.35; }
  .sep { border-top: 1px solid #2a2d3a; margin: 16px 0; padding-top: 14px; }
  .heatmap { width: 100%; border-collapse: collapse; font-family: 'JetBrains Mono', monospace; font-size: 12px; }
  .heatmap th { text-align: center; padding: 6px 4px; font-size: 11px; font-weight: 500; color: #9ca3af; }
  .heatmap th:first-child, .heatmap th:nth-child(2) { text-align: left; }
  .heatmap td { padding: 5px 6px; text-align: center; }
  .heatmap td:first-child { text-align: left; font-weight: 600; }
  .heatmap td:nth-child(2) { text-align: left; color: #9ca3af; font-size: 11px; }
  .heatmap tr { cursor: pointer; }
  .heatmap tr:hover td { opacity: 0.8; }
  .conf-table { border-collapse: collapse; font-family: 'JetBrains Mono', monospace; font-size: 13px; }
  .conf-table th { padding: 8px 16px; font-weight: 500; color: #9ca3af; font-size: 12px; }
  .conf-table td { padding: 8px 16px; text-align: center; border: 1px solid #2a2d3a; }
  .conf-table td:first-child { text-align: left; font-weight: 600; color: #9ca3af; border: none; }
  .detail-card { background: #22252f; border: 1px solid #3a3d4a; border-radius: 12px; padding: 20px 24px; margin-top: 16px; }
  .detail-title { font-size: 16px; font-weight: 600; margin-bottom: 12px; }
  .detail-row { display: flex; justify-content: space-between; font-size: 13px; padding: 4px 0; border-bottom: 1px solid #2a2d3a; }
  .detail-row:last-child { border-bottom: none; }
  .close-btn { font-size: 12px; cursor: pointer; padding: 4px 14px; margin-bottom: 10px; background: #2a2d3a; border: 1px solid #3a3d4a; color: #e1e4ea; border-radius: 6px; }
  .close-btn:hover { background: #3a3d4a; }
  .diff-chart { display: flex; align-items: flex-end; gap: 32px; justify-content: center; padding: 20px 0; }
  .diff-group { text-align: center; }
  .diff-bars { display: flex; gap: 4px; align-items: flex-end; height: 150px; }
  .diff-bar { width: 32px; border-radius: 4px 4px 0 0; position: relative; }
  .diff-bar-label { position: absolute; top: -18px; left: 0; right: 0; text-align: center; font-size: 11px; font-family: 'JetBrains Mono', monospace; color: #e1e4ea; }
  .diff-name { font-size: 13px; color: #9ca3af; margin-top: 8px; }
  .legend { display: flex; gap: 20px; margin-bottom: 12px; font-size: 12px; color: #9ca3af; }
  .legend-dot { width: 10px; height: 10px; border-radius: 2px; display: inline-block; margin-right: 5px; vertical-align: middle; }
  .failed-item { background: #991b1b15; border-radius: 8px; padding: 12px; margin-bottom: 8px; border: 1px solid #991b1b33; font-size: 13px; }
  .info-btn { display: inline-block; cursor: pointer; padding: 3px 10px; font-size: 12px; background: #2a2d3a; border: 1px solid #3a3d4a; color: #9ca3af; border-radius: 6px; margin-left: 8px; vertical-align: middle; }
  .info-btn:hover { background: #3a3d4a; color: #e1e4ea; }
  .legend-overlay { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.7); z-index: 100; overflow-y: auto; }
  .legend-overlay.active { display: flex; justify-content: center; align-items: flex-start; padding: 40px 20px; }
  .legend-modal { background: #1a1d27; border: 1px solid #2a2d3a; border-radius: 16px; padding: 28px 32px; max-width: 700px; width: 100%; max-height: 90vh; overflow-y: auto; }
  .legend-modal h2 { font-size: 18px; font-weight: 700; margin-bottom: 20px; }
  .legend-close { float: right; cursor: pointer; padding: 4px 12px; font-size: 13px; background: #2a2d3a; border: 1px solid #3a3d4a; color: #e1e4ea; border-radius: 6px; }
  .legend-close:hover { background: #3a3d4a; }
  .legend-section { margin-bottom: 20px; }
  .legend-section h3 { font-size: 14px; font-weight: 600; color: #9ca3af; margin-bottom: 10px; padding-bottom: 6px; border-bottom: 1px solid #2a2d3a; }
  .metric-item { margin-bottom: 12px; padding-left: 12px; border-left: 3px solid #2a2d3a; }
  .metric-item.gate { border-left-color: #6366f1; }
  .metric-name { font-size: 13px; font-weight: 600; margin-bottom: 2px; }
  .metric-desc { font-size: 12px; color: #9ca3af; line-height: 1.5; }
  .metric-thresh { font-size: 11px; font-family: 'JetBrains Mono', monospace; color: #6b7280; margin-top: 2px; }
</style>
</head>
<body>
<div class="dash" id="app"></div>
<script>
var BATCH = %%BATCH_DATA%%;
var SCORING = %%SCORING_DATA%%;

var GATE_METRICS = [
  ["verdict_accuracy","Verdict accuracy",0.60],
  ["prior_art_hit_rate","Prior art hit rate",0.60],
  ["feature_precision","Feature precision",0.60],
  ["feature_recall","Feature recall",0.65],
  ["report_section_completeness","Report completeness",0.70],
  ["tool_error_rate","Tool error rate",0.90]
];
var TIER2 = [["prior_art_recall","Prior art recall"],["search_strategy_adequacy","Search strategy"],["search_reproducibility","Search reproducibility"],["triage_agreement","Triage agreement"],["feature_coverage_accuracy","Feature coverage"]];
var TIER3 = [["cost_per_run","Cost/run"],["latency","Latency"],["token_efficiency","Token efficiency"],["tool_invocations","Tool invocations"],["research_rounds","Research rounds"]];

function color(s, t) {
  if (t && s >= t) return "#22c55e";
  if (s >= 0.5) return "#f59e0b";
  return "#ef4444";
}

function cellBg(s) {
  if (s == null) return "#1a1d27";
  if (s >= 0.8) return "#166534";
  if (s >= 0.6) return "#365314";
  if (s >= 0.4) return "#854d0e";
  if (s >= 0.2) return "#92400e";
  return "#991b1b";
}

var selectedFixture = null;

function render() {
  var s = SCORING.suite_summary || {};
  var g = SCORING.gate_result || {};
  var gKeys = Object.keys(g);
  var gp = 0;
  for (var i = 0; i < gKeys.length; i++) { if (g[gKeys[i]]) gp++; }
  var gt = gKeys.length;
  var ap = SCORING.alpha_passed;
  var allFixtures = BATCH.fixture_results || [];
  var completed = [];
  var failed = [];
  for (var i = 0; i < allFixtures.length; i++) {
    if (allFixtures[i].status === "completed") completed.push(allFixtures[i]);
    if (allFixtures[i].status === "failed") failed.push(allFixtures[i]);
  }

  var h = "";

  h += "<h1>Alpha gate evaluation dashboard <span class='info-btn' onclick='toggleLegend()'>? Metric guide</span></h1>";
  h += '<div class="subtitle">Config: ' + (BATCH.config_name || "?") + " | Model: " + (BATCH.model || "?") + " | HITL: " + (BATCH.hitl_mode || "?") + "</div>";

  h += '<div class="legend-overlay" id="legendOverlay" onclick="if(event.target===this)toggleLegend()">';
  h += '<div class="legend-modal">';
  h += '<button class="legend-close" onclick="toggleLegend()">Close</button>';
  h += '<h2>Metric guide</h2>';

  h += '<div class="legend-section"><h3>Tier-1 gate metrics (pass/fail)</h3>';
  h += '<div class="metric-item gate"><div class="metric-name">Verdict accuracy</div><div class="metric-desc">Does the agent reach the same novelty conclusion (novel / partially novel / not novel) as the SME? Binary per fixture, averaged across the suite.</div><div class="metric-thresh">Threshold: 60%</div></div>';
  h += '<div class="metric-item gate"><div class="metric-name">Prior art hit rate</div><div class="metric-desc">Did the agent find at least one reference that the SME identified as relevant (A or B level)? Binary per fixture.</div><div class="metric-thresh">Threshold: 60%</div></div>';
  h += '<div class="metric-item gate"><div class="metric-name">Prior art recall</div><div class="metric-desc">What fraction of the SME-identified A-level (blocking) references did the agent find? Uses family-level patent number matching.</div><div class="metric-thresh">Threshold: 40%</div></div>';
  h += '<div class="metric-item gate"><div class="metric-name">Feature precision</div><div class="metric-desc">Of the features the agent extracted, what fraction match a ground truth feature? Measures whether the agent invents spurious features. Uses hybrid text similarity (lexical + semantic embeddings).</div><div class="metric-thresh">Threshold: 70%</div></div>';
  h += '<div class="metric-item gate"><div class="metric-name">Feature recall</div><div class="metric-desc">Of the ground truth features, what fraction did the agent extract? Measures whether the agent misses important features.</div><div class="metric-thresh">Threshold: 65%</div></div>';
  h += '<div class="metric-item gate"><div class="metric-name">Report completeness</div><div class="metric-desc">Are all required report sections present? Checks for executive summary, scope, feature matrix, search strategy, prior art analysis, feature coverage, risk assessment, recommendations, limitations, and references.</div><div class="metric-thresh">Threshold: 80%</div></div>';
  h += '<div class="metric-item gate"><div class="metric-name">Tool error rate</div><div class="metric-desc">Score = 1 - (failed tool calls / total tool calls). Measures agent reliability in tool usage.</div><div class="metric-thresh">Threshold: 90%</div></div>';
  h += '</div>';

  h += '<div class="legend-section"><h3>Tier-2 diagnostic (no gate)</h3>';
  h += '<div class="metric-item"><div class="metric-name">Search strategy</div><div class="metric-desc">Does the agent use appropriate CPC/IPC codes and keyword strategies matching the SME-defined search approach?</div></div>';
  h += '<div class="metric-item"><div class="metric-name">Search reproducibility</div><div class="metric-desc">Are all search queries fully logged with arguments in telemetry? Enables audit trail.</div></div>';
  h += '<div class="metric-item"><div class="metric-name">Triage agreement</div><div class="metric-desc">Does the agent assign the same triage label (A/B/C) to references as the SME?</div></div>';
  h += '<div class="metric-item"><div class="metric-name">Feature coverage</div><div class="metric-desc">Does the agent correctly map which features are covered by which references, matching SME coverage assessments?</div></div>';
  h += '</div>';

  h += '<div class="legend-section"><h3>Tier-3 operational (no gate)</h3>';
  h += '<div class="metric-item"><div class="metric-name">Cost/run</div><div class="metric-desc">Estimated LLM cost per fixture. Score = 1 - (cost / $15 max). Lower cost = higher score.</div></div>';
  h += '<div class="metric-item"><div class="metric-name">Latency</div><div class="metric-desc">Total wall-clock time per fixture. Score = 1 - (duration / 3600s max).</div></div>';
  h += '<div class="metric-item"><div class="metric-name">Token efficiency</div><div class="metric-desc">Tokens consumed per reference found. Score = 1 - (tokens_per_ref / 250K max). Lower token usage per reference = higher score.</div></div>';
  h += '<div class="metric-item"><div class="metric-name">Tool invocations</div><div class="metric-desc">Total tool calls per run. Score = 1 - (calls / 200 max). Tracks agent chattiness.</div></div>';
  h += '<div class="metric-item"><div class="metric-name">Research rounds</div><div class="metric-desc">Number of search-reflect-decide iterations. Score = 1.0 for 2-4 rounds, 0.5 for 1 or 5, 0.0 for 0.</div></div>';
  h += '</div>';

  h += '</div></div>';

  h += '<div class="gate-banner ' + (ap ? "gate-pass" : "gate-fail") + '">';
  h += '<div><div class="gate-result" style="color:' + (ap ? "#22c55e" : "#ef4444") + '">' + (ap ? "PASSED" : "NOT PASSED") + "</div>";
  h += '<div class="gate-sub">' + gp + " of " + gt + " gate metrics met threshold</div></div>";
  h += '<div class="gate-right"><div class="gate-big">' + completed.length + "</div>";
  h += '<div class="gate-sub">' + failed.length + " failed | $" + (BATCH.total_estimated_cost_usd || 0).toFixed(2) + " cost</div></div></div>";

  var tc = 0, td = 0;
  for (var i = 0; i < completed.length; i++) {
    tc += (completed[i].estimated_cost_usd || 0);
    td += (completed[i].duration_seconds || 0) / 60;
  }
  h += '<div class="cards">';
  h += '<div class="card"><div class="card-label">Total cost</div><div class="card-value">$' + tc.toFixed(0) + "</div></div>";
  h += '<div class="card"><div class="card-label">Avg cost</div><div class="card-value">$' + (completed.length ? (tc / completed.length).toFixed(2) : "0") + "</div></div>";
  h += '<div class="card"><div class="card-label">Total time</div><div class="card-value">' + (td / 60).toFixed(1) + "h</div></div>";
  h += '<div class="card"><div class="card-label">Avg time</div><div class="card-value">' + (completed.length ? (td / completed.length).toFixed(0) : "0") + "m</div></div>";
  h += "</div>";

  h += '<div class="grid2">';

  h += '<div class="panel"><h2>Tier-1 gate metrics</h2>';
  for (var i = 0; i < GATE_METRICS.length; i++) {
    var k = GATE_METRICS[i][0], n = GATE_METRICS[i][1], t = GATE_METRICS[i][2];
    var v = s[k] || 0;
    var p = Math.round(v * 100);
    var tp = Math.round(t * 100);
    h += '<div class="bar-row"><div class="bar-header"><span>' + n + '</span><span class="bar-val" style="color:' + color(v, t) + '">' + p + "%</span></div>";
    h += '<div class="bar-track"><div class="bar-fill" style="width:' + Math.min(p, 100) + "%;background:" + color(v, t) + '"></div>';
    h += '<div class="bar-thresh" style="left:' + tp + '%"></div></div></div>';
  }
  h += '<div class="sep"><h3>Tier-2 diagnostic</h3>';
  for (var i = 0; i < TIER2.length; i++) {
    var v = s[TIER2[i][0]] || 0; var p = Math.round(v * 100);
    h += '<div class="bar-row"><div class="bar-header"><span>' + TIER2[i][1] + '</span><span class="bar-val" style="color:' + color(v) + '">' + p + "%</span></div>";
    h += '<div class="bar-track"><div class="bar-fill" style="width:' + Math.min(p, 100) + "%;background:" + color(v) + '"></div></div></div>';
  }
  h += '</div><div class="sep"><h3>Tier-3 operational</h3>';
  for (var i = 0; i < TIER3.length; i++) {
    var v = s[TIER3[i][0]] || 0; var p = Math.round(v * 100);
    h += '<div class="bar-row"><div class="bar-header"><span>' + TIER3[i][1] + '</span><span class="bar-val" style="color:' + color(v) + '">' + p + "%</span></div>";
    h += '<div class="bar-track"><div class="bar-fill" style="width:' + Math.min(p, 100) + "%;background:" + color(v) + '"></div></div></div>';
  }
  h += "</div></div>";

  h += "<div>";

  var verdicts = ["novel", "partially_novel", "not_novel"];
  var vl = {"novel": "Novel", "partially_novel": "Partial", "not_novel": "Not novel"};
  var mx = {};
  for (var i = 0; i < verdicts.length; i++) {
    mx[verdicts[i]] = {};
    for (var j = 0; j < verdicts.length; j++) { mx[verdicts[i]][verdicts[j]] = 0; }
  }
  for (var i = 0; i < completed.length; i++) {
    var fs = SCORING.fixture_results[completed[i].case_id] || [];
    for (var j = 0; j < fs.length; j++) {
      if (fs[j].metric_name === "verdict_accuracy" && fs[j].evidence) {
        var gt2 = fs[j].evidence.expected_verdict || "";
        var ag = fs[j].evidence.agent_verdict || "";
        if (mx[gt2] && mx[gt2][ag] !== undefined) mx[gt2][ag]++;
      }
    }
  }
  h += '<div class="panel" style="margin-bottom:16px"><h2>Verdict confusion matrix</h2>';
  h += '<div style="font-size:12px;color:#6b7280;margin-bottom:10px">Rows = ground truth | Columns = agent</div>';
  h += '<table class="conf-table"><thead><tr><th></th>';
  for (var i = 0; i < verdicts.length; i++) { h += "<th>" + vl[verdicts[i]] + "</th>"; }
  h += "</tr></thead><tbody>";
  for (var i = 0; i < verdicts.length; i++) {
    h += "<tr><td>" + vl[verdicts[i]] + "</td>";
    for (var j = 0; j < verdicts.length; j++) {
      var c = mx[verdicts[i]][verdicts[j]];
      var ok = verdicts[i] === verdicts[j];
      var bg = c > 0 ? (ok ? "#16653430" : "#991b1b30") : "transparent";
      var cl = c > 0 ? (ok ? "#22c55e" : "#ef4444") : "#4b5563";
      h += '<td style="background:' + bg + ";color:" + cl + ";font-weight:" + (c > 0 ? 700 : 400) + '">' + c + "</td>";
    }
    h += "</tr>";
  }
  h += "</tbody></table></div>";

  if (failed.length) {
    h += '<div class="panel" style="border-color:#ef444433"><h3 style="color:#ef4444">Failed fixtures</h3>';
    for (var i = 0; i < failed.length; i++) {
      h += '<div class="failed-item"><span style="font-weight:600">' + failed[i].case_id + "</span> ";
      h += '<span style="color:#9ca3af">' + Math.round((failed[i].duration_seconds || 0) / 60) + "m</span>";
      h += '<div style="color:#f87171;font-size:12px;margin-top:3px">' + ((failed[i].error || "Unknown").substring(0, 130)) + "</div></div>";
    }
    h += "</div>";
  }

  h += "</div></div>";

  var short = {"verdict_accuracy":"Verdict","prior_art_hit_rate":"PA hit","prior_art_recall":"PA rec","feature_precision":"F prec","feature_recall":"F rec","report_section_completeness":"Report","tool_error_rate":"Tool err"};
  var mk = [];
  for (var i = 0; i < GATE_METRICS.length; i++) mk.push(GATE_METRICS[i][0]);
  h += '<div class="panel"><h2>Per-fixture heatmap</h2>';
  h += '<div style="font-size:12px;color:#6b7280;margin-bottom:10px">Click a row to see fixture details</div>';
  h += '<table class="heatmap"><thead><tr><th>Case</th><th>Diff</th>';
  for (var i = 0; i < mk.length; i++) { h += "<th>" + short[mk[i]] + "</th>"; }
  h += "</tr></thead><tbody>";
  for (var fi = 0; fi < completed.length; fi++) {
    var f = completed[fi];
    var scores = {};
    var fs = SCORING.fixture_results[f.case_id] || [];
    for (var j = 0; j < fs.length; j++) { scores[fs[j].metric_name] = fs[j].score; }
    h += '<tr onclick="selectFixture(\'' + f.case_id + '\')">';
    h += "<td>" + f.case_id + "</td><td>" + (f.difficulty || "?") + "</td>";
    for (var j = 0; j < mk.length; j++) {
      var sv = scores[mk[j]];
      h += '<td style="background:' + cellBg(sv) + '">' + (sv != null ? Math.round(sv * 100) : "-") + "</td>";
    }
    h += "</tr>";
  }
  h += "</tbody></table></div>";

  var byDiff = {};
  for (var i = 0; i < completed.length; i++) {
    var d = completed[i].difficulty || "?";
    if (!byDiff[d]) byDiff[d] = {count: 0, m: {}};
    byDiff[d].count++;
    var fs = SCORING.fixture_results[completed[i].case_id] || [];
    for (var j = 0; j < fs.length; j++) {
      if (!byDiff[d].m[fs[j].metric_name]) byDiff[d].m[fs[j].metric_name] = [];
      byDiff[d].m[fs[j].metric_name].push(fs[j].score);
    }
  }
  var sel = ["verdict_accuracy", "prior_art_recall", "feature_recall"];
  var selN = {"verdict_accuracy": "Verdict", "prior_art_recall": "PA recall", "feature_recall": "F recall"};
  var selC = ["#6366f1", "#f59e0b", "#22c55e"];
  h += '<div class="panel"><h2>Score by difficulty</h2><div class="legend">';
  for (var i = 0; i < sel.length; i++) {
    h += '<span><span class="legend-dot" style="background:' + selC[i] + '"></span>' + selN[sel[i]] + "</span>";
  }
  h += '</div><div class="diff-chart">';
  var diffOrder = ["Easy", "Medium", "Hard"];
  for (var di = 0; di < diffOrder.length; di++) {
    var d = diffOrder[di];
    if (!byDiff[d]) continue;
    var data = byDiff[d];
    h += '<div class="diff-group"><div class="diff-bars">';
    for (var i = 0; i < sel.length; i++) {
      var vals = data.m[sel[i]] || [];
      var sum = 0; for (var j = 0; j < vals.length; j++) sum += vals[j];
      var avg = vals.length ? sum / vals.length : 0;
      var ht = Math.max(3, avg * 150);
      h += '<div class="diff-bar" style="height:' + ht + "px;background:" + selC[i] + '"><div class="diff-bar-label">' + Math.round(avg * 100) + "%</div></div>";
    }
    h += '</div><div class="diff-name">' + d + " (" + data.count + ")</div></div>";
  }
  h += "</div></div>";

  h += '<div id="detail"></div>';

  document.getElementById("app").innerHTML = h;
}

function selectFixture(caseId) {
  if (selectedFixture === caseId) {
    selectedFixture = null;
    document.getElementById("detail").innerHTML = "";
    return;
  }
  selectedFixture = caseId;
  var fr = null;
  var allFixtures = BATCH.fixture_results || [];
  for (var i = 0; i < allFixtures.length; i++) {
    if (allFixtures[i].case_id === caseId) { fr = allFixtures[i]; break; }
  }
  var fs = SCORING.fixture_results[caseId] || [];
  var d = '<div class="detail-card">';
  d += '<button class="close-btn" onclick="selectFixture(\'' + caseId + '\')">Close</button>';
  d += '<div class="detail-title">' + caseId + " \u2014 " + (fr.difficulty || "?") + " difficulty</div>";
  d += '<div class="detail-row"><span>Duration</span><span style="font-family:JetBrains Mono,monospace">' + Math.round((fr.duration_seconds || 0) / 60) + " min</span></div>";
  d += '<div class="detail-row"><span>Cost</span><span style="font-family:JetBrains Mono,monospace">$' + (fr.estimated_cost_usd || 0).toFixed(2) + "</span></div>";
  d += '<div class="detail-row"><span>Turns</span><span style="font-family:JetBrains Mono,monospace">' + (fr.total_turns || "?") + "</span></div>";

  var vr = null;
  for (var i = 0; i < fs.length; i++) {
    if (fs[i].metric_name === "verdict_accuracy") { vr = fs[i]; break; }
  }
  if (vr && vr.evidence) {
    d += '<div class="detail-row"><span>GT verdict</span><span>' + (vr.evidence.expected_verdict || "?") + "</span></div>";
    var vc = vr.score >= 1 ? "#22c55e" : "#ef4444";
    d += '<div class="detail-row"><span>Agent verdict</span><span style="color:' + vc + '">' + (vr.evidence.agent_verdict || "?") + "</span></div>";
  }
  d += '<div style="margin-top:14px;border-top:1px solid #2a2d3a;padding-top:14px"><h3 style="font-size:14px;font-weight:600;margin-bottom:10px;color:#9ca3af">All metrics</h3>';
  for (var i = 0; i < fs.length; i++) {
    var gm = null;
    for (var j = 0; j < GATE_METRICS.length; j++) {
      if (GATE_METRICS[j][0] === fs[i].metric_name) { gm = GATE_METRICS[j]; break; }
    }
    var thresh = gm ? gm[2] : null;
    var passed = thresh ? fs[i].score >= thresh : fs[i].score >= 0.5;
    var mc = passed ? "#22c55e" : "#ef4444";
    d += '<div class="detail-row"><span>' + fs[i].metric_name.replace(/_/g, " ") + "</span>";
    d += '<span style="font-family:JetBrains Mono,monospace;font-size:13px;color:' + mc + '">' + Math.round(fs[i].score * 100) + "%</span></div>";
  }
  d += "</div></div>";
  document.getElementById("detail").innerHTML = d;
  document.getElementById("detail").scrollIntoView({behavior: "smooth"});
}

function toggleLegend() {
  var overlay = document.getElementById("legendOverlay");
  if (overlay.classList.contains("active")) {
    overlay.classList.remove("active");
    document.body.style.overflow = "";
  } else {
    overlay.classList.add("active");
    document.body.style.overflow = "hidden";
  }
}

render();
</script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Generate Alpha Gate Dashboard")
    parser.add_argument("--batch", type=Path, default=DEFAULT_BATCH)
    parser.add_argument("--scoring", type=Path, default=DEFAULT_SCORING)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    with open(args.batch) as f:
        batch = json.load(f)
    with open(args.scoring) as f:
        scoring = json.load(f)

    # Inject difficulty from fixture meta if not in batch
    for fr in batch.get("fixture_results", []):
        if "difficulty" not in fr:
            case_id = fr.get("case_id", "")
            for fname in ("fixture_meta.yaml", "metadata.yaml"):
                meta_file = Path("src/novelty_checker/evaluation/fixtures") / case_id / fname
                if meta_file.exists():
                    try:
                        import yaml
                        with open(meta_file) as mf:
                            meta = yaml.safe_load(mf)
                        fr["difficulty"] = meta.get("difficulty", "?")
                    except Exception:
                        pass
                    break

    batch_json = json.dumps(batch, ensure_ascii=True)
    scoring_json = json.dumps(scoring, ensure_ascii=True)

    html = TEMPLATE.replace("%%BATCH_DATA%%", batch_json).replace("%%SCORING_DATA%%", scoring_json)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Dashboard written to {args.output}")
    print(f"Open in browser: file://{args.output.resolve()}")


if __name__ == "__main__":
    main()