#!/usr/bin/env python3
"""Quick test for Phase 1 changes."""

import sys
sys.path.insert(0, '.')

# Import directly to test
exec(compile(open('vs_code_agent/novelty_agent/shared_state.py').read(), 'shared_state.py', 'exec'))

print("Testing Phase 1 Feature Matrix Migration...")

# Test 1: ReferenceEntry display methods
ref = ReferenceEntry(
    ref_id="US10234567B2",
    ref_type="patent",
    title="Test Patent",
    priority_date="2018-03-15",
    jurisdiction="US",
)
assert ref.get_display_id() == "US10234567B2"
assert ref.get_ref_type_display() == "Patent"
assert ref.get_date_display() == "2018-03-15"
print("✅ Test 1 PASSED: ReferenceEntry display methods")

# Test 2: Feature coverage
ref2 = ReferenceEntry(
    ref_id="WOS:000299510600010",
    ref_type="npl",
    title="Test Paper",
    pub_year="2012",
    feature_coverage={"F1": "Y", "F2": "N"},
)
assert ref2.get_ref_type_display() == "Research Paper"
assert ref2.feature_coverage["F1"] == "Y"
print("✅ Test 2 PASSED: Feature coverage fields")

# Test 3: FeatureMatrixBuilder
builder = FeatureMatrixBuilder(feature_ids=["F1", "F2"])
ref_a = ReferenceEntry(
    ref_id="US12345678B2",
    ref_type="patent",
    title="Patent A",
    triage_label="A",
    feature_coverage={"F1": "Y", "F2": "N"},
)
builder.add_reference(ref_a)
assert len(builder.rows) == 1
print("✅ Test 3 PASSED: FeatureMatrixBuilder")

# Test 4: Validate identifiers
bad_matrix = """
| Publication Number | Ref Type |
|---|---|
| K1.1 | Patent |
"""
is_valid, errors = validate_feature_matrix_identifiers(bad_matrix)
assert not is_valid
assert len(errors) == 1
print("✅ Test 4 PASSED: Validation detects query IDs")

print("\n🎉 All Phase 1 tests PASSED!")
