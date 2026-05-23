from http import HTTPStatus

from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_returns_service_status() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "ok", "service": "personal-budget-backend"}


def test_cors_preflight_allows_local_frontend_dev_origin() -> None:
    client = TestClient(app)

    response = client.options(
        "/workspaces",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "x-user-id,content-type",
        },
    )

    assert response.status_code == HTTPStatus.OK
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "GET" in response.headers["access-control-allow-methods"]
    assert "x-user-id" in response.headers["access-control-allow-headers"].lower()
