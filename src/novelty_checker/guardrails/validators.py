"""Custom guardrails-ai validators for the novelty checker agent.

Six validators covering critical and high-risk guardrails identified
in the agentic risk assessment (48-scenario behaviour testing).

Each validator uses regex/keyword detection (no LLM calls) for <5ms
validation latency.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, Optional

from guardrails.validators import (
    FailResult,
    PassResult,
    ValidationResult,
    Validator,
    register_validator,
)


# ============================================================================
# Guardrail #1: Block Patentability Opinions
# ============================================================================

# Patterns that indicate the AGENT is making a patentability assessment.
# Excludes quoted user claims (preceded by "user stated", "customer believes", etc.)
_PATENTABILITY_PATTERNS = [
    # Direct assessments
    r"\bis\s+(?:likely\s+)?patentable\b",
    r"\bis\s+not\s+patentable\b",
    r"\bunpatentable\b",
    r"\bpatentability\s+(?:assessment|analysis|evaluation|opinion|determination)\b",
    r"\bmeets?\s+(?:the\s+)?(?:criteria|requirements|threshold)\s+(?:for\s+)?patentability\b",
    r"\bnovel\s+and\s+non[- ]obvious\b",
    r"\bwould\s+(?:likely\s+)?be\s+patentable\b",
    r"\bshould\s+be\s+(?:considered\s+)?patentable\b",
    r"\bstrong\s+(?:case|argument)\s+for\s+patentability\b",
    r"\bweak\s+(?:case|argument)\s+for\s+patentability\b",
    # Hypothetical / jailbreak variants
    r"\bhypothetically\s+(?:speaking[,]?\s+)?(?:this\s+)?(?:is|would\s+be)\s+patentable\b",
    r"\bin\s+(?:my|this)\s+(?:opinion|assessment|view)\s*[,]?\s*(?:the\s+)?(?:invention\s+)?(?:is|appears?)\s+patentable\b",
    # Prosecution strategy (closely tied to patentability)
    r"\bprosecution\s+strategy\b",
    r"\boffice\s+action\s+response\b",
    r"\bclaim\s+(?:scope|breadth)\s+(?:is|appears?|seems?)\s+(?:sufficient|adequate|narrow|broad)\b",
    # "case for patentability" / "strongest case"
    r"\b(?:strong(?:est)?|weak(?:est)?)\s+case\s+for\s+patentability\b",
    r"\bcase\s+for\s+patentability\b",
    r"\bpatent[- ]eligible\s+subject\s+matter\b",
]

# Context that indicates the agent is quoting the user, not opining
_PATENTABILITY_EXCLUSION_PREFIXES = [
    r"(?:the\s+)?(?:user|customer|inventor|applicant)\s+(?:stated|believes?|claims?|mentioned|said|indicated)",
    r"you\s+(?:mentioned|stated|believe|indicated)",
    r"according\s+to\s+(?:the\s+)?(?:user|customer|inventor)",
]

_patentability_compiled = [re.compile(p, re.IGNORECASE) for p in _PATENTABILITY_PATTERNS]
_patentability_exclusions = [re.compile(p, re.IGNORECASE) for p in _PATENTABILITY_EXCLUSION_PREFIXES]


@register_validator(name="block-patentability-opinion", data_type="string")
class BlockPatentabilityOpinion(Validator):
    """Blocks patentability opinions under any framing."""

    def validate(self, value: Any, metadata: Optional[Dict] = None) -> ValidationResult:
        if not isinstance(value, str):
            return PassResult()

        for pattern in _patentability_compiled:
            match = pattern.search(value)
            if match:
                # Check if this match is preceded by an exclusion phrase (user quote)
                start = max(0, match.start() - 120)
                preceding = value[start:match.start()]
                if any(exc.search(preceding) for exc in _patentability_exclusions):
                    continue
                return FailResult(
                    error_message=(
                        f"Response contains a patentability opinion "
                        f"(matched: '{match.group()}'). Patentability "
                        f"assessments are outside the agent's scope."
                    ),
                )

        return PassResult()


# ============================================================================
# Guardrail #2: Block Architecture / System Prompt Disclosure
# ============================================================================

# Protected names -> generic replacements
_PROTECTED_NAME_REPLACEMENTS: dict[str, str] = {
    # Database / API vendor names
    r"\bInnography\b": "patent database",
    r"\bNGSP\b": "semantic search engine",
    r"\bDerwent\b": "patent analytics platform",
    r"\bWeb\s+of\s+Science\b": "academic literature database",
    r"\bWoS\b": "academic literature database",
    r"\binnography\.com\b": "patent database",
    # Tool function names
    r"\bpatent_keyword_search\b": "patent search",
    r"\bnpl_search\b": "academic literature search",
    r"\bsemantic_patent_search\b": "semantic search",
    r"\bbatch_patent_search\b": "batch patent search",
    r"\bbatch_npl_search\b": "batch literature search",
    r"\bbatch_semantic_search\b": "batch semantic search",
    r"\bbatch_unified_search\b": "unified search",
    r"\bbatch_citation_search\b": "citation search",
    r"\bcitation_chain_search\b": "citation network analysis",
    r"\bget_patent_citations\b": "citation retrieval",
    r"\bget_patent_details\b": "patent detail retrieval",
    r"\btriage_reference\b": "reference assessment",
    r"\bmap_features_to_reference\b": "feature mapping",
    r"\bevaluate_coverage\b": "coverage evaluation",
    r"\bgenerate_search_strategy\b": "search strategy generation",
    r"\bbuild_feature_matrix\b": "feature matrix construction",
    r"\bsave_round_findings\b": "findings persistence",
    r"\bget_all_findings\b": "findings retrieval",
    r"\bget_coverage_gaps\b": "coverage gap analysis",
    r"\bthink_tool\b": "internal reflection",
    # Architecture terms
    r"\bdeepagents?\b": "agent framework",
    r"\bSubAgentMiddleware\b": "internal component",
    r"\bFilesystemBackend\b": "storage system",
    r"\bLangGraph\b": "agent framework",
    r"\blanggraph\b": "agent framework",
    r"\bsub[- ]?agents?\b": "specialized search capabilities",
    r"\borchestrator\b": "coordination system",
}

_protected_compiled = [
    (re.compile(pattern, re.IGNORECASE), replacement)
    for pattern, replacement in _PROTECTED_NAME_REPLACEMENTS.items()
]

# Detection-only patterns (if ANY match, the validator triggers a fix)
_ARCHITECTURE_DETECTION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bInnography\b",
        r"\bNGSP\b",
        r"\bDerwent\b",
        r"\bWeb\s+of\s+Science\b",
        r"\bWoS\b",
        r"\bpatent_keyword_search\b",
        r"\bnpl_search\b",
        r"\bsemantic_patent_search\b",
        r"\bbatch_\w+_search\b",
        r"\bcitation_chain_search\b",
        r"\bget_patent_(?:citations|details)\b",
        r"\bdeepagents?\b",
        r"\bSubAgentMiddleware\b",
        r"\bFilesystemBackend\b",
        r"\bLangGraph\b",
        r"\blanggraph\b",
        r"\btriage_reference\b",
        r"\bmap_features_to_reference\b",
        r"\bevaluate_coverage\b",
        r"\bgenerate_search_strategy\b",
        r"\bbuild_feature_matrix\b",
        r"\bsave_round_findings\b",
        r"\bget_all_findings\b",
        r"\bget_coverage_gaps\b",
        r"\bthink_tool\b",
    ]
]


@register_validator(name="block-architecture-disclosure", data_type="string")
class BlockArchitectureDisclosure(Validator):
    """Detects and redacts internal tool/architecture names from output.

    Uses on_fail='fix' — returns sanitized text with protected names
    replaced by generic terms, preserving the rest of the response.
    """

    def validate(self, value: Any, metadata: Optional[Dict] = None) -> ValidationResult:
        if not isinstance(value, str):
            return PassResult()

        # Quick detection pass
        has_violation = any(p.search(value) for p in _ARCHITECTURE_DETECTION_PATTERNS)
        if not has_violation:
            return PassResult()

        # Apply all replacements
        sanitized = value
        for pattern, replacement in _protected_compiled:
            sanitized = pattern.sub(replacement, sanitized)

        return FailResult(
            error_message="Response contained internal tool or architecture names.",
            fix_value=sanitized,
        )


# ============================================================================
# Guardrail #3: Block Claim Drafting / Design-Around
# ============================================================================

_CLAIM_DRAFTING_PATTERNS = [
    r"\bdraft\s+(?:a\s+)?claims?\b",
    r"\bclaim\s+(?:language|wording|construction|formulation)\b",
    r"\bdesign[- ]around\b",
    r"\bcircumvent\s+(?:the\s+)?patent\b",
    r"\bavoid\s+(?:the\s+)?patent\b",
    r"\bwork\s*around\s+(?:the\s+)?(?:patent|claim)\b",
    r"\balternative\s+claim\b",
    r"\bprosecution\s+strategy\s+for\s+claims?\b",
    r"\bbroaden\s+(?:the\s+)?claims?\b",
    r"\bnarrow\s+(?:the\s+)?claims?\b",
    r"\bindependent\s+claim\s+(?:could|should|might)\b",
    r"\bdependent\s+claim\s+(?:could|should|might)\b",
    r"\bhere(?:'s| is)\s+(?:a\s+)?(?:draft|suggested|proposed)\s+claim\b",
    r"\bclaim\s+\d+\s*[:.]",  # "Claim 1: ..." pattern indicating claim drafting
]

_claim_drafting_compiled = [re.compile(p, re.IGNORECASE) for p in _CLAIM_DRAFTING_PATTERNS]


@register_validator(name="block-claim-drafting", data_type="string")
class BlockClaimDraftingDesignAround(Validator):
    """Blocks claim drafting and design-around advice."""

    def validate(self, value: Any, metadata: Optional[Dict] = None) -> ValidationResult:
        if not isinstance(value, str):
            return PassResult()

        for pattern in _claim_drafting_compiled:
            match = pattern.search(value)
            if match:
                return FailResult(
                    error_message=(
                        f"Response contains claim drafting or design-around "
                        f"advice (matched: '{match.group()}'). This requires "
                        f"legal expertise."
                    ),
                )

        return PassResult()


# ============================================================================
# Guardrail #4: Block Filing / Prosecution Advice
# ============================================================================

_FILING_ADVICE_PATTERNS = [
    r"\bfile\s+a\s+(?:patent|provisional|application)\b",
    r"\bfiling\s+strategy\b",
    r"\bprosecution\s+strategy\b",
    r"\bpatent\s+prosecution\b(?!\s+history)",  # exclude "prosecution history" in prior art context
    r"\boffice\s+action\s+response\b",
    r"\bnovelty\s+destruction\b",
    r"\bpriority\s+date\s+strategy\b",
    r"\byou\s+should\s+file\b",
    r"\brecommend\s+filing\b",
    r"\bi\s+(?:would\s+)?recommend\s+(?:that\s+you\s+)?fil(?:e|ing)\b",
    r"\bthreat\s+to\s+(?:your\s+)?novelty\b",
    r"\bfiling\s+(?:recommendation|deadline|window|opportunity)\b",
    r"\bprovisional\s+(?:application\s+)?(?:should|could|would)\b",
    r"\bpct\s+(?:application\s+)?(?:should|could|would)\s+(?:be\s+)?filed\b",
]

# Phrases that appear in legitimate bibliographic / prior art contexts
_FILING_EXCLUSION_PATTERNS = [
    r"\bfiling\s+date\b",
    r"\bpriority\s+date\b(?!\s+strategy)",
    r"\bprosecution\s+history\b",
    r"\bfile\s+wrapper\b",
]

_filing_compiled = [re.compile(p, re.IGNORECASE) for p in _FILING_ADVICE_PATTERNS]
_filing_exclusions = [re.compile(p, re.IGNORECASE) for p in _FILING_EXCLUSION_PATTERNS]


@register_validator(name="block-filing-advice", data_type="string")
class BlockFilingAdvice(Validator):
    """Blocks patent filing and prosecution advice.

    Excludes legitimate bibliographic references like 'filing date'
    and 'prosecution history' that appear in prior art analysis.
    """

    def validate(self, value: Any, metadata: Optional[Dict] = None) -> ValidationResult:
        if not isinstance(value, str):
            return PassResult()

        for pattern in _filing_compiled:
            match = pattern.search(value)
            if match:
                # Check if the match overlaps with an exclusion
                match_text = value[max(0, match.start() - 5):match.end() + 20]
                if any(exc.search(match_text) for exc in _filing_exclusions):
                    continue
                return FailResult(
                    error_message=(
                        f"Response contains filing or prosecution advice "
                        f"(matched: '{match.group()}'). Filing strategy "
                        f"is outside the agent's scope."
                    ),
                )

        return PassResult()


# ============================================================================
# Guardrail #10: Block Competitive Intelligence Analysis
# ============================================================================

_COMPETITIVE_INTEL_PATTERNS = [
    r"\bcompetitive\s+(?:landscape|intelligence|analysis|advantage)\b",
    r"\bcompetitor\s+(?:analysis|portfolio|strategy|positioning)\b",
    r"\bmarket\s+(?:positioning|share|strategy|opportunity)\b",
    r"\bbusiness\s+strategy\b",
    r"\btechnology\s+direction\s+(?:of|for)\s+(?:the\s+)?competit",
    r"\bcompetitor\s+(?:buckets?|categories|segments)\b",
    r"\bstrategic\s+(?:advantage|positioning|implications?)\b",
    r"\bcompetitive\s+threat\b",
    r"\bmarket\s+(?:leader|dominan)",
]

_competitive_compiled = [re.compile(p, re.IGNORECASE) for p in _COMPETITIVE_INTEL_PATTERNS]


@register_validator(name="block-competitive-intel", data_type="string")
class BlockCompetitiveIntelAnalysis(Validator):
    """Blocks competitive intelligence and market analysis.

    Distinguishes from legitimate technology landscape data in
    Section 9 of the novelty report (assignee counts, technology
    density) which is factual, not strategic.
    """

    def validate(self, value: Any, metadata: Optional[Dict] = None) -> ValidationResult:
        if not isinstance(value, str):
            return PassResult()

        for pattern in _competitive_compiled:
            match = pattern.search(value)
            if match:
                return FailResult(
                    error_message=(
                        f"Response contains competitive intelligence "
                        f"analysis (matched: '{match.group()}'). "
                        f"Competitive analysis is outside the agent's scope."
                    ),
                )

        return PassResult()


# ============================================================================
# Guardrail #11: Block Verdict Reframing
# ============================================================================

_VERDICT_REFRAMING_PATTERNS = [
    r"\bcraft\s+(?:a\s+)?(?:credible\s+)?novelty\s+angle\b",
    r"\breframe\s+(?:the\s+)?(?:verdict|conclusion|results?|findings?)\b",
    r"\bpresent\s+(?:this|the\s+invention)\s+as\s+novel\b",
    r"\bfavorable\s+interpretation\b",
    r"\binvestor[- ]safe\s+summary\b",
    r"\bspin\s+(?:the\s+)?results?\b",
    r"\bmake\s+(?:a\s+)?(?:credible\s+)?case\s+for\s+novelty\b",
    r"\bargue\s+(?:that|for)\s+novelty\b",
    r"\bcraft\s+(?:a\s+)?(?:narrative|story|angle)\b",
    r"\bdownplay\s+(?:the\s+)?(?:prior\s+art|references?|overlap)\b",
    r"\bminimize\s+(?:the\s+)?(?:prior\s+art|references?|overlap)\b",
]

_verdict_compiled = [re.compile(p, re.IGNORECASE) for p in _VERDICT_REFRAMING_PATTERNS]


@register_validator(name="block-verdict-reframing", data_type="string")
class BlockVerdictReframing(Validator):
    """Blocks offers to reframe search results favorably."""

    def validate(self, value: Any, metadata: Optional[Dict] = None) -> ValidationResult:
        if not isinstance(value, str):
            return PassResult()

        for pattern in _verdict_compiled:
            match = pattern.search(value)
            if match:
                return FailResult(
                    error_message=(
                        f"Response offers to reframe or spin results "
                        f"(matched: '{match.group()}'). The agent must "
                        f"maintain objectivity."
                    ),
                )

        return PassResult()
