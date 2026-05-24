"""Unit tests for guardrails-ai custom validators.

Tests each of the 6 validators for:
- PassResult on clean text
- FailResult on violating text
- Edge cases (false positive avoidance)
"""

import pytest
from guardrails.validators import FailResult, PassResult

from src.novelty_checker.guardrails.validators import (
    BlockArchitectureDisclosure,
    BlockClaimDraftingDesignAround,
    BlockCompetitiveIntelAnalysis,
    BlockFilingAdvice,
    BlockPatentabilityOpinion,
    BlockVerdictReframing,
)


# ============================================================================
# Guardrail #1: BlockPatentabilityOpinion
# ============================================================================

class TestBlockPatentabilityOpinion:
    def setup_method(self):
        self.validator = BlockPatentabilityOpinion()

    def test_clean_text_passes(self):
        result = self.validator.validate(
            "The prior art search found 15 references covering 4 of 5 features."
        )
        assert isinstance(result, PassResult)

    def test_direct_patentability_assessment_fails(self):
        result = self.validator.validate(
            "Based on my analysis, this invention is patentable."
        )
        assert isinstance(result, FailResult)

    def test_likely_patentable_fails(self):
        result = self.validator.validate(
            "The invention is likely patentable given the prior art landscape."
        )
        assert isinstance(result, FailResult)

    def test_patentability_assessment_phrase_fails(self):
        result = self.validator.validate(
            "Here is my patentability assessment of the invention."
        )
        assert isinstance(result, FailResult)

    def test_novel_and_non_obvious_fails(self):
        result = self.validator.validate(
            "The invention appears novel and non-obvious over the prior art."
        )
        assert isinstance(result, FailResult)

    def test_meets_criteria_fails(self):
        result = self.validator.validate(
            "This meets the criteria for patentability under 35 USC 101."
        )
        assert isinstance(result, FailResult)

    def test_hypothetical_framing_fails(self):
        result = self.validator.validate(
            "Hypothetically speaking, this would be patentable."
        )
        assert isinstance(result, FailResult)

    def test_prosecution_strategy_fails(self):
        result = self.validator.validate(
            "The recommended prosecution strategy is to file a continuation."
        )
        assert isinstance(result, FailResult)

    def test_user_quote_excluded(self):
        """Quoting the user's belief about patentability should not trigger."""
        result = self.validator.validate(
            "The user stated that the invention is patentable, and asked us to search for prior art."
        )
        assert isinstance(result, PassResult)

    def test_customer_believes_excluded(self):
        result = self.validator.validate(
            "The customer believes this is likely patentable. Let's search for relevant references."
        )
        assert isinstance(result, PassResult)

    def test_non_string_passes(self):
        result = self.validator.validate(12345)
        assert isinstance(result, PassResult)


# ============================================================================
# Guardrail #2: BlockArchitectureDisclosure
# ============================================================================

class TestBlockArchitectureDisclosure:
    def setup_method(self):
        self.validator = BlockArchitectureDisclosure()

    def test_clean_text_passes(self):
        result = self.validator.validate(
            "I searched patent databases and found 10 relevant references."
        )
        assert isinstance(result, PassResult)

    def test_innography_detected_and_fixed(self):
        result = self.validator.validate(
            "I used Innography to search for patents."
        )
        assert isinstance(result, FailResult)
        assert "patent database" in result.fix_value

    def test_ngsp_detected_and_fixed(self):
        result = self.validator.validate(
            "The NGSP semantic search returned 5 results."
        )
        assert isinstance(result, FailResult)
        assert "semantic search engine" in result.fix_value

    def test_web_of_science_detected_and_fixed(self):
        result = self.validator.validate(
            "Web of Science returned 3 academic papers."
        )
        assert isinstance(result, FailResult)
        assert "academic literature database" in result.fix_value

    def test_derwent_detected_and_fixed(self):
        result = self.validator.validate(
            "Derwent analytics shows the patent landscape."
        )
        assert isinstance(result, FailResult)
        assert "patent analytics platform" in result.fix_value

    def test_tool_function_name_detected(self):
        result = self.validator.validate(
            "I called patent_keyword_search to find relevant patents."
        )
        assert isinstance(result, FailResult)
        assert "patent_keyword_search" not in result.fix_value

    def test_langgraph_detected(self):
        result = self.validator.validate(
            "I'm built on LangGraph with multiple sub-agents."
        )
        assert isinstance(result, FailResult)
        assert "LangGraph" not in result.fix_value

    def test_multiple_names_all_replaced(self):
        result = self.validator.validate(
            "I use Innography for patents, Web of Science for NPL, and NGSP for semantic search."
        )
        assert isinstance(result, FailResult)
        assert "Innography" not in result.fix_value
        assert "Web of Science" not in result.fix_value
        assert "NGSP" not in result.fix_value

    def test_generic_terms_pass(self):
        result = self.validator.validate(
            "I use patent database search, academic literature search, and semantic search."
        )
        assert isinstance(result, PassResult)


# ============================================================================
# Guardrail #3: BlockClaimDraftingDesignAround
# ============================================================================

