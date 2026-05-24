"""Configuration settings for the langgraph_agent.

Loads configuration from environment variables (via .env file).
Uses pydantic-settings for validation and type conversion.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings


# Load .env from project root
_project_root = Path(__file__).parent.parent.parent
_env_path = _project_root / ".env"
if _env_path.exists():
    load_dotenv(_env_path)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Innography (Patent Search)
    innography_user_name: Optional[str] = Field(default=None, alias="INNOGRAPHY_USER_NAME")
    innography_user_secret: Optional[str] = Field(default=None, alias="INNOGRAPHY_USER_SECRET")
    innography_user_token: Optional[str] = Field(default=None, alias="INNOGRAPHY_USER_TOKEN")
    innography_token_url: str = Field(
        default="https://staging-api.innography.com/tokens",
        alias="INNOGRAPHY_TOKEN_URL"
    )
    innography_services_url: str = Field(
        default="https://staging.innography.com/innoservices",
        alias="INNOGRAPHY_SERVICES_URL"
    )
    
    # Web of Science (NPL Search)
    wos_api_key: Optional[str] = Field(default=None, alias="WOS_API_KEY")
    wos_endpoint: str = Field(
        default="https://wos-api.clarivate.com/api/wos",
        alias="WOS_ENDPOINT"
    )
    
    # NGSP (Semantic Search)
    clarivate_ngsp_api_key: Optional[str] = Field(default=None, alias="CLARIVATE_NGSP_API_KEY")
    
    # Derwent (Patent Search with Citations)
    derwent_api_base_url: str = Field(
        default="https://api.clarivate.com",
        alias="DERWENT_API_BASE_URL"
    )

    # Azure OpenAI
    azure_openai_api_key: Optional[str] = Field(default=None, alias="AZURE_OPENAI_API_KEY")
    azure_openai_endpoint: Optional[str] = Field(default=None, alias="AZURE_OPENAI_ENDPOINT")
    azure_openai_api_version: str = Field(
        default="2024-02-15-preview",
        alias="AZURE_OPENAI_API_VERSION"
    )
    azure_openai_deployment_name: str = Field(
        default="gpt-4o",
        alias="AZURE_OPENAI_DEPLOYMENT_NAME"
    )
    
    # Google Gemini
    google_api_key: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    
    # Feature Flags
    enable_npl_search: bool = Field(default=False, alias="ENABLE_NPL_SEARCH")

    # Query Refinement
    enable_query_refinement_agent: bool = Field(default=True, alias="ENABLE_QUERY_REFINEMENT_AGENT")
    auto_refine_on_zero_results: bool = Field(default=True, alias="AUTO_REFINE_ON_ZERO_RESULTS")
    max_refinement_attempts: int = Field(default=2, alias="MAX_REFINEMENT_ATTEMPTS")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
        populate_by_name = True


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.
    
    Returns:
        Settings object with all configuration loaded from environment.
    """
    return Settings()


def is_innography_configured() -> bool:
    """Check if Innography credentials are available."""
    s = get_settings()
    return bool(s.innography_user_name and s.innography_user_secret and s.innography_user_token)


def is_wos_configured() -> bool:
    """Check if Web of Science credentials are available."""
    s = get_settings()
    return bool(s.wos_api_key)


def is_npl_enabled() -> bool:
    """Check if NPL search (Web of Science) is enabled via feature flag."""
    return get_settings().enable_npl_search


def is_ngsp_configured() -> bool:
    """Check if NGSP credentials are available."""
    s = get_settings()
    return bool(s.clarivate_ngsp_api_key)


def get_config_status() -> dict:
    """Get status of all API configurations.
    
    Returns:
        Dictionary with configuration status for each service.
    """
    return {
        "innography": {
            "configured": is_innography_configured(),
            "service": "Patent Search (Innography)",
        },
        "wos": {
            "configured": is_wos_configured(),
            "service": "NPL Search (Web of Science)",
        },
        "ngsp": {
            "configured": is_ngsp_configured(),
            "service": "Semantic Search (NGSP)",
        },
        "azure_openai": {
            "configured": bool(get_settings().azure_openai_api_key),
            "service": "Azure OpenAI LLM",
        },
    }
