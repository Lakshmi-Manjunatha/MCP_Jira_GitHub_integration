import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from app.integration.mcp_exceptions import MCPIntegrationError
from app.model.models import ClassifyRequest, IssueType, JiraRequest
from app.service import jira_service as service


@pytest.fixture(autouse=True)
def settings(monkeypatch):
    settings = SimpleNamespace(atlassian_cloud_id="https://example.atlassian.net/")
    monkeypatch.setattr(service, "get_settings", Mock(return_value=settings))
    return settings


@pytest.fixture(autouse=True)
def mcp_call(monkeypatch):
    call = AsyncMock(return_value={"structuredContent": {"key": "PROJ-123"}})
    # Patch where the imported MCP function is used by the service.
    monkeypatch.setattr(service, "call_jira_mcp_tool", call)
    return call


@pytest.fixture
def issue():
    return JiraRequest(
        summary="Add upload support",
        description="Allow document uploads",
        issue_type=IssueType.TASK,
        jira_project_key="proj",
    )


@pytest.mark.parametrize("issue_type", list(IssueType))
def test_classification_returns_expected_type_and_source(issue_type, mcp_call):
    request = ClassifyRequest(
        summary="Add upload support",
        description="Allow document uploads",
        issue_type=issue_type,
    )
    result = service.classify_jira_issue_type(request)
    assert result.issue_type == (IssueType.TASK if issue_type == IssueType.AUTO else issue_type)
    assert result.source == ("LLM" if issue_type == IssueType.AUTO else "manual")
    mcp_call.assert_not_awaited()


@pytest.mark.parametrize("issue_type", [IssueType.STORY, IssueType.BUG, IssueType.TASK])
def test_create_sends_expected_mcp_arguments(issue, mcp_call, settings, issue_type):
    issue.issue_type = issue_type
    # Parent must only be sent for subtasks.
    issue.parent_jira_id = "PROJ-100"
    result = asyncio.run(service.create_jira(issue))
    mcp_call.assert_awaited_once_with("createJiraIssue", {
        "cloudId": settings.atlassian_cloud_id,
        "projectKey": "PROJ",
        "summary": "Add upload support",
        "issueType": issue_type.value.capitalize(),
        "description": "Allow document uploads",
        "contentFormat": "markdown",
    })
    assert result.model_dump() == {
        "success": True,
        "jira_id": "PROJ-123",
        "jira_url": "https://example.atlassian.net/browse/PROJ-123",
    }


def test_create_subtask_includes_parent(issue, mcp_call):
    issue.issue_type = IssueType.SUBTASK
    issue.parent_jira_id = "PROJ-100"
    asyncio.run(service.create_jira(issue))
    mcp_call.assert_awaited_once()
    arguments = mcp_call.await_args.args[1]
    assert arguments["parent"] == "PROJ-100"
    assert arguments["issueType"] == "Subtask"


@pytest.mark.parametrize("criteria", [None, "", "User can upload a PDF"])
def test_acceptance_criteria_are_appended_without_mutating_request(issue, mcp_call, criteria):
    issue.acceptance_criteria = criteria
    original_description = issue.description
    asyncio.run(service.create_jira(issue))
    expected = original_description
    if criteria:
        expected += "\n\n## Acceptance Criteria\n" + criteria
    assert mcp_call.await_args.args[1]["description"] == expected
    assert issue.description == original_description


@pytest.mark.parametrize("issue_type,detail", [
    (IssueType.AUTO, "Confirm issue type before creating Jira"),
    (IssueType.SUBTASK, "Parent Jira ID is required for subtask"),
])
def test_service_guards_reject_unreviewed_or_parentless_issues(issue, mcp_call, issue_type, detail):
    # Mutate a valid model to exercise service guards independently of model validation.
    issue.issue_type = issue_type
    with pytest.raises(HTTPException) as raised:
        asyncio.run(service.create_jira(issue))
    assert raised.value.status_code == 400
    assert raised.value.detail == detail
    mcp_call.assert_not_awaited()
    service.get_settings.assert_not_called()


def test_create_propagates_mcp_failure_without_retrying(issue, mcp_call):
    error = MCPIntegrationError("Atlassian rate limit exceeded", 429)
    mcp_call.side_effect = error
    with pytest.raises(MCPIntegrationError) as raised:
        asyncio.run(service.create_jira(issue))
    assert raised.value is error
    mcp_call.assert_awaited_once()


def test_create_unparseable_result_warns_before_retry(issue, mcp_call):
    mcp_call.return_value = {"content": [{"type": "text", "text": "Created successfully"}]}
    with pytest.raises(HTTPException) as raised:
        asyncio.run(service.create_jira(issue))
    assert raised.value.status_code == 502
    assert "Check Jira before retrying" in raised.value.detail
    mcp_call.assert_awaited_once()


@pytest.mark.parametrize("payload,expected", [
    ({"structuredContent": {"key": "PROJ-123"}}, "PROJ-123"),
    ({"structuredContent": {"issueKey": "PROJ-124"}}, "PROJ-124"),
    ({"content": [{"type": "text", "text": '{"key": "PROJ-125"}'}]}, "PROJ-125"),
    ({"content": [{"type": "text", "text": '{"issueKey": "PROJ-126"}'}]}, "PROJ-126"),
    ({"content": [{"type": "text", "text": "Created proj-127 successfully"}]}, "PROJ-127"),
    ({"structuredContent": None, "content": [
        {"type": "image", "data": "ignored"},
        {"type": "text", "text": "not JSON and no issue key"},
        {"type": "text", "text": "[]"},
        {"type": "text", "text": "Created PROJ-128"},
    ]}, "PROJ-128"),
])
def test_extract_issue_key_from_supported_response_formats(payload, expected):
    result = service.extract_jira_id_return_response(payload, "PROJ", "https://example.atlassian.net/")
    assert result.success is True
    assert result.jira_id == expected
    assert result.jira_url == f"https://example.atlassian.net/browse/{expected}"


def test_structured_key_takes_precedence_over_text():
    result = service.extract_jira_id_return_response({
        "structuredContent": {"key": "PROJ-123", "issueKey": "PROJ-124"},
        "content": [{"type": "text", "text": "Created PROJ-125"}],
    }, "PROJ", "https://example.atlassian.net")
    assert result.jira_id == "PROJ-123"


@pytest.mark.parametrize("payload", [
    {},
    {"structuredContent": {}},
    {"content": []},
    {"content": [{"type": "image", "data": "PROJ-123"}]},
    {"content": [{"type": "text", "text": "Created OTHER-123"}]},
    {"content": [{"type": "text", "text": "Created XPROJ-123"}]},
    {"content": [{"type": "text", "text": "null"}]},
])
def test_extract_missing_or_unrelated_issue_key_returns_502(payload):
    with pytest.raises(HTTPException) as raised:
        service.extract_jira_id_return_response(payload, "PROJ", "https://example.atlassian.net")
    assert raised.value.status_code == 502
    assert "Jira may already have created the issue" in raised.value.detail
    assert "Check Jira before retrying" in raised.value.detail
