"""Configuration module for the Novelty Checker agent.

This module consolidates all configuration:
- LLM configuration (llm_config.py)
- Application settings (settings.py)
"""

from src.config.settings import (
    Settings,
    get_settings,
    is_innography_configured,
    is_wos_configured,
    is_ngsp_configured,
    get_config_status,
)
from src.config.llm import (
    get_llm,
    get_azure_model_name,
    get_active_backend_info,
    create_azure_llm,
)

__all__ = [
    # Settings
    "Settings",
    "get_settings",
    "is_innography_configured",
    "is_wos_configured",
    "is_ngsp_configured",
    "get_config_status",
    # LLM
    "get_llm",
    "get_azure_model_name",
    "get_active_backend_info",
    "create_azure_llm",
]
