"""Evaluation scorers for the novelty checker agent.

Provides deterministic and LLM-judge metrics that consume eval_trace.json
and ground truth fixtures to produce scored results.
"""

from src.novelty_checker.evaluation.scorers._base import NoveltyBaseMetric, ScorerResult

__all__ = [
    "NoveltyBaseMetric",
    "ScorerResult",
]
