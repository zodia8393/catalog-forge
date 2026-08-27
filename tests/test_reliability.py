from catalog_forge.reliability import CircuitBreaker, CircuitState, RetryPolicy


def test_circuit_opens_and_recovers_half_open() -> None:
    circuit = CircuitBreaker(failure_threshold=2, recovery_timeout_seconds=5)
    circuit.record_failure(now=10)
    circuit.record_failure(now=11)

    assert circuit.state == CircuitState.OPEN
    assert circuit.allow_request(now=15) is False
    assert circuit.allow_request(now=16) is True
    assert circuit.state == CircuitState.HALF_OPEN

    circuit.record_success()
    assert circuit.state == CircuitState.CLOSED


def test_retry_after_takes_precedence_and_is_capped() -> None:
    policy = RetryPolicy(max_delay_seconds=10, jitter_ratio=0)

    assert policy.delay_for(3, retry_after=2) == 2
    assert policy.delay_for(3, retry_after=50) == 10
    assert policy.delay_for(3) == 1.0
