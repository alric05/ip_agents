"""Strategic reflection tool for novelty search progress assessment.

This module provides a think_tool that forces explicit reflection after each
search round, following the pattern from deepagents/examples/deep_research.

The tool helps agents:
- Assess current coverage levels per feature
- Identify gaps requiring additional searches
- Make explicit decisions about next steps
- Prevent over-searching and under-searching
"""

import logging
from langchain_core.tools import tool

_logger = logging.getLogger(__name__)


@tool(parse_docstring=True)
def think_tool(reflection: str) -> str:
    """Strategic reflection on novelty search progress and coverage assessment.
    
    Use this tool after EACH search to analyze results systematically.
    This creates a deliberate pause in the search workflow for quality decision-making.
    
    When to use:
    - After receiving search results: What key references did I find?
    - Before deciding next steps: Do I have enough coverage for core features?
    - When assessing coverage gaps: Which features still need A/B references?
    - Before concluding search: Can I provide comprehensive findings now?
    
    Your reflection should address these four areas:
    
    1. References Found: List the A/B refs from this search
       - Patent numbers or WOS IDs discovered
       - Their triage labels (A = high relevance, B = medium)
       - Which features they cover
    
    2. Coverage Update: Current coverage level per feature
       - NONE: No relevant refs yet
       - WEAK: 1 B-ref only  
       - MODERATE: 2+ B-refs OR 1 A-ref
       - STRONG: 1+ A-ref AND 2+ B-refs
       - SATURATED: 2+ A-refs AND 3+ B-refs
    
    3. Gap Analysis: Which core features still need coverage?
       - Core features (is_core=True) MUST reach STRONG
       - Non-core features can remain at MODERATE
       - Target: 70% overall coverage
    
    4. Decision: What to do next?
       - Continue searching? What specific query?
       - Switch strategy? Keyword to Semantic? Different terms?
       - Return findings? Why is current coverage sufficient?
    
    Args:
        reflection: Detailed analysis covering all four areas above
    
    Returns:
        Confirmation that reflection was recorded
    
    Example:
        think_tool('''
        ## References Found
        - JP2007171504A (A-ref): Covers F1 (worm gear) and F5 (housing)
        - CN106054342A (B-ref): Covers F5 only
        
        ## Coverage Update
        - F1: NONE → WEAK (1 A-ref, need more B-refs)
        - F2: NONE (no hits yet)
        - F3: NONE (no hits yet)
        - F4: NONE (no hits yet)
        - F5: WEAK → MODERATE (1 A-ref + 1 B-ref)
        
        ## Gap Analysis
        Core features F1, F2, F3 still at NONE/WEAK. Need targeted searches.
        
        ## Decision
        Continue searching with narrower terms for F2 (cascade mechanism).
        Next query: @(dwpi_title,dwpi_abstract) (cascade NEAR/5 gear)
        ''')
    """
    # Log when think_tool is called so we can verify it's being used
    _logger.info(f"🧠 think_tool called with reflection:\n{reflection[:500]}...")
    
    # Simple return like deep_research example - don't interfere with agent workflow
    return f"📊 Reflection recorded. Continue with your decided action."
