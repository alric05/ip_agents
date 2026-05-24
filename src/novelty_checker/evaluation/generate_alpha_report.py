"""Generate Alpha Gate Report from batch and scoring results.

Generic report generator - works with any batch run. 
Usage:
    python generate_alpha_report.py
    python generate_alpha_report.py --batch path/to/batch_summary.json --scoring path/to/scoring_results.json
"""

import json
import argparse
from pathlib import Path
from datetime import datetime

DEFAULT_BATCH = Path("src/novelty_checker/evaluation/results/batch_summary.json")
DEFAULT_SCORING = Path("src/novelty_checker/evaluation/results/scoring_results.json")
DEFAULT_FIXTURES = Path("src/novelty_checker/evaluation/fixtures")


GATE_METRICS = {
    "verdict_accuracy": "Verdict Accuracy",
    "prior_art_hit_rate": "Prior Art Hit Rate",
    "prior_art_recall": "Prior Art Recall",
    "feature_precision": "Feature Precision",
    "feature_recall": "Feature Recall",
    "report_section_completeness": "Report Completeness",
    "tool_error_rate": "Tool Error Rate",
}

OTHER_METRICS = {
    "search_strategy_adequacy": "Search Strategy",
    "search_reproducibility": "Search Reproducibility",
    "latency": "Latency",
    "token_efficiency": "Token Efficiency",
    "cost_per_run": "Cost per Run",
    "tool_invocations": "Tool Invocations",
    "research_rounds": "Research Rounds",
    "triage_agreement": "Triage Agreement",
    "feature_coverage_accuracy": "Feature Coverage Accuracy",
}


def load_fixture_meta(case_id, fixtures_dir):
    for fname in ("fixture_meta.yaml", "metadata.yaml"):
        meta_file = fixtures_dir / case_id / fname
        if meta_file.exists():
            try:
                import yaml
                with open(meta_file) as f:
                    meta = yaml.safe_load(f)
                return meta.get("domain", "?"), meta.get("difficulty", "?")
            except Exception:
                pass
    return "?", "?"


def get_per_fixture_scores(scoring):
    per_fixture = {}
    fixture_results = scoring.get("fixture_results", {})

    if isinstance(fixture_results, dict):
        for case_id, results in fixture_results.items():
            scores = {}
            if isinstance(results, list):
                for r in results:
                    scores[r.get("metric_name", "")] = {
                        "score": r.get("score", 0.0),
                        "passed": r.get("passed", False),
                        "failures": r.get("failures", []),
                        "evidence": r.get("evidence", {}),
                    }
            per_fixture[case_id] = scores
    elif isinstance(fixture_results, list):
        scores = {}
        for r in fixture_results:
            scores[r.get("metric_name", "")] = {
                "score": r.get("score", 0.0),
                "passed": r.get("passed", False),
                "failures": r.get("failures", []),
                "evidence": r.get("evidence", {}),
            }
        per_fixture["single"] = scores

    return per_fixture


