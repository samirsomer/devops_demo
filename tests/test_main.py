"""Smoke tests for every endpoint.

Run with: pytest -v
These are intentionally lightweight — they check status codes and
response shapes, not business logic (there isn't much of it), and are
meant as a starting point for wiring into a CI pipeline.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_liveness() -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_returns_200_or_503() -> None:
    response = client.get("/health/ready")
    assert response.status_code in (200, 503)


def test_version() -> None:
    response = client.get("/version")
    assert response.status_code == 200
    body = response.json()
    assert "app_version" in body
    assert "python_version" in body


def test_delay_endpoint() -> None:
    response = client.get("/simulate/delay", params={"min_ms": 1, "max_ms": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["actual_delay_ms"] >= 0


def test_delay_invalid_range() -> None:
    response = client.get("/simulate/delay", params={"min_ms": 100, "max_ms": 1})
    assert response.status_code == 400


def test_error_endpoint_never_errors_at_zero_rate() -> None:
    response = client.get("/simulate/error", params={"error_rate": 0})
    assert response.status_code == 200


def test_error_endpoint_always_errors_at_full_rate() -> None:
    response = client.get("/simulate/error", params={"error_rate": 1})
    assert response.status_code in (400, 404, 429, 500, 503)


def test_cpu_task() -> None:
    response = client.get("/simulate/cpu", params={"iterations": 1000})
    assert response.status_code == 200
    assert response.json()["primes_found"] > 0


def test_memory_task() -> None:
    response = client.get("/simulate/memory", params={"size_mb": 1, "hold_ms": 1})
    assert response.status_code == 200
    assert response.json()["allocated_bytes"] == 1024 * 1024


def test_force_status_success() -> None:
    response = client.get("/simulate/status/200")
    assert response.status_code == 200


def test_force_status_error() -> None:
    response = client.get("/simulate/status/503")
    assert response.status_code == 503


def test_force_status_invalid_code() -> None:
    response = client.get("/simulate/status/999")
    assert response.status_code == 400


def test_echo() -> None:
    response = client.post("/simulate/echo", json={"message": "hi", "payload": {"a": 1}})
    assert response.status_code == 200
    body = response.json()
    assert body["received"]["message"] == "hi"
    assert body["request_id"] is not None


def test_metrics_endpoint_exposed() -> None:
    response = client.get("/metrics")
    assert response.status_code == 200
    assert b"http_requests" in response.content or b"# HELP" in response.content
