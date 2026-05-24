#!/usr/bin/env python3
"""Phase 3 Test: State Schema Migration"""
import sys
import os
from pathlib import Path

# Change to project directory
project_root = Path(__file__).parent.parent
os.chdir(project_root)
sys.path.insert(0, str(project_root))

# Write output to file for debugging
output_file = str(project_root / "phase3_result.txt")

try:
    with open(output_file, "w") as f:
        f.write("Phase 3 Test Starting...\n")
        
        from src.novelty_checker.state import DeepAgentState, Feature, Reference, CoverageStatus
        f.write(f"✅ DeepAgentState fields: {len(DeepAgentState.__annotations__)} fields\n")
        
        from src.novelty_checker.deep_agent import create_deep_agent, load_subagents, BASE_DIR
        f.write(f"✅ Imports successful\n")
        f.write(f"BASE_DIR: {BASE_DIR}\n")
        
        # Test creating agent (returns tuple now)
        agent, session_id = create_deep_agent()
        f.write(f"✅ Agent created: {type(agent).__name__}\n")
        f.write(f"✅ Session ID: {session_id}\n")
        
        f.write("\n✅ Phase 3 Test PASSED!\n")
        
except Exception as e:
    with open(output_file, "a") as f:
        f.write(f"\n❌ ERROR: {e}\n")
        import traceback
        f.write(traceback.format_exc())
