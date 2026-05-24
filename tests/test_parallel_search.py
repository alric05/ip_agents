"""Tests for the parallel search feature.

This module contains:
1. Unit tests for aggregate_search_results tool
2. Integration tests for subagent loading
3. End-to-end test structure for sample invention
"""

import pytest
from pathlib import Path


# =============================================================================
# Unit Tests: aggregate_search_results
# =============================================================================

class TestAggregateSearchResults:
    """Unit tests for the aggregate_search_results tool."""
    
    def test_empty_input(self):
        """Test with no path results."""
        from src.tools.aggregation import aggregate_search_results
        
        result = aggregate_search_results.invoke({"path_results": []})
        assert "No path results provided" in result
    
    def test_single_path_results(self):
        """Test with results from a single path."""
        from src.tools.aggregation import aggregate_search_results
        
        path_results = [
            {
                "path_id": "keyword_precision",
                "references_found": [
                    {"ref_id": "US1234567", "title": "Test Patent 1", "source": "Innography"},
                    {"ref_id": "US7654321", "title": "Test Patent 2", "source": "Innography"},
                ]
            }
        ]
        
        result = aggregate_search_results.invoke({"path_results": path_results})
        
        assert "Aggregation Complete" in result
        assert "Paths executed | 1" in result
        assert "Total refs before dedup | 2" in result
        assert "Total refs after dedup | 2" in result
        assert "US1234567" in result
        assert "US7654321" in result
    
    def test_multi_path_deduplication(self):
        """Test deduplication across multiple paths."""
        from src.tools.aggregation import aggregate_search_results
        
        path_results = [
            {
                "path_id": "keyword_precision",
                "references_found": [
                    {"ref_id": "US1234567", "title": "Shared Patent", "source": "Innography"},
                    {"ref_id": "US1111111", "title": "Unique to Path 1", "source": "Innography"},
                ]
            },
            {
                "path_id": "semantic_recall",
                "references_found": [
                    {"ref_id": "US1234567", "title": "Shared Patent", "source": "NGSP"},
                    {"ref_id": "US2222222", "title": "Unique to Path 2", "source": "NGSP"},
                ]
            },
        ]
        
        result = aggregate_search_results.invoke({"path_results": path_results})
        
        assert "Paths executed | 2" in result
        assert "Total refs before dedup | 4" in result
        assert "Total refs after dedup | 3" in result
        assert "Multi-path discoveries | 1" in result
    
    def test_diversity_scoring(self):
        """Test that diversity scores are calculated correctly."""
        from src.tools.aggregation import aggregate_search_results
        
        path_results = [
            {
                "path_id": "keyword_precision",
                "references_found": [
                    {"ref_id": "US1234567", "title": "Found by all 3", "source": "Innography"},
                ]
            },
            {
                "path_id": "semantic_recall",
                "references_found": [
                    {"ref_id": "US1234567", "title": "Found by all 3", "source": "NGSP"},
                ]
            },
            {
                "path_id": "structural_combination",
                "references_found": [
                    {"ref_id": "US1234567", "title": "Found by all 3", "source": "Innography"},
                ]
            },
        ]
        
        result = aggregate_search_results.invoke({"path_results": path_results})
        
        # Score should be: 1.0 (base) + 1.0 (2 extra paths) + 0.2 (semantic) + 0.3 (combo) = 2.5
        assert "2.5" in result
    
    def test_ref_id_normalization(self):
        """Test that ref IDs are normalized (uppercase, no spaces/dashes)."""
        from src.tools.aggregation import aggregate_search_results
        
        path_results = [
            {
                "path_id": "keyword_precision",
                "references_found": [
                    {"ref_id": "US 1234567", "title": "With space", "source": "A"},
                ]
            },
            {
                "path_id": "semantic_recall",
                "references_found": [
                    {"ref_id": "us-1234567", "title": "With dash lowercase", "source": "B"},
                ]
            },
        ]
        
        result = aggregate_search_results.invoke({"path_results": path_results})
        
        # Should be deduplicated to 1 reference
        assert "Total refs after dedup | 1" in result
        assert "Multi-path discoveries | 1" in result


# =============================================================================
# Integration Tests: SubAgent Loading
# =============================================================================

