"""LangGraph Studio entry point for the Novelty Checker agent.

This module exposes the compiled graph for use with LangGraph Studio/UI.
Run with: langgraph dev

IMPORTANT: Session Management
- Each new thread in LangGraph Studio gets a fresh session workspace
- The graph factory function creates a new session for each unique thread_id
- This ensures a fresh workspace for each novelty check
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

# Import LLM configuration
from src.config.llm import get_llm, get_active_backend_info

# Import the deep agent factory and session utilities
from src.novelty_checker.deep_agent import create_deep_agent

# Log which backend is being used
import logging
logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger(__name__)
backend_info = get_active_backend_info()
_logger.info(f"LangGraph Studio using: {backend_info['provider']} - {backend_info['model']}")

# Derwent JWT pre-flight. Studio takes the token from DERWENT_JWT_TOKEN at
# module load; warn loudly here if it's missing/expired so the user notices
# before they start a run rather than after metrics collapse to 0.00.
# Warn-only (not hard fail) because `langgraph dev` imports this module at
# server boot and crashing would block the whole Studio UI.
from src.tools.clients.derwent_auth import check_derwent_jwt, DerwentAuthError
try:
    check_derwent_jwt()
except DerwentAuthError as _jwt_err:
    _logger.warning("Derwent JWT pre-flight FAILED: %s", _jwt_err)


# =============================================================================
# Graph and Session Management
# =============================================================================

# Create the graph for LangGraph Studio with per-thread session isolation.
# use_backend_factory=True ensures each thread gets its own workspace directory
# under sessions/{thread_id}/, preventing artifact leakage between conversations.
#
# Note: use_custom_state=False disables custom state reducers to enable
# JSON schema serialization for the UI. For production use (Python API),
# use create_deep_agent() with use_custom_state=True (default) to get:
# - Safe parallel subagent updates
# - Reference deduplication via merge_references reducer
# - Findings accumulator merging via merge_findings_accumulator reducer
# - Coverage merging via merge_coverage reducer
graph, _session_id = create_deep_agent(
    model=get_llm(),
    checkpointer=None,
    use_custom_state=False,  # Required for LangGraph Studio UI compatibility
    use_backend_factory=True,  # Per-thread session isolation
)

# Monkey-patch langgraph_api.serde.default to recover from MockValSer errors.
# In the langgraph dev server (uvicorn + reload), Pydantic model serializers can
# become permanently MockValSer due to import-order or reload timing.
# model_rebuild() does not fix it, so we bypass model_dump() entirely and use
# dict(obj) which reads field values directly from __dict__, skipping the broken
# Pydantic serializer. orjson recursively calls default() for nested values.
import langgraph_api.serde as _serde_mod

_original_serde_default = _serde_mod.default


def _mockvalser_safe_default(obj):
    try:
        return _original_serde_default(obj)
    except TypeError as e:
        if 'MockValSer' in str(e):
            return dict(obj)
        raise


_serde_mod.default = _mockvalser_safe_default

# Strip middleware-contributed channels whose type annotations break Pydantic
# BaseModel schema generation (MockValSer / PydanticForbiddenQualifier errors):
#   - files:               Annotated[NotRequired[...], reducer]
#   - todos:               Annotated[NotRequired[...], OmitFromSchema]
#   - structured_response:  Annotated[~ResponseT, OmitFromSchema]  (unresolved TypeVar)
#   - memory_contents:      Annotated[dict, OmitFromSchema(output=True)]
# Internal graph.channels are unaffected — middleware read/write still works.
_broken_channels = ('files', 'todos', 'structured_response', 'memory_contents')
graph.output_channels = [ch for ch in graph.output_channels if ch not in _broken_channels]
graph.stream_channels = [ch for ch in graph.stream_channels if ch not in _broken_channels]
_logger.info(
    f"LangGraph Studio graph created with thread-aware backend factory "
    f"(default session: {_session_id})"
)

# Note: No _clear_session_files() call at module load.
# Each thread creates its own fresh workspace on first access via
# ThreadAwareBackendFactory._prepare_session_directory().
