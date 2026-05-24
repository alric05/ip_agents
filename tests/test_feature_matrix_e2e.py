"""End-to-End Tests for Feature Matrix Identifier Migration.

These tests verify that the entire pipeline correctly generates Feature Matrix
tables with Publication Numbers instead of Query IDs.

Run with: pytest test_feature_matrix_e2e.py -v
"""

import pytest
from typing import Literal

# =============================================================================
# Test Data: Simulated Pipeline State
# =============================================================================

SAMPLE_FEATURES = [
    {
        "id": "F1",
        "name": "UV Fluorescence Detection",
        "description": "Using UV fluorescence for polymer detection",
        "keywords": ["UV", "fluorescence", "polymer"],
        "is_core": True,
        "priority": "P1",
    },
    {
        "id": "F2",
        "name": "Microplastic Size Range",
        "description": "Detection of particles 1-100 microns",
        "keywords": ["microplastic", "particle size"],
        "is_core": True,
        "priority": "P1",
    },
    {
        "id": "F3",
        "name": "Real-time Analysis",
        "description": "Continuous real-time monitoring",
        "keywords": ["real-time", "continuous"],
        "is_core": False,
        "priority": "P2",
    },
]

# Correctly formatted references (with publication numbers)
CORRECT_REFERENCES = [
    {
        "ref_id": "US10234567B2",
        "title": "Method for polymer detection using UV fluorescence in water samples",
        "source": "innography",
        "ref_type": "patent",
        "triage_label": "A",
        "priority_date": "2018-03-15",
        "jurisdiction": "US",
        "feature_coverage": {"F1": "Y", "F2": "Y1", "F3": "N"},
        "aspects_covered": "F1 full disclosure, F2 partial",
        "comments": "Claims 1, 5; Fig. 2",
    },
    {
        "ref_id": "JP2007171504A",
        "title": "Particle size analyzer with fluorescence capabilities",
        "source": "ngsp",
        "ref_type": "patent",
        "triage_label": "A",
        "priority_date": "2006-12-20",
        "jurisdiction": "JP",
        "feature_coverage": {"F1": "Y", "F2": "Y", "F3": "N"},
        "aspects_covered": "Core features F1, F2 fully disclosed",
        "comments": "Claims 1-3; Fig. 4",
        "x_category": True,  # All core features are Y
    },
    {
        "ref_id": "WOS:000299510600010",
        "title": "Spectroscopic methods for microplastic detection",
        "source": "wos",
        "ref_type": "npl",
        "triage_label": "B",
        "pub_year": "2012",
        "jurisdiction": "Environ. Sci. Technol.",
        "feature_coverage": {"F1": "Y1", "F2": "N", "F3": "Y"},
        "aspects_covered": "F1 partial, F3 real-time aspect",
        "comments": "Section 3.2, p.45-48",
    },
    {
        "ref_id": "CN106054342A",
        "title": "Microplastic fluorescence detection device",
        "source": "innography",
        "ref_type": "patent",
        "triage_label": "C",  # Should be excluded from Feature Matrix
        "priority_date": "2015-07-10",
        "jurisdiction": "CN",
        "feature_coverage": {"F1": "N", "F2": "N", "F3": "N"},
        "aspects_covered": "Peripheral reference only",
        "comments": "Low relevance",
    },
]

# Incorrectly formatted references (with query IDs - should fail validation)
INCORRECT_REFERENCES = [
    {
        "ref_id": "K1.1",  # ❌ Query ID, not publication number
        "title": "Some patent about detection",
        "source": "innography",
        "triage_label": "A",
        "feature_coverage": {"F1": "Y", "F2": "N", "F3": "N"},
    },
    {
        "ref_id": "NQP-1.2",  # ❌ Query ID
        "title": "Some research paper",
        "source": "wos",
        "triage_label": "B",
        "feature_coverage": {"F1": "N", "F2": "Y", "F3": "N"},
    },
]


# =============================================================================
# Test: Feature Matrix Generator
# =============================================================================