class TestSubAgentLoading:
    """Integration tests for subagent configuration loading."""
    
    def test_subagents_yaml_exists(self):
        """Test that subagents.yaml exists."""
        yaml_path = Path(__file__).parent.parent / "src" / "novelty_checker" / "subagents.yaml"
        assert yaml_path.exists(), f"subagents.yaml not found at {yaml_path}"
    
    def test_subagents_yaml_valid(self):
        """Test that subagents.yaml is valid YAML."""
        import yaml
        
        yaml_path = Path(__file__).parent.parent / "src" / "novelty_checker" / "subagents.yaml"
        with open(yaml_path) as f:
            data = yaml.safe_load(f)
        
        assert isinstance(data, dict), "subagents.yaml should parse to a dict"
    
    def test_path_subagents_defined(self):
        """Test that all 3 path subagents are defined."""
        import yaml
        
        yaml_path = Path(__file__).parent.parent / "src" / "novelty_checker" / "subagents.yaml"
        with open(yaml_path) as f:
            data = yaml.safe_load(f)
        
        required_subagents = [
            "keyword-precision-searcher",
            "semantic-recall-searcher", 
            "structural-combo-searcher",
        ]
        
        for subagent in required_subagents:
            assert subagent in data, f"Missing subagent: {subagent}"
            assert "description" in data[subagent], f"{subagent} missing description"
            assert "system_prompt" in data[subagent], f"{subagent} missing system_prompt"
            assert "tools" in data[subagent], f"{subagent} missing tools"
    
    def test_path_subagent_tools(self):
        """Test that path subagents have correct tools assigned."""
        import yaml
        
        yaml_path = Path(__file__).parent.parent / "src" / "novelty_checker" / "subagents.yaml"
        with open(yaml_path) as f:
            data = yaml.safe_load(f)
        
        # keyword-precision should NOT have semantic_patent_search
        kw_tools = data["keyword-precision-searcher"]["tools"]
        assert "patent_keyword_search" in kw_tools
        assert "semantic_patent_search" not in kw_tools
        
        # semantic-recall should have semantic_patent_search
        sem_tools = data["semantic-recall-searcher"]["tools"]
        assert "semantic_patent_search" in sem_tools
        
        # structural-combo should have both
        combo_tools = data["structural-combo-searcher"]["tools"]
        assert "patent_keyword_search" in combo_tools
        assert "semantic_patent_search" in combo_tools


# =============================================================================
# Integration Tests: Tool Registry
# =============================================================================

class TestToolRegistry:
    """Integration tests for tool registry updates."""
    
    def test_aggregate_search_results_in_registry(self):
        """Test that aggregate_search_results is in ANALYSIS_TOOLS."""
        from src.tools.registry import ANALYSIS_TOOLS
        
        tool_names = [t.name for t in ANALYSIS_TOOLS]
        assert "aggregate_search_results" in tool_names
    
    def test_aggregate_search_results_in_all_tools(self):
        """Test that aggregate_search_results is returned by get_all_tools."""
        from src.tools.registry import get_all_tools
        
        all_tools = get_all_tools()
        tool_names = [t.name for t in all_tools]
        assert "aggregate_search_results" in tool_names
    
    def test_aggregate_search_results_exported(self):
        """Test that aggregate_search_results is exported from __init__."""
        from src.tools import aggregate_search_results
        
        assert aggregate_search_results is not None
        assert hasattr(aggregate_search_results, "invoke")


# =============================================================================
# Integration Tests: Skill Loading
# =============================================================================

class TestSkillLoading:
    """Integration tests for parallel-search skill."""
    
    def test_skill_file_exists(self):
        """Test that parallel-search SKILL.md exists."""
        skill_path = Path(__file__).parent.parent / "src" / "novelty_checker" / "skills" / "parallel-search" / "SKILL.md"
        assert skill_path.exists(), f"SKILL.md not found at {skill_path}"
    
    def test_skill_has_frontmatter(self):
        """Test that skill has proper YAML frontmatter."""
        skill_path = Path(__file__).parent.parent / "src" / "novelty_checker" / "skills" / "parallel-search" / "SKILL.md"
        content = skill_path.read_text()
        
        assert content.startswith("---"), "SKILL.md should start with YAML frontmatter"
        assert "name: parallel-search" in content
        assert "triggers:" in content


# =============================================================================
# E2E Test Structure (requires mocking)
# =============================================================================

class TestE2EStructure:
    """End-to-end test structure - requires API mocking for full execution."""
    
    def test_sample_invention_context(self):
        """Test that we can prepare a sample invention context."""
        sample_features = """
        Features:
        - F1: PA6 Granule Degradation Detection - Detect thermo-oxidative degradation in PA6 granules via UV-induced fluorescence
        - F2: UV Excitation Band (300-350nm) - UV light source in 300-350nm range to excite fluorescence
        - F3: Fluorescence Emission Detection - Measure fluorescence emission in 350-400nm band
        """
        
        # Context should be non-empty and contain all features
        assert "F1" in sample_features
        assert "F2" in sample_features
        assert "F3" in sample_features
        assert "PA6" in sample_features
    
    def test_path_results_structure(self):
        """Test the expected structure of path results."""
        sample_path_result = {
            "path_id": "keyword_precision",
            "queries_executed": [
                "@(dwpi_title,dwpi_novelty) (PA6 NEAR/5 degradation)",
                "@(dwpi_title,dwpi_novelty) (fluorescence NEAR/5 detection)",
            ],
            "references_found": [
                {
                    "ref_id": "US10123456",
                    "title": "Method for detecting polymer degradation",
                    "source": "Innography",
                    "abstract": "A method for detecting degradation in polymers...",
                },
            ],
            "count": 1,
        }
        
        # Validate structure
        assert "path_id" in sample_path_result
        assert "references_found" in sample_path_result
        assert isinstance(sample_path_result["references_found"], list)


# =============================================================================
# Run tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
