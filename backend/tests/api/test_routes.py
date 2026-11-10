from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api import routes
from app.model.models import ClassifyRequest, IssueType, JiraRequest


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(routes.router)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def classify_mock(monkeypatch):
    service = Mock(return_value={"issue_type": "task", "source": "LLM"})
    monkeypatch.setattr(routes, "classify_jira_issue_type", service)
    return service


@pytest.fixture
def create_mock(monkeypatch):
    service = AsyncMock(return_value={
        "success": True,
        "jira_id": "PROJ-123",
        "jira_url": "https://example.atlassian.net/browse/PROJ-123",
    })
    monkeypatch.setattr(routes, "create_jira", service)
    return service


@pytest.fixture
def issue_form():
    return {
        "summary": "Add upload support",
        "description": "Allow users to upload documents",
        "issue_type": "task",
        "jira_project_key": "proj",
    }


def test_health(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "service is up"}


@pytest.mark.parametrize("issue_type", [member.value for member in IssueType])
def test_classify_delegates_valid_request(client, classify_mock, issue_type):
    payload = {
        "summary": "Add upload support",
        "description": "Allow users to upload documents",
        "issue_type": issue_type,
    }
    response = client.post("/api/v1/jira/classify", json=payload)
    assert response.status_code == 200
    assert response.json() == classify_mock.return_value
    classify_mock.assert_called_once_with(ClassifyRequest(**payload))


@pytest.mark.parametrize("changes", [
    {"summary": "ab"},
    {"description": "ab"},
    {"issue_type": "unknown"},
    {"summary": "x" * 256},
])
def test_classify_rejects_invalid_input(client, classify_mock, changes):
    payload = {"summary": "Valid summary", "description": "Valid description", "issue_type": "auto"}
    response = client.post("/api/v1/jira/classify", json={**payload, **changes})
    assert response.status_code == 422
    classify_mock.assert_not_called()


def test_classify_requires_body(client, classify_mock):
    assert client.post("/api/v1/jira/classify").status_code == 422
    classify_mock.assert_not_called()


def test_create_issue_passes_normalized_form_to_service(client, create_mock, issue_form):
    issue_form["acceptance_criteria"] = "Documents can be uploaded"
    response = client.post("/api/v1/jira/issues", data=issue_form)
    assert response.status_code == 200
    assert response.json() == create_mock.return_value
    create_mock.assert_awaited_once_with(JiraRequest(**issue_form), [])
    assert create_mock.await_args.args[0].jira_project_key == "PROJ"


def test_create_subtask_passes_parent(client, create_mock, issue_form):
    issue_form.update(issue_type="subtask", parent_jira_id="PROJ-100")
    response = client.post("/api/v1/jira/issues", data=issue_form)
    assert response.status_code == 200
    create_mock.assert_awaited_once_with(JiraRequest(**issue_form), [])


@pytest.mark.parametrize("changes", [
    {"summary": "ab"},
    {"summary": "x" * 256},
    {"description": "ab"},
    {"issue_type": "auto"},
    {"issue_type": "unknown"},
    {"issue_type": "subtask"},
    {"jira_project_key": "12"},
    {"jira_project_key": "BAD-KEY"},
])
def test_create_rejects_invalid_form(client, create_mock, issue_form, changes):
    response = client.post("/api/v1/jira/issues", data={**issue_form, **changes})
    assert response.status_code == 422
    create_mock.assert_not_awaited()


@pytest.mark.parametrize("field", ["summary", "description", "issue_type", "jira_project_key"])
def test_create_requires_fields(client, create_mock, issue_form, field):
    del issue_form[field]
    response = client.post("/api/v1/jira/issues", data=issue_form)
    assert response.status_code == 422
    create_mock.assert_not_awaited()


def test_create_rejects_json_instead_of_form(client, create_mock, issue_form):
    response = client.post("/api/v1/jira/issues", json=issue_form)
    assert response.status_code == 422
    create_mock.assert_not_awaited()


def test_create_propagates_service_http_error(client, create_mock, issue_form):
    create_mock.side_effect = HTTPException(status_code=502, detail="Upstream Jira unavailable")
    response = client.post("/api/v1/jira/issues", data=issue_form)
    assert response.status_code == 502
    assert response.json() == {"detail": "Upstream Jira unavailable"}
    create_mock.assert_awaited_once()

