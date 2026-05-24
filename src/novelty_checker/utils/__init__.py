"""Utility modules for the Novelty Checker system."""

from src.novelty_checker.utils.feature_matrix import (
    FeatureMatrixGenerator,
    build_feature_matrix_from_state,
    validate_feature_matrix_in_report,
    extract_feature_matrix_from_markdown,
)
from src.novelty_checker.utils.report_coverage import (
    CoverageResult,
    verify_report_coverage_from_eval,
    verify_report_coverage_from_path,
)
from src.novelty_checker.utils.query_translator import (
    QueryTranslator
)

__all__ = [
    "FeatureMatrixGenerator",
    "build_feature_matrix_from_state",
    "validate_feature_matrix_in_report",
    "extract_feature_matrix_from_markdown",
    "CoverageResult",
    "verify_report_coverage_from_path",
    "verify_report_coverage_from_eval",
    "QueryTranslator",
]
