"""Tests for state reducer functions (Phase 0)."""

from src.novelty_checker.state import (
    merge_references,
    merge_findings_accumulator,
    merge_coverage,
)


def test_merge_references_deduplicates():
    """Test that merge_references deduplicates by ref_id."""
    ref1 = {"ref_id": "US-12345", "title": "Test Patent", "discovery_method": "keyword"}
    ref2 = {"ref_id": "US-12345", "title": "Test Patent", "discovery_method": "semantic"}
    ref3 = {"ref_id": "US-67890", "title": "Other Patent", "discovery_method": "keyword"}

    merged = merge_references([ref1], [ref2, ref3])

    assert len(merged) == 2, "Should have 2 unique references"

    # Find the merged ref
    merged_ref = next(r for r in merged if r["ref_id"] == "US-12345")

    # Should combine discovery methods
    assert "keyword" in merged_ref["discovery_method"]
    assert "semantic" in merged_ref["discovery_method"]


def test_merge_references_empty_lists():
    """Test merge_references with empty lists."""
    ref1 = {"ref_id": "US-12345", "title": "Test"}

    assert merge_references([], [ref1]) == [ref1]
    assert merge_references([ref1], []) == [ref1]
    assert merge_references([], []) == []


def test_merge_findings_accumulator():
    """Test that merge_findings_accumulator appends rounds and deduplicates references."""
    acc1 = {
        "rounds": [{"round_number": 1, "new_refs_count": 5}],
        "all_references": [{"ref_id": "US-1", "title": "First"}],
        "current_round": 1,
    }
    acc2 = {
        "rounds": [{"round_number": 2, "new_refs_count": 3}],
        "all_references": [{"ref_id": "US-2", "title": "Second"}],
        "current_round": 2,
    }

    merged = merge_findings_accumulator(acc1, acc2)

    assert len(merged["rounds"]) == 2, "Should have 2 rounds"
    assert len(merged["all_references"]) == 2, "Should have 2 unique references"
    assert merged["current_round"] == 2, "Should take max round number"


def test_merge_findings_accumulator_with_duplicate_refs():
    """Test that merge_findings_accumulator deduplicates references."""
    acc1 = {
        "rounds": [{"round_number": 1}],
        "all_references": [
            {"ref_id": "US-12345", "title": "Test", "discovery_method": "keyword"}
        ],
    }
    acc2 = {
        "rounds": [{"round_number": 2}],
        "all_references": [
            {"ref_id": "US-12345", "title": "Test", "discovery_method": "semantic"},
            {"ref_id": "US-67890", "title": "Other", "discovery_method": "npl"},
        ],
    }

    merged = merge_findings_accumulator(acc1, acc2)

    assert len(merged["all_references"]) == 2, "Should deduplicate US-12345"

    # Check that discovery methods were merged
    ref_12345 = next(r for r in merged["all_references"] if r["ref_id"] == "US-12345")
    assert "keyword" in ref_12345["discovery_method"]
    assert "semantic" in ref_12345["discovery_method"]


def test_merge_findings_accumulator_with_none():
    """Test merge_findings_accumulator handles None values."""
    acc = {"rounds": [{"round_number": 1}]}

    assert merge_findings_accumulator(None, acc) == acc
    assert merge_findings_accumulator(acc, None) == acc
    assert merge_findings_accumulator(None, None) == {}


def test_merge_coverage():
    """Test that merge_coverage takes latest status per feature."""
    cov1 = [
        {"feature_id": "F1", "level": "weak", "a_refs": 0, "b_refs": 1},
        {"feature_id": "F2", "level": "none", "a_refs": 0, "b_refs": 0},
    ]
    cov2 = [
        {"feature_id": "F1", "level": "strong", "a_refs": 2, "b_refs": 3},
        {"feature_id": "F3", "level": "moderate", "a_refs": 1, "b_refs": 1},
    ]

    merged = merge_coverage(cov1, cov2)

    assert len(merged) == 3, "Should have 3 features (F1, F2, F3)"

    # F1 should have the latest (updated) status
    f1 = next(c for c in merged if c["feature_id"] == "F1")
    assert f1["level"] == "strong", "F1 should be updated to strong"
    assert f1["a_refs"] == 2

    # F2 should remain from first list
    f2 = next(c for c in merged if c["feature_id"] == "F2")
    assert f2["level"] == "none"

    # F3 should be added from second list
    f3 = next(c for c in merged if c["feature_id"] == "F3")
    assert f3["level"] == "moderate"


def test_merge_coverage_empty_lists():
    """Test merge_coverage with empty lists."""
    cov = [{"feature_id": "F1", "level": "weak"}]

    assert merge_coverage([], cov) == cov
    assert merge_coverage(cov, []) == cov
    assert merge_coverage([], []) == []


if __name__ == "__main__":
    # Run tests
    test_merge_references_deduplicates()
    test_merge_references_empty_lists()
    test_merge_findings_accumulator()
    test_merge_findings_accumulator_with_duplicate_refs()
    test_merge_findings_accumulator_with_none()
    test_merge_coverage()
    test_merge_coverage_empty_lists()

    print("✅ All state reducer tests passed!")
