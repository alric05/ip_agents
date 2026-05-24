"""Middleware modules for the Novelty Checker deep agent.

This package provides custom middleware for:
- Automatic findings persistence
- Feature confirmation gate enforcement
- Autonomous research enforcement (post-Gate-2)
- Research loop continuation enforcement
- Citation analysis enforcement
- Patent lifecycle tracking and loss detection
- Content policy violation guard for subagents
"""

from .autonomous_research import AutonomousResearchMiddleware
from .content_filter import ContentFilterMiddleware
from .feature_confirmation import FeatureConfirmationMiddleware
from .findings import FindingsPersistenceMiddleware
from .patent_tracking import PatentTrackingMiddleware
from .research_continuation import ResearchContinuationMiddleware

__all__ = [
    "AutonomousResearchMiddleware",
    "ContentFilterMiddleware",
    "FeatureConfirmationMiddleware",
    "FindingsPersistenceMiddleware",
    "PatentTrackingMiddleware",
    "ResearchContinuationMiddleware",
]
