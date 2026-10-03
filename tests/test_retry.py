from app.automation.retry_manager import RetryPolicy, policy_for


def test_retry_count_includes_the_first_attempt_and_stops():
    policy = policy_for(2, 3000)
    assert policy.max_attempts == 3
    assert policy.should_retry(1)
    assert policy.should_retry(2)
    assert not policy.should_retry(3)
    assert policy.delay_seconds() == 3


def test_zero_retries_means_one_attempt():
    policy = RetryPolicy(count=0, delay_ms=0)
    assert policy.max_attempts == 1
    assert not policy.should_retry(1)
