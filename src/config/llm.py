"""
Centralized LLM Configuration for Novelty Checker Deep Agent.

This module provides centralized control over Azure OpenAI LLM configuration
using LiteLLM for unified model access.

Usage:
    from langgraph_agent.llm_config import get_llm, get_azure_model_name
    llm = get_llm()  # Returns ChatLiteLLM instance for Azure OpenAI
"""

import logging
import os
from pathlib import Path

import litellm
from dotenv import load_dotenv
from langchain_litellm import ChatLiteLLM

# Load .env from project root
_project_root = Path(__file__).parent.parent.parent
load_dotenv(_project_root / ".env")

# Configure logging
_logger = logging.getLogger("llm_config")

# Drop unsupported params for Azure OpenAI (e.g., top_p is not supported for some Azure models)
litellm.drop_params = True


# ═══════════════════════════════════════════════════════════════════════════════
# AZURE OPENAI CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Azure OpenAI deployment name (model)
AZURE_DEPLOYMENT = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-5")

# Force temperature=1 for Azure models that don't support custom temperature (e.g., gpt-5)
AZURE_FORCE_TEMPERATURE_1 = os.environ.get("AZURE_FORCE_TEMPERATURE_1", "").lower() in ("true", "1", "yes")

# GPT-5 specific: Longer timeout for GPT-5 models (they can be slower with complex tool chains)
IS_GPT5_MODEL = "gpt-5" in AZURE_DEPLOYMENT.lower() or "gpt5" in AZURE_DEPLOYMENT.lower()

# Default timeout: 10 min for regular models, 15 min for GPT-5
DEFAULT_TIMEOUT_SECONDS = int(os.environ.get("LLM_TIMEOUT", "900" if IS_GPT5_MODEL else "600"))

# Retry configuration for transient Azure connection errors
MAX_RETRIES = int(os.environ.get("LLM_MAX_RETRIES", "3"))


# ═══════════════════════════════════════════════════════════════════════════════
# MODEL NAME HELPERS
# ═══════════════════════════════════════════════════════════════════════════════


def get_azure_model_name() -> str:
    """Get Azure OpenAI model name from environment.
    
    Returns:
        LiteLLM-formatted model string (azure/<deployment>)
    """
    deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-5")
    return f"azure/{deployment}"


# ═══════════════════════════════════════════════════════════════════════════════
# LLM FACTORY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def create_azure_llm() -> ChatLiteLLM:
    """Create Azure OpenAI ChatLiteLLM instance with GPT-5 aware timeout.
    
    Returns:
        Configured ChatLiteLLM instance for Azure OpenAI.
    """
    return ChatLiteLLM(
        model=get_azure_model_name(),
        api_base=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview"),
        timeout=DEFAULT_TIMEOUT_SECONDS,
        max_retries=MAX_RETRIES,
    )


def get_llm() -> ChatLiteLLM:
    """Get the configured Azure OpenAI LLM.
    
    Returns:
        ChatLiteLLM instance configured for Azure OpenAI.
    """
    _logger.info(f"Using Azure OpenAI with model: {get_azure_model_name()}")
    return create_azure_llm()


def get_active_backend_info() -> dict:
    """Get information about the currently active LLM backend."""
    return {
        "provider": "azure",
        "model": get_azure_model_name(),
        "endpoint": os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
        "api_version": os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview"),
        "timeout": DEFAULT_TIMEOUT_SECONDS,
        "max_retries": MAX_RETRIES,
        "force_temperature_1": AZURE_FORCE_TEMPERATURE_1,
    }
