"""Resilience patterns for tool calls: retry, circuit breaker, timeout.

This module provides decorators and utilities to make API calls more resilient
to transient failures, following industry best practices for production systems.

Key Patterns:
- Exponential backoff retry for transient failures
- Configurable retry policies per tool type
- Detailed logging for debugging retry behavior

Usage:
    from src.tools.resilience import retry_with_backoff

    @retry_with_backoff(max_retries=3, base_delay=2.0)
    def my_api_call():
        return requests.get("https://api.example.com")
"""

import functools
import time
import logging
from typing import Callable, TypeVar, ParamSpec

_logger = logging.getLogger(__name__)

P = ParamSpec('P')
T = TypeVar('T')


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    retriable_exceptions: tuple = (Exception,),
):
    """Decorator for retry with exponential backoff.

    Retries a function with increasing delays: base_delay, base_delay*2, base_delay*4, etc.
    This pattern is essential for production systems interacting with external APIs that
    may experience transient failures (network issues, rate limits, temporary outages).

    Args:
        max_retries: Maximum retry attempts (default 3)
            Total attempts = max_retries + 1 (initial attempt)
        base_delay: Initial delay in seconds (default 1.0)
            First retry waits base_delay seconds
        max_delay: Maximum delay cap (default 60.0)
            Prevents exponential growth from causing excessive waits
        exponential_base: Multiplier for backoff (default 2.0)
            Delay formula: base_delay * (exponential_base ** attempt)
        retriable_exceptions: Exception types to retry (default all)
            Tuple of exception classes that trigger retry

    Returns:
        Decorated function that retries on failure

    Example:
        @retry_with_backoff(max_retries=3, base_delay=2.0)
        def search_patents(query: str):
            return api_client.search(query)

        # Retry schedule for base_delay=2.0, exponential_base=2.0:
        # - Attempt 1: Immediate
        # - Attempt 2: After 2s delay
        # - Attempt 3: After 4s delay
        # - Attempt 4: After 8s delay

    Raises:
        The last exception encountered if all retries are exhausted
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)

                except retriable_exceptions as e:
                    last_exception = e

                    # If this was the last attempt, log error and raise
                    if attempt == max_retries:
                        _logger.error(
                            f"{func.__name__} failed after {max_retries + 1} attempts: {e}"
                        )
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay
                    )

                    _logger.warning(
                        f"{func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )

                    time.sleep(delay)

            # Should never reach here, but if we do, raise the last exception
            raise last_exception

        return wrapper
    return decorator


# Convenience decorators for common retry policies

def retry_search_api(func: Callable[P, T]) -> Callable[P, T]:
    """Retry decorator optimized for search API calls.

    Uses longer delays suitable for potentially rate-limited search APIs.
    - 3 retries with 2s base delay
    - Max delay capped at 30s
    """
    return retry_with_backoff(
        max_retries=3,
        base_delay=2.0,
        max_delay=30.0,
    )(func)


def retry_quick_api(func: Callable[P, T]) -> Callable[P, T]:
    """Retry decorator for quick API calls.

    Uses shorter delays for fast, lightweight APIs.
    - 2 retries with 0.5s base delay
    - Max delay capped at 5s
    """
    return retry_with_backoff(
        max_retries=2,
        base_delay=0.5,
        max_delay=5.0,
    )(func)