class TestFeatureMatrixGenerator:
    """Tests for the FeatureMatrixGenerator class."""
    
    def test_generator_creates_correct_headers(self):
        """Verify Feature Matrix has correct column headers."""
        from src.novelty_checker.utils.feature_matrix import FeatureMatrixGenerator
        
        generator = FeatureMatrixGenerator(
            features=SAMPLE_FEATURES,
            core_feature_ids=["F1", "F2"],
        )
        
        for ref in CORRECT_REFERENCES:
            generator.add_reference(ref)
        
        markdown = generator.to_markdown()
        
        # Check required columns
        assert "Publication Number" in markdown
        assert "Ref Type" in markdown
        assert "Earliest Priority" in markdown
        assert "F1" in markdown
        assert "F2" in markdown
        assert "F3" in markdown
        assert "X-category" in markdown
    
    def test_generator_includes_only_ab_references(self):
        """Verify only A and B triage labels are included."""
        from src.novelty_checker.utils.feature_matrix import FeatureMatrixGenerator
        
        generator = FeatureMatrixGenerator(
            features=SAMPLE_FEATURES,
            core_feature_ids=["F1", "F2"],
        )
        
        for ref in CORRECT_REFERENCES:
            generator.add_reference(ref)
        
        # Should have 3 rows (2 A-rated, 1 B-rated, 1 C-rated excluded)
        assert len(generator.rows) == 3
        
        markdown = generator.to_markdown()
        
        # Included
        assert "US10234567B2" in markdown
        assert "JP2007171504A" in markdown
        assert "WOS:000299510600010" in markdown
        
        # Excluded (C-rated)
        assert "CN106054342A" not in markdown
    
    def test_generator_rejects_query_ids(self):
        """Verify query IDs are rejected (not added to matrix)."""
        from src.novelty_checker.utils.feature_matrix import FeatureMatrixGenerator
        
        generator = FeatureMatrixGenerator(
            features=SAMPLE_FEATURES,
            core_feature_ids=["F1", "F2"],
        )
        
        for ref in INCORRECT_REFERENCES:
            added = generator.add_reference(ref)
            assert not added, f"Query ID {ref['ref_id']} should have been rejected"
        
        assert len(generator.rows) == 0
    
    def test_generator_identifies_x_category(self):
        """Verify X-category is correctly identified."""
        from src.novelty_checker.utils.feature_matrix import FeatureMatrixGenerator
        
        generator = FeatureMatrixGenerator(
            features=SAMPLE_FEATURES,
            core_feature_ids=["F1", "F2"],
        )
        
        for ref in CORRECT_REFERENCES:
            generator.add_reference(ref)
        
        # JP2007171504A has F1=Y and F2=Y (both core features)
        jp_row = next(r for r in generator.rows if r["publication_number"] == "JP2007171504A")
        assert jp_row["x_category"] == True
        
        # US10234567B2 has F1=Y but F2=Y1 (partial)
        us_row = next(r for r in generator.rows if r["publication_number"] == "US10234567B2")
        assert us_row["x_category"] == False


# =============================================================================
# Test: State-Based Functions
# =============================================================================

class TestStateFunctions:
    """Tests for state-based Feature Matrix functions."""
    
    def test_build_feature_matrix_from_state(self):
        """Verify Feature Matrix can be built from agent state."""
        from src.novelty_checker.utils.feature_matrix import build_feature_matrix_from_state
        
        state = {
            "features": SAMPLE_FEATURES,
            "references": CORRECT_REFERENCES,
        }
        
        markdown = build_feature_matrix_from_state(state)
        
        # Should have publication numbers, not query IDs
        assert "US10234567B2" in markdown
        assert "JP2007171504A" in markdown
        assert "WOS:000299510600010" in markdown
        
        # Should NOT have query IDs
        assert "K1.1" not in markdown
        assert "NQP-" not in markdown
        
        # C-rated should be excluded
        assert "CN106054342A" not in markdown
    
    def test_pre_report_check_passes_with_correct_refs(self):
        """Verify pre-report check passes with correct identifiers."""
        from src.novelty_checker.utils.feature_matrix import pre_report_feature_matrix_check
        
        state = {
            "features": SAMPLE_FEATURES,
            "references": CORRECT_REFERENCES,
        }
        
        is_valid, message = pre_report_feature_matrix_check(state)
        
        assert is_valid == True
        assert "✅" in message
    
    def test_pre_report_check_fails_with_query_ids(self):
        """Verify pre-report check fails when query IDs are present."""
        from src.novelty_checker.utils.feature_matrix import pre_report_feature_matrix_check
        
        state = {
            "features": SAMPLE_FEATURES,
            "references": INCORRECT_REFERENCES,
        }
        
        is_valid, message = pre_report_feature_matrix_check(state)
        
        assert is_valid == False
        assert "query ID" in message.lower() or "K1.1" in message or "NQP-1.2" in message


