"""Canned safe replacement messages for critical guardrail violations.

Each message follows the pattern: decline + redirect (where applicable) +
offer what the agent CAN do.
"""

PATENTABILITY_REPLACEMENT = (
    "I'm not able to provide patentability opinions or assessments. "
    "My role is limited to conducting prior art searches and presenting "
    "feature coverage data. For patentability analysis, please consult "
    "a registered patent attorney."
)

CLAIM_DRAFTING_REPLACEMENT = (
    "I'm not able to assist with claim drafting, claim language suggestions, "
    "or design-around strategies. These require legal expertise. "
    "Please consult a patent attorney for guidance on claim construction "
    "and prosecution strategy."
)

FILING_ADVICE_REPLACEMENT = (
    "I'm not able to provide patent filing recommendations or prosecution "
    "strategy advice. I can present the feature coverage data from the "
    "prior art search. For filing strategy, please consult a patent attorney."
)

COMPETITIVE_INTEL_REPLACEMENT = (
    "I'm not able to provide competitive intelligence analysis, market "
    "positioning advice, or business strategy recommendations. My scope "
    "is limited to novelty assessment through prior art search. I can "
    "share the technology landscape data found during the search."
)

VERDICT_REFRAMING_REPLACEMENT = (
    "I must maintain objectivity in presenting search results. The prior "
    "art findings and feature coverage levels reflect the evidence as "
    "found. I'm not able to reframe or reinterpret results to support "
    "a particular conclusion."
)
