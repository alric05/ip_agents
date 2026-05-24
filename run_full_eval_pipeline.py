"""Run the complete evaluation pipeline: eval_runner + checklist + trace_writer.

Usage:
    cd ~/Documents/Projects/dw-rnd-unified-agent
    source venv/bin/activate
    python run_full_pipeline.py
"""

from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent / ".env")

from src.novelty_checker.eval_runner import run_novelty_check_e2e
from src.novelty_checker.evaluation.eval_checklist import run_functional_checklist
from src.novelty_checker.evaluation.trace_writer import write_eval_trace

# Step 1: Run the agent
print("Step 1: Running evaluation...")
result = run_novelty_check_e2e(
    idea="A wearable wrist device that monitors blood oxygen levels using dual-wavelength infrared LEDs and provides haptic vibration alerts when saturation drops below a configurable threshold, designed for sleep apnea patients",
    max_turns=5,
)
print(f"  Phase: {result.final_phase.name}")
print(f"  Turns: {result.total_turns}")
print(f"  Duration: {result.total_duration_seconds:.1f}s")
print(f"  Model: {result.model_name}")
print(f"  Error: {result.error}")

# Show enriched turn data
print("\n  Turn details:")
for turn in result.turns:
    tokens = f"{turn.token_usage.total_tokens:,}" if turn.token_usage else "n/a"
    gate = f" [GATE: {turn.gate_event['gate_name']}]" if turn.gate_event else ""
    print(f"    Turn {turn.turn_number}: {turn.phase.name} | {len(turn.tool_call_details)} tool calls | {tokens} tokens | {turn.duration_seconds:.1f}s{gate}")
    for tc in turn.tool_call_details[:5]:
        status = "OK" if tc.success else "FAIL"
        print(f"      {tc.name} [{status}] -> {tc.output_size_chars} chars")
    if len(turn.tool_call_details) > 5:
        print(f"      ... and {len(turn.tool_call_details) - 5} more")

# Step 2: Run the checklist
print("\nStep 2: Running functional checklist...")
checklist = run_functional_checklist(result)
print(f"  Overall: {'PASSED' if checklist.passed else 'FAILED'}")
for name, passed in checklist.checks.items():
    status = "PASS" if passed else "FAIL"
    print(f"    [{status}] {name}: {checklist.details[name]}")

# Step 3: Write unified trace
print("\nStep 3: Writing eval_trace.json...")
trace = write_eval_trace(result, checklist)
trace_path = result.session_path / "eval_trace.json"
print(f"  Written to: {trace_path}")
print(f"  File size: {trace_path.stat().st_size:,} bytes")
print(f"  Schema version: {trace['schema_version']}")
print(f"  Turns in trace: {len(trace['turns'])}")
print(f"  Stage summary phases: {list(trace['stage_summary'].keys())}")
print(f"  Telemetry: {'present' if trace['telemetry'] else 'missing'}")
print(f"  Checklist passed: {trace['checklist']['passed']}")
print(f"  Artifacts: {len(trace['artifacts_manifest'])} files")

print("\nDone. Full pipeline complete.")
print(f"Session directory: {result.session_path}")
print(f"Trace file: {trace_path}")