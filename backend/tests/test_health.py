from fastapi.testclient import TestClient


def test_live_health(client: TestClient) -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "ProductFlow API",
        "version": "0.1.0",
    }
    assert response.headers["X-Request-ID"]


def test_api_prefixed_live_health(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")

    assert response.status_code == 200


def test_ready_health_uses_real_dependencies(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["dependencies"] == {
        "postgres": {"status": "ok", "message": None},
        "redis": {"status": "ok", "message": None},
    }