def generate_report(batch, scoring, fixtures_dir):
    lines = []

    # Header
    lines.append("# Alpha Gate Evaluation Report")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append(f"**Config:** {batch.get('config_name', 'N/A')}")
    lines.append(f"**Model:** {batch.get('model', 'N/A')}")
    lines.append(f"**HITL Mode:** {batch.get('hitl_mode', 'N/A')}")
    lines.append("")

    # 1. Executive Summary
    lines.append("## 1. Executive Summary")
    lines.append("")

    alpha_passed = scoring.get("alpha_passed", False)
    gate_result = scoring.get("gate_result", {})
    gates_passed = sum(1 for v in gate_result.values() if v)
    gates_total = len(gate_result)
    result_str = "PASSED" if alpha_passed else "FAILED"

    total = batch.get("total_fixtures", 0)
    completed = batch.get("completed", 0)
    failed = batch.get("failed", 0)
    skipped = batch.get("skipped", 0)
    total_cost = batch.get("total_estimated_cost_usd", 0)
    total_duration = batch.get("total_duration_seconds", 0)

    lines.append(f"**Alpha Gate Result: {result_str}** ({gates_passed}/{gates_total} gate metrics passed)")
    lines.append("")
    lines.append(f"- Fixtures evaluated: {completed} of {total} ({failed} failed, {skipped} skipped)")
    lines.append(f"- Total cost: ${total_cost:.2f}")
    lines.append(f"- Total duration: {total_duration / 3600:.1f} hours")
    if completed > 0:
        lines.append(f"- Average cost per fixture: ${total_cost / completed:.2f}")
        lines.append(f"- Average duration per fixture: {total_duration / completed / 60:.0f} minutes")
    lines.append("")

    # 2. Tier-1 Gate Metrics
    lines.append("## 2. Tier-1 Gate Metrics")
    lines.append("")
    lines.append("| Metric | Score | Status |")
    lines.append("|--------|------:|--------|")

    suite = scoring.get("suite_summary", {})
    for key, name in GATE_METRICS.items():
        score = suite.get(key, 0.0)
        passed = gate_result.get(key, False)
        status = "PASS" if passed else "FAIL"
        lines.append(f"| {name} | {score:.4f} | {status} |")
    lines.append("")

    # 3. Tier-2/3 Metrics
    lines.append("## 3. Tier-2 and Tier-3 Metrics")
    lines.append("")
    lines.append("| Metric | Score |")
    lines.append("|--------|------:|")
    for key, name in OTHER_METRICS.items():
        score = suite.get(key, 0.0)
        lines.append(f"| {name} | {score:.4f} |")
    lines.append("")

    # 4. Per-Fixture Batch Results
    lines.append("## 4. Per-Fixture Batch Results")
    lines.append("")
    lines.append("| Case ID | Domain | Difficulty | Duration | Cost | Turns | Status |")
    lines.append("|---------|--------|------------|----------|------|-------|--------|")

    for fr in batch.get("fixture_results", []):
        case_id = fr.get("case_id", "?")
        status = fr.get("status", "?")
        duration = fr.get("duration_seconds", 0)
        cost = fr.get("estimated_cost_usd", 0)
        turns = fr.get("total_turns", 0)
        domain, difficulty = load_fixture_meta(case_id, fixtures_dir)
        lines.append(f"| {case_id} | {domain} | {difficulty} | {duration / 60:.0f} min | ${cost:.2f} | {turns} | {status} |")
    lines.append("")

    # 5. Per-Fixture Metric Scores
    per_fixture = get_per_fixture_scores(scoring)
    if per_fixture:
        lines.append("## 5. Per-Fixture Metric Scores (Tier-1)")
        lines.append("")

        metric_short = {
            "verdict_accuracy": "Verdict",
            "prior_art_hit_rate": "PA Hit",
            "prior_art_recall": "PA Recall",
            "feature_precision": "F Prec",
            "feature_recall": "F Recall",
            "report_section_completeness": "Report",
            "tool_error_rate": "Tool Err",
        }
        metric_keys = list(GATE_METRICS.keys())

        header = "| Case ID | " + " | ".join(metric_short.get(k, k) for k in metric_keys) + " |"
        sep = "|---------|" + "|".join("------:" for _ in metric_keys) + "|"
        lines.append(header)
        lines.append(sep)

        for case_id, scores in sorted(per_fixture.items()):
            row = f"| {case_id} "
            for key in metric_keys:
                if key in scores:
                    s = scores[key]["score"]
                    row += f"| {s:.2f} "
                else:
                    row += "| ERR "
            row += "|"
            lines.append(row)
        lines.append("")

    # 6. Failed Fixtures
    failed_fixtures = [fr for fr in batch.get("fixture_results", []) if fr.get("status") == "failed"]
    if failed_fixtures:
        lines.append("## 6. Failed Fixtures")
        lines.append("")
        lines.append("| Case ID | Error | Duration |")
        lines.append("|---------|-------|----------|")
        for fr in failed_fixtures:
            case_id = fr.get("case_id", "?")
            error = str(fr.get("error", "Unknown"))
            duration = fr.get("duration_seconds", 0)
            if len(error) > 120:
                error = error[:120] + "..."
            lines.append(f"| {case_id} | {error} | {duration / 60:.0f} min |")
        lines.append("")

    # 7. Scorer Errors
    scorer_errors = []
    for case_id, scores in per_fixture.items():
        for metric_name, data in scores.items():
            for failure in data.get("failures", []):
                if failure.get("type") == "scorer_error":
                    scorer_errors.append({
                        "case_id": case_id,
                        "metric": metric_name,
                        "error": failure.get("evidence", "Unknown"),
                    })

    if scorer_errors:
        lines.append("## 7. Scorer Errors")
        lines.append("")
        lines.append("| Case ID | Metric | Error |")
        lines.append("|---------|--------|-------|")
        for err in scorer_errors:
            error_str = str(err["error"])
            if len(error_str) > 100:
                error_str = error_str[:100] + "..."
            lines.append(f"| {err['case_id']} | {err['metric']} | {error_str} |")
        lines.append("")

    # 8. Cost and Duration
    lines.append("## 8. Cost and Duration Summary")
    lines.append("")
    completed_fixtures = [fr for fr in batch.get("fixture_results", []) if fr.get("status") == "completed"]
    if completed_fixtures:
        costs = [fr.get("estimated_cost_usd", 0) for fr in completed_fixtures]
        durations = [fr.get("duration_seconds", 0) for fr in completed_fixtures]
        lines.append(f"- Total cost: ${sum(costs):.2f}")
        lines.append(f"- Min / Max cost: ${min(costs):.2f} / ${max(costs):.2f}")
        lines.append(f"- Mean cost: ${sum(costs) / len(costs):.2f}")
        lines.append(f"- Total duration: {sum(durations) / 3600:.1f} hours")
        lines.append(f"- Min / Max duration: {min(durations) / 60:.0f} min / {max(durations) / 60:.0f} min")
        lines.append(f"- Mean duration: {sum(durations) / len(durations) / 60:.0f} min")
    lines.append("")

    # 9. Breakdown by Difficulty
    lines.append("## 9. Score Breakdown by Difficulty")
    lines.append("")

    difficulty_scores = {}
    for fr in completed_fixtures:
        case_id = fr.get("case_id", "?")
        _, difficulty = load_fixture_meta(case_id, fixtures_dir)
        if difficulty not in difficulty_scores:
            difficulty_scores[difficulty] = {"count": 0, "metrics": {}}
        difficulty_scores[difficulty]["count"] += 1
        if case_id in per_fixture:
            for mk in GATE_METRICS:
                if mk in per_fixture[case_id]:
                    score = per_fixture[case_id][mk]["score"]
                    difficulty_scores[difficulty]["metrics"].setdefault(mk, []).append(score)

    if difficulty_scores:
        sel_metrics = list(GATE_METRICS.keys())
        metric_short = {
            "verdict_accuracy": "Verdict",
            "prior_art_hit_rate": "PA Hit",
            "prior_art_recall": "PA Recall",
            "feature_precision": "F Prec",
            "feature_recall": "F Recall",
            "report_section_completeness": "Report",
            "tool_error_rate": "Tool Err",
        }
        header = "| Difficulty | Count | " + " | ".join(metric_short.get(k, k) for k in sel_metrics) + " |"
        sep = "|------------|------:|" + "|".join("------:" for _ in sel_metrics) + "|"
        lines.append(header)
        lines.append(sep)

        for diff in sorted(difficulty_scores.keys()):
            data = difficulty_scores[diff]
            row = f"| {diff} | {data['count']} "
            for key in sel_metrics:
                vals = data["metrics"].get(key, [])
                if vals:
                    mean = sum(vals) / len(vals)
                    row += f"| {mean:.2f} "
                else:
                    row += "| --- "
            row += "|"
            lines.append(row)
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate Alpha Gate Report")
    parser.add_argument("--batch", type=Path, default=DEFAULT_BATCH)
    parser.add_argument("--scoring", type=Path, default=DEFAULT_SCORING)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    with open(args.batch) as f:
        batch = json.load(f)
    with open(args.scoring) as f:
        scoring = json.load(f)

    output = args.output or args.scoring.parent / "alpha_gate_report.md"
    report = generate_report(batch, scoring, args.fixtures)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        f.write(report)

    alpha_passed = scoring.get("alpha_passed", False)
    print(f"Report written to {output}")
    print(f"Alpha Gate: {'PASSED' if alpha_passed else 'FAILED'}")


if __name__ == "__main__":
    main()