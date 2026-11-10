import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import config, logging_config
from app.api import routes
from app.integration.mcp_exceptions import MCPIntegrationError


@pytest.fixture
def main_module(monkeypatch):
    # Execute main.py afresh without changing the shared app.main module or cache.
    # Mock before import so .env credentials and logging files are never required.
    monkeypatch.setattr(config, "get_settings", Mock(return_value=SimpleNamespace(
        cors_origins=["http://localhost:5500"],
    )))
    monkeypatch.setattr(logging_config, "configure_logging", Mock())
    monkeypatch.setattr(routes, "classify_jira_issue_type", Mock(return_value={
        "issue_type": "task", "source": "LLM",
    }))
    monkeypatch.setattr(routes, "create_jira", AsyncMock(return_value={
        "success": True, "jira_id": "PROJ-123", "jira_url": None,
    }))
    spec = importlib.util.spec_from_file_location(
        "app._main_under_test", Path(config.__file__).with_name("main.py"),
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def client(main_module):
    # Allow the production 500 handler to return its response to the test client.
    with TestClient(main_module.app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def issue_form():
    return {
        "summary": "Add upload support",
        "description": "Allow document uploads",
        "issue_type": "task",
        "jira_project_key": "PROJ",
    }


def test_application_initializes_settings_and_logging(main_module):
    assert main_module.app.title == "Jira GitHub MCP Integration API"
    config.get_settings.assert_called_once_with()
    logging_config.configure_logging.assert_called_once_with()


def test_health_router_is_registered(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "service is up"}


def test_openapi_exposes_jira_routes(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "Jira GitHub MCP Integration API"
    assert "get" in schema["paths"]["/api/v1/health"]
    assert "post" in schema["paths"]["/api/v1/jira/classify"]
    assert "post" in schema["paths"]["/api/v1/jira/issues"]


def test_unknown_route_uses_custom_http_error_format(client):
    response = client.get("/missing-route")
    assert response.status_code == 404
    assert response.json() == {"success": False, "error": "Not Found"}


def test_unsupported_method_uses_custom_error_and_preserves_allow_header(client):
    response = client.post("/api/v1/health")
    assert response.status_code == 405
    assert response.json() == {"success": False, "error": "Method Not Allowed"}
    assert "GET" in response.headers["allow"]


def test_service_http_error_preserves_status_detail_and_headers(client, issue_form):
    routes.create_jira.side_effect = HTTPException(
        status_code=429, detail="Try again later", headers={"Retry-After": "30"},
    )
    response = client.post("/api/v1/jira/issues", data=issue_form)
    assert response.status_code == 429
    assert response.json() == {"success": False, "error": "Try again later"}
    assert response.headers["retry-after"] == "30"
    routes.create_jira.assert_awaited_once()


@pytest.mark.parametrize("endpoint,payload,location", [
    ("/api/v1/jira/classify", {}, "summary"),
    ("/api/v1/jira/classify", {
        "summary": "Valid summary", "description": "Valid description", "issue_type": "invalid",
    }, "issue_type"),
    ("/api/v1/jira/issues", {}, "summary"),
])
def test_validation_error_uses_custom_format(client, endpoint, payload, location):
    kwargs = {"data": payload} if endpoint.endswith("issues") else {"json": payload}
    response = client.post(endpoint, **kwargs)
    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"] == "Validation error"
    assert any(location in detail["loc"] for detail in body["details"])
    routes.create_jira.assert_not_awaited()
    routes.classify_jira_issue_type.assert_not_called()


def test_model_validator_error_is_json_serializable(client, issue_form):
    issue_form["issue_type"] = "auto"
    response = client.post("/api/v1/jira/issues", data=issue_form)
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "Validation error"
    assert any("must be reviewed" in detail["msg"] for detail in body["details"])
    routes.create_jira.assert_not_awaited()


@pytest.mark.parametrize("status", [401, 403, 429, 502, 504])
def test_mcp_error_uses_its_status_and_message(client, issue_form, status):
    routes.create_jira.side_effect = MCPIntegrationError("Mock MCP failure", status)
    response = client.post("/api/v1/jira/issues", data=issue_form)
    assert response.status_code == status
    assert response.json() == {"success": False, "error": "Mock MCP failure"}
    routes.create_jira.assert_awaited_once()


def test_unexpected_error_returns_safe_response_and_logs(client, issue_form, main_module, monkeypatch):
    logger = Mock()
    monkeypatch.setattr(main_module, "logger", logger)
    routes.create_jira.side_effect = RuntimeError("private upstream credentials")
    response = client.post("/api/v1/jira/issues", data=issue_form)
    assert response.status_code == 500
    assert response.json() == {"success": False, "error": "Internal server error"}
    assert "private upstream credentials" not in response.text
    logger.exception.assert_called_once_with("Unhandled exception occurred")


def test_allowed_origin_receives_cors_headers(client):
    response = client.get("/api/v1/health", headers={"Origin": "http://localhost:5500"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5500"


def test_disallowed_origin_has_no_allow_origin_header(client):
    response = client.get("/api/v1/health", headers={"Origin": "https://untrusted.example"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("method", ["GET", "POST"])
def test_cors_preflight_allows_configured_methods(client, method):
    response = client.options("/api/v1/jira/issues", headers={
        "Origin": "http://localhost:5500",
        "Access-Control-Request-Method": method,
        "Access-Control-Request-Headers": "Content-Type",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5500"
    assert method in response.headers["access-control-allow-methods"]
    assert "content-type" in response.headers["access-control-allow-headers"].lower()


@pytest.mark.parametrize("origin,method", [
    ("https://untrusted.example", "POST"),
    ("http://localhost:5500", "DELETE"),
])
def test_cors_preflight_rejects_unconfigured_origin_or_method(client, origin, method):
    response = client.options("/api/v1/jira/issues", headers={
        "Origin": origin,
        "Access-Control-Request-Method": method,
    })
    assert response.status_code == 400