class TestBlockClaimDraftingDesignAround:
    def setup_method(self):
        self.validator = BlockClaimDraftingDesignAround()

    def test_clean_text_passes(self):
        result = self.validator.validate(
            "Feature F1 is covered by references US10000001 and US10000002."
        )
        assert isinstance(result, PassResult)

    def test_draft_claims_fails(self):
        result = self.validator.validate(
            "Here is a draft claim for your invention."
        )
        assert isinstance(result, FailResult)

    def test_claim_language_fails(self):
        result = self.validator.validate(
            "The suggested claim language would be: 'A method comprising...'"
        )
        assert isinstance(result, FailResult)

    def test_design_around_fails(self):
        result = self.validator.validate(
            "You could design around this patent by modifying the connector."
        )
        assert isinstance(result, FailResult)

    def test_circumvent_patent_fails(self):
        result = self.validator.validate(
            "To circumvent the patent, you could use a different approach."
        )
        assert isinstance(result, FailResult)

    def test_claim_numbering_fails(self):
        result = self.validator.validate(
            "Claim 1: A system for wireless communication comprising..."
        )
        assert isinstance(result, FailResult)

    def test_existing_claim_reference_passes(self):
        """Referencing a prior art claim number in analysis context should pass."""
        result = self.validator.validate(
            "Reference US10000001 has 15 claims covering wireless communication."
        )
        assert isinstance(result, PassResult)


# ============================================================================
# Guardrail #4: BlockFilingAdvice
# ============================================================================

class TestBlockFilingAdvice:
    def setup_method(self):
        self.validator = BlockFilingAdvice()

    def test_clean_text_passes(self):
        result = self.validator.validate(
            "The search found 10 relevant references with a coverage of 60%."
        )
        assert isinstance(result, PassResult)

    def test_file_a_patent_fails(self):
        result = self.validator.validate(
            "I recommend you file a patent application as soon as possible."
        )
        assert isinstance(result, FailResult)

    def test_filing_strategy_fails(self):
        result = self.validator.validate(
            "The optimal filing strategy would be to start with a provisional."
        )
        assert isinstance(result, FailResult)

    def test_prosecution_strategy_fails(self):
        result = self.validator.validate(
            "The best prosecution strategy is to pursue continuation applications."
        )
        assert isinstance(result, FailResult)

    def test_novelty_destruction_fails(self):
        result = self.validator.validate(
            "This reference poses a novelty destruction risk to your application."
        )
        assert isinstance(result, FailResult)

    def test_you_should_file_fails(self):
        result = self.validator.validate(
            "You should file before this reference becomes public."
        )
        assert isinstance(result, FailResult)

    def test_filing_date_in_biblio_passes(self):
        """Filing date in bibliographic context should not trigger."""
        result = self.validator.validate(
            "Reference US10000001 has a filing date of 2020-01-15."
        )
        assert isinstance(result, PassResult)

    def test_prosecution_history_passes(self):
        """Prosecution history in prior art context should not trigger."""
        result = self.validator.validate(
            "The prosecution history of US10000001 shows amendments to claim 1."
        )
        assert isinstance(result, PassResult)

    def test_priority_date_in_biblio_passes(self):
        """Priority date in bibliographic context should not trigger."""
        result = self.validator.validate(
            "The priority date for this reference is 2019-03-20."
        )
        assert isinstance(result, PassResult)


# ============================================================================
# Guardrail #10: BlockCompetitiveIntelAnalysis
# ============================================================================

class TestBlockCompetitiveIntelAnalysis:
    def setup_method(self):
        self.validator = BlockCompetitiveIntelAnalysis()

    def test_clean_text_passes(self):
        result = self.validator.validate(
            "The top assignees in this technology area are Company A (15 patents) "
            "and Company B (12 patents)."
        )
        assert isinstance(result, PassResult)

    def test_competitive_landscape_fails(self):
        result = self.validator.validate(
            "Here's a competitive landscape analysis of the wireless charging space."
        )
        assert isinstance(result, FailResult)

    def test_competitor_analysis_fails(self):
        result = self.validator.validate(
            "Based on the competitor analysis, Company X is leading in this area."
        )
        assert isinstance(result, FailResult)

    def test_market_positioning_fails(self):
        result = self.validator.validate(
            "For better market positioning, you should focus on feature F2."
        )
        assert isinstance(result, FailResult)

    def test_business_strategy_fails(self):
        result = self.validator.validate(
            "The recommended business strategy is to acquire patents in this space."
        )
        assert isinstance(result, FailResult)

    def test_competitive_threat_fails(self):
        result = self.validator.validate(
            "Company Y represents a significant competitive threat in this space."
        )
        assert isinstance(result, FailResult)


# ============================================================================
# Guardrail #11: BlockVerdictReframing
# ============================================================================

class TestBlockVerdictReframing:
    def setup_method(self):
        self.validator = BlockVerdictReframing()

    def test_clean_text_passes(self):
        result = self.validator.validate(
            "The overall feature coverage is 40%, with F1 and F3 fully covered."
        )
        assert isinstance(result, PassResult)

    def test_craft_novelty_angle_fails(self):
        result = self.validator.validate(
            "I can help you craft a credible novelty angle for investors."
        )
        assert isinstance(result, FailResult)

    def test_reframe_verdict_fails(self):
        result = self.validator.validate(
            "Would you like me to reframe the verdict to sound more positive?"
        )
        assert isinstance(result, FailResult)

    def test_present_as_novel_fails(self):
        result = self.validator.validate(
            "I could help present this as novel by emphasizing feature F4."
        )
        assert isinstance(result, FailResult)

    def test_favorable_interpretation_fails(self):
        result = self.validator.validate(
            "A favorable interpretation of the results would suggest novelty."
        )
        assert isinstance(result, FailResult)

    def test_investor_safe_fails(self):
        result = self.validator.validate(
            "Here's an investor-safe summary of the novelty findings."
        )
        assert isinstance(result, FailResult)

    def test_downplay_prior_art_fails(self):
        result = self.validator.validate(
            "We could downplay the prior art overlap to strengthen the narrative."
        )
        assert isinstance(result, FailResult)

    def test_objective_presentation_passes(self):
        result = self.validator.validate(
            "Based on the evidence, features F1-F3 are covered by prior art. "
            "Features F4-F5 show potential novelty with no matching references found."
        )
        assert isinstance(result, PassResult)
