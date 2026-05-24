"""Test Phase 0 checkpointer integration."""

from pathlib import Path
from src.novelty_checker.deep_agent import create_deep_agent, SESSIONS_DIR

def test_checkpointer_created():
    """Verify that checkpointer is created by default."""
    graph, session_id = create_deep_agent()

    session_path = SESSIONS_DIR / session_id

    # Verify session directory exists
    assert session_path.exists(), f"Session directory should exist at {session_path}"

    # Verify findings directory was created
    findings_path = session_path / "findings"
    assert findings_path.exists(), "Findings directory should exist"

    # Verify graph has checkpointer
    assert graph.checkpointer is not None, "Graph should have a checkpointer"

    print(f"✅ Session created at: {session_path}")
    print(f"✅ Checkpointer type: {type(graph.checkpointer).__name__}")
    print(f"✅ Findings directory exists: {findings_path.exists()}")

    return True

if __name__ == "__main__":
    test_checkpointer_created()
    print("\n🎉 Checkpointer test passed!")
