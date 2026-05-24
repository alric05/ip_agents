"""Run scorers on all completed sessions from a batch run.

Reads batch_summary.json to find session paths, runs all scorers
on each, then produces an aggregated scoring profile.

Usage:
    python run_all_scorers.py
"""

import json
import sys
from pathlib import Path

from src.novelty_checker.evaluation.scorers.runner import score_fixture, get_all_scorers
from src.novelty_checker.evaluation.scorers.profile import ScoringProfile

BATCH_SUMMARY = Path("src/novelty_checker/evaluation/results/batch_summary_final.json")
FIXTURES_DIR = Path("src/novelty_checker/evaluation/fixtures")
SESSIONS_DIR = Path("sessions")


def main():
    with open(BATCH_SUMMARY) as f:
        batch = json.load(f)

    scorers = get_all_scorers()
    all_results = {}

    for fr in batch["fixture_results"]:
        case_id = fr["case_id"]
        session_id = fr.get("session_id", "")
        status = fr["status"]

        if status != "completed" or not session_id:
            print(f"SKIP {case_id} (status={status})")
            continue

        session_path = SESSIONS_DIR / session_id
        fixture_path = FIXTURES_DIR / case_id

        if not session_path.exists():
            print(f"SKIP {case_id} - session not found: {session_path}")
            continue
        if not fixture_path.exists():
            print(f"SKIP {case_id} - fixture not found: {fixture_path}")
            continue

        print(f"\nScoring {case_id} (session={session_id})...")
        results = score_fixture(session_path, fixture_path, scorers)
        all_results[case_id] = results

    if not all_results:
        print("No fixtures scored.")
        sys.exit(1)

    profile = ScoringProfile.from_results(all_results)
    print(profile.summary_table())

    output_path = Path("src/novelty_checker/evaluation/results/scoring_results.json")
    profile.to_json(output_path)
    print(f"\nResults written to {output_path}")

if __name__ == "__main__":
    main()