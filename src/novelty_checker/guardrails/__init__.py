"""Guardrails package for novelty checker agent.

Provides custom guardrails-ai validators and middleware for enforcing
safety boundaries identified in the agentic risk assessment.

Three-layer defense:
1. System prompt instructions (GUARDRAILS_INSTRUCTIONS in prompts.py)
2. Pre-processing middleware (GuardrailsPromptMiddleware)
3. Post-processing middleware (GuardrailsOutputFilterMiddleware)
"""

from src.novelty_checker.guardrails.output_filter_middleware import (
    GuardrailsOutputFilterMiddleware,
)
from src.novelty_checker.guardrails.prompt_middleware import (
    GuardrailsPromptMiddleware,
)
from src.novelty_checker.guardrails.validators import (
    BlockArchitectureDisclosure,
    BlockClaimDraftingDesignAround,
    BlockCompetitiveIntelAnalysis,
    BlockFilingAdvice,
    BlockPatentabilityOpinion,
    BlockVerdictReframing,
)

__all__ = [
    "BlockArchitectureDisclosure",
    "BlockClaimDraftingDesignAround",
    "BlockCompetitiveIntelAnalysis",
    "BlockFilingAdvice",
    "BlockPatentabilityOpinion",
    "BlockVerdictReframing",
    "GuardrailsOutputFilterMiddleware",
    "GuardrailsPromptMiddleware",
]