# =============================================================================
# Test: Validation Functions
# =============================================================================

class TestValidation:
    """Tests for Feature Matrix validation."""
    
    def test_validate_correct_matrix(self):
        """Verify validation passes for correctly formatted matrix."""
        from src.novelty_checker.utils.feature_matrix import validate_feature_matrix_in_report
        
        report = """
# Novelty Report

## 4. Feature Matrix (Core Analytical Deliverable)

| Publication Number | Ref Type | F1 | F2 | F3 |
|---|---|---|---|---|
| US10234567B2 | Patent | Y | Y1 | N |
| JP2007171504A | Patent | Y | Y | N |
| WOS:000299510600010 | Research Paper | Y1 | N | Y |
"""
        
        result = validate_feature_matrix_in_report(report)
        
        assert result.is_valid == True
        assert len(result.query_ids_found) == 0
        assert "US10234567B2" in result.valid_identifiers
        assert "JP2007171504A" in result.valid_identifiers
        assert "WOS:000299510600010" in result.valid_identifiers
    
    def test_validate_incorrect_matrix_with_query_ids(self):
        """Verify validation fails when query IDs are used."""
        from src.novelty_checker.utils.feature_matrix import validate_feature_matrix_in_report
        
        report = """
# Novelty Report

## 4. Feature Matrix (Core Analytical Deliverable)

| Query | F1 | F2 | F3 |
|---|---|---|---|
| K1.1 | Y | Y1 | N |
| NQP-1.2 | Y | Y | N |
| S1.1 | Y1 | N | Y |
"""
        
        result = validate_feature_matrix_in_report(report)
        
        assert result.is_valid == False
        assert len(result.query_ids_found) >= 2
        assert "K1.1" in result.query_ids_found
        assert "NQP-1.2" in result.query_ids_found
    
    def test_extract_feature_matrix_section(self):
        """Verify Feature Matrix section extraction works."""
        from src.novelty_checker.utils.feature_matrix import extract_feature_matrix_from_markdown
        
        report = """
# Novelty Report

## 1. Scope

Some scope content.

## 4. Feature Matrix (Core Analytical Deliverable)

| Publication Number | Ref Type | F1 |
|---|---|---|
| US10234567B2 | Patent | Y |

## 5. Conclusion

Final conclusion.
"""
        
        matrix_section = extract_feature_matrix_from_markdown(report)
        
        assert matrix_section is not None
        assert "Feature Matrix" in matrix_section
        assert "US10234567B2" in matrix_section
        assert "Conclusion" not in matrix_section


# =============================================================================
# Test: Tool Integration (from Phase 2)
# =============================================================================

class TestToolIntegration:
    """Tests for Phase 2 tools integration."""
    
    def test_build_feature_matrix_tool(self):
        """Verify build_feature_matrix tool works correctly."""
        from src.tools import build_feature_matrix
        
        refs = [
            {
                "ref_id": "US10234567B2",
                "ref_type": "patent",
                "title": "UV Fluorescence Detection Method",
                "triage_label": "A",
                "priority_date": "2018-03-15",
                "jurisdiction": "US",
                "feature_coverage": {"F1": "Y", "F2": "Y1"},
                "aspects_covered": "F1 full",
                "comments": "Claims 1, 5",
            }
        ]
        
        result = build_feature_matrix.invoke({
            "references": refs,
            "feature_ids": ["F1", "F2"],
            "core_feature_ids": ["F1"],
        })
        
        assert "US10234567B2" in result
        assert "Patent" in result
        assert "K1.1" not in result  # No query IDs
    
    def test_validate_feature_matrix_format_tool(self):
        """Verify validate_feature_matrix_format tool works."""
        from src.tools import validate_feature_matrix_format
        
        good_matrix = """
| Publication Number | Ref Type | F1 |
|---|---|---|
| US10234567B2 | Patent | Y |
"""
        
        result = validate_feature_matrix_format.invoke({
            "feature_matrix_markdown": good_matrix
        })
        
        assert "PASSED" in result


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
