"""Tests for resilience patterns (Phase 1)."""

import time
from src.tools.resilience import retry_with_backoff


def test_retry_succeeds_immediately():
    """Test that function succeeds on first attempt without retry."""
    call_count = 0

    @retry_with_backoff(max_retries=3, base_delay=0.1)
    def successful_function():
        nonlocal call_count
        call_count += 1
        return "Success"

    result = successful_function()

    assert result == "Success"
    assert call_count == 1, "Should succeed on first attempt"


def test_retry_succeeds_on_third_attempt():
    """Test that function succeeds after 2 failures."""
    call_count = 0

    @retry_with_backoff(max_retries=3, base_delay=0.1)
    def flaky_function():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("Transient failure")
        return "Success"

    start_time = time.time()
    result = flaky_function()
    duration = time.time() - start_time

    assert result == "Success"
    assert call_count == 3, "Should succeed on third attempt"
    # Should have waited ~0.1s + ~0.2s = ~0.3s (exponential backoff)
    assert duration >= 0.3, f"Should have waited for retries, but took {duration}s"


def test_retry_exhausts_all_attempts():
    """Test that function raises exception after all retries are exhausted."""
    call_count = 0

    @retry_with_backoff(max_retries=2, base_delay=0.05)
    def always_fails():
        nonlocal call_count
        call_count += 1
        raise ValueError("Persistent failure")

    try:
        always_fails()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert str(e) == "Persistent failure"
        assert call_count == 3, "Should attempt 3 times (1 initial + 2 retries)"


def test_retry_exponential_backoff():
    """Test that retry delays follow exponential backoff pattern."""
    call_times = []

    @retry_with_backoff(max_retries=3, base_delay=0.1, exponential_base=2.0)
    def failing_function():
        call_times.append(time.time())
        if len(call_times) < 4:
            raise Exception("Transient failure")
        return "Success"

    result = failing_function()

    assert result == "Success"
    assert len(call_times) == 4

    # Check delays between attempts
    delay1 = call_times[1] - call_times[0]  # Should be ~0.1s
    delay2 = call_times[2] - call_times[1]  # Should be ~0.2s
    delay3 = call_times[3] - call_times[2]  # Should be ~0.4s

    assert 0.08 <= delay1 <= 0.15, f"First delay should be ~0.1s, got {delay1}s"
    assert 0.18 <= delay2 <= 0.25, f"Second delay should be ~0.2s, got {delay2}s"
    assert 0.38 <= delay3 <= 0.45, f"Third delay should be ~0.4s, got {delay3}s"


def test_retry_max_delay_cap():
    """Test that delay is capped at max_delay."""
    call_times = []

    @retry_with_backoff(max_retries=5, base_delay=10.0, max_delay=0.2, exponential_base=2.0)
    def failing_function():
        call_times.append(time.time())
        if len(call_times) < 3:
            raise Exception("Transient failure")
        return "Success"

    result = failing_function()

    assert result == "Success"
    assert len(call_times) == 3

    # Even though base_delay=10.0, delays should be capped at 0.2s
    delay1 = call_times[1] - call_times[0]
    delay2 = call_times[2] - call_times[1]

    assert delay1 <= 0.25, f"First delay should be capped at 0.2s, got {delay1}s"
    assert delay2 <= 0.25, f"Second delay should be capped at 0.2s, got {delay2}s"


def test_retry_specific_exceptions_only():
    """Test that only specific exceptions trigger retry."""
    call_count = 0

    @retry_with_backoff(max_retries=3, base_delay=0.05, retriable_exceptions=(ValueError,))
    def raises_type_error():
        nonlocal call_count
        call_count += 1
        raise TypeError("Not retriable")

    try:
        raises_type_error()
        assert False, "Should have raised TypeError"
    except TypeError:
        assert call_count == 1, "Should not retry TypeError (only ValueError is retriable)"


def test_retry_with_return_value():
    """Test that return value is preserved through decorator."""
    @retry_with_backoff(max_retries=2, base_delay=0.05)
    def returns_dict():
        return {"status": "ok", "data": [1, 2, 3]}

    result = returns_dict()

    assert result == {"status": "ok", "data": [1, 2, 3]}
    assert isinstance(result, dict)


def test_retry_preserves_function_metadata():
    """Test that decorator preserves function name and docstring."""
    @retry_with_backoff(max_retries=2)
    def my_function():
        """This is my function."""
        return "result"

    assert my_function.__name__ == "my_function"
    assert my_function.__doc__ == "This is my function."


if __name__ == "__main__":
    # Run tests
    test_retry_succeeds_immediately()
    print("✅ test_retry_succeeds_immediately passed")

    test_retry_succeeds_on_third_attempt()
    print("✅ test_retry_succeeds_on_third_attempt passed")

    test_retry_exhausts_all_attempts()
    print("✅ test_retry_exhausts_all_attempts passed")

    test_retry_exponential_backoff()
    print("✅ test_retry_exponential_backoff passed")

    test_retry_max_delay_cap()
    print("✅ test_retry_max_delay_cap passed")

    test_retry_specific_exceptions_only()
    print("✅ test_retry_specific_exceptions_only passed")

    test_retry_with_return_value()
    print("✅ test_retry_with_return_value passed")

    test_retry_preserves_function_metadata()
    print("✅ test_retry_preserves_function_metadata passed")

    print("\n🎉 All resilience tests passed!")
