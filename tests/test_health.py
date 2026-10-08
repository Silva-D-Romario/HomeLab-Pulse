from fastapi.testclient import TestClient

from homelab_pulse.main import app


client = TestClient(app)


def test_health_check_returns_application_status() -> None:
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["application"] == "HomeLab Pulse"
    assert payload["environment"] == "development"
    assert payload["version"] == "0.1.0"
    assert payload["status"] == "UP"
    assert payload["timestamp"]


def test_openapi_documentation_is_available() -> None:
    response = client.get("/docs")

    assert response.status_code == 200
    assert "swagger-ui" in response.text
