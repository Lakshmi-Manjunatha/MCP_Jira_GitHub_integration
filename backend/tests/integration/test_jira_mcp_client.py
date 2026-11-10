import asyncio
import base64
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from app.integration import jira_mcp_client as client
from app.integration.mcp_exceptions import MCPIntegrationError


@pytest.fixture
def settings(monkeypatch):
    settings = SimpleNamespace(
        atlassian_email="test@example.com",
        atlassian_api_token="fake-token",
        atlassian_mcp_url="https://mcp.example.test/mcp",
    )
    monkeypatch.setattr(client, "get_settings", Mock(return_value=settings))
    return settings


@pytest.fixture
def mcp(monkeypatch, settings):
    """Replace every network boundary with an asynchronous context manager."""
    http = AsyncMock()
    http.__aenter__.return_value = http
    transport = AsyncMock()
    read, write = object(), object()
    transport.__aenter__.return_value = (read, write)
    session = AsyncMock()
    session.__aenter__.return_value = session
    result = Mock()
    result.model_dump.return_value = {"structuredContent": {"key": "PROJ-123"}}
    session.call_tool.return_value = result
    http_factory = Mock(return_value=http)
    transport_factory = Mock(return_value=transport)
    session_factory = Mock(return_value=session)
    monkeypatch.setattr(client.httpx, "AsyncClient", http_factory)
    monkeypatch.setattr(client, "streamable_http_client", transport_factory)
    monkeypatch.setattr(client, "ClientSession", session_factory)
    return SimpleNamespace(
        http=http, transport=transport, session=session, result=result,
        http_factory=http_factory, transport_factory=transport_factory,
        session_factory=session_factory, read=read, write=write,
    )


def invoke():
    return asyncio.run(client.call_jira_mcp_tool("createJiraIssue", {"summary": "Test issue"}))


def assert_closed(mcp):
    mcp.session.__aexit__.assert_awaited_once()
    mcp.transport.__aexit__.assert_awaited_once()
    mcp.http.__aexit__.assert_awaited_once()


def http_error(status):
    request = httpx.Request("POST", "https://mcp.example.test/mcp")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError("private upstream detail", request=request, response=response)


def test_build_auth_headers(settings):
    headers = client.build_auth_headers()
    scheme, token = headers["Authorization"].split(" ", 1)
    assert scheme == "Basic"
    assert base64.b64decode(token).decode("utf-8") == "test@example.com:fake-token"
    assert set(headers) == {"Authorization"}


def test_tool_success_initializes_session_and_forwards_arguments(mcp, settings):
    assert invoke() == {"structuredContent": {"key": "PROJ-123"}}
    mcp.session.initialize.assert_awaited_once_with()
    mcp.session.call_tool.assert_awaited_once_with(
        "createJiraIssue", arguments={"summary": "Test issue"},
    )
    mcp.result.model_dump.assert_called_once_with(mode="json", by_alias=True, exclude_none=True)
    mcp.transport_factory.assert_called_once_with(settings.atlassian_mcp_url, http_client=mcp.http)
    mcp.session_factory.assert_called_once_with(mcp.read, mcp.write)
    options = mcp.http_factory.call_args.kwargs
    assert options["headers"] == client.build_auth_headers()
    assert options["follow_redirects"] is True
    assert options["timeout"].connect == 60.0
    assert options["timeout"].read == 300.0
    assert_closed(mcp)


@pytest.mark.parametrize("status,message", [
    (400, "Invalid Jira MCP request"),
    (401, "Atlassian authentication failed. Check your API token"),
    (403, "Atlassian access denied. Check token scopes and permissions"),
    (404, "Requested Atlassian resource was not found"),
    (429, "Atlassian rate limit exceeded. Try again later"),
    (500, "Atlassian MCP operation failed"),
])
def test_tool_error_maps_status_without_exposing_upstream_details(mcp, status, message):
    mcp.result.model_dump.return_value = {
        "isError": True,
        "content": [{"type": "text", "text": json.dumps({
            "statusCode": status, "message": "secret upstream detail",
        })}],
    }
    with pytest.raises(MCPIntegrationError) as raised:
        invoke()
    assert raised.value.status_code == (status if status != 500 else 502)
    assert str(raised.value) == message
    assert_closed(mcp)


@pytest.mark.parametrize("content", [
    [],
    [{"type": "image", "data": "ignored"}],
    [{"type": "text", "text": "not JSON"}],
    [{"type": "text", "text": "[]"}],
    [{"type": "text", "text": None}],
    [{"type": "text", "text": "{}"}],
])
def test_unusable_tool_error_returns_safe_default(content):
    error = client.extract_mcp_error({"content": content})
    assert error.status_code == 502
    assert str(error) == "Atlassian MCP operation failed"


def test_error_parser_skips_invalid_content_before_valid_error():
    error = client.extract_mcp_error({"content": [
        {"type": "text", "text": "not JSON"},
        {"type": "text", "text": "[]"},
        {"type": "text", "text": '{"statusCode": 401}'},
    ]})
    assert error.status_code == 401


@pytest.mark.parametrize("status,expected", [(401, 401), (403, 403), (429, 429), (404, 502), (500, 502)])
def test_http_failure_is_mapped_and_preserves_cause(mcp, status, expected):
    original = http_error(status)
    mcp.session.call_tool.side_effect = original
    with pytest.raises(MCPIntegrationError) as raised:
        invoke()
    assert raised.value.status_code == expected
    assert raised.value.__cause__ is original
    assert "private upstream detail" not in str(raised.value)
    assert_closed(mcp)


@pytest.mark.parametrize("stage", ["initialize", "call_tool"])
def test_timeout_inside_nested_exception_group(mcp, stage):
    original = ExceptionGroup("outer", [ValueError("other"), ExceptionGroup(
        "inner", [httpx.ReadTimeout("private timeout detail")],
    )])
    getattr(mcp.session, stage).side_effect = original
    with pytest.raises(MCPIntegrationError) as raised:
        invoke()
    assert raised.value.status_code == 504
    assert "Check Jira before retrying" in str(raised.value)
    assert raised.value.__cause__ is original
    if stage == "initialize":
        mcp.session.call_tool.assert_not_awaited()
    assert_closed(mcp)


@pytest.mark.parametrize("original", [httpx.ConnectError("private connection detail"), RuntimeError("private error")])
def test_unexpected_connection_failure_is_sanitized(mcp, original):
    mcp.session.call_tool.side_effect = original
    with pytest.raises(MCPIntegrationError) as raised:
        invoke()
    assert raised.value.status_code == 502
    assert str(raised.value) == "Unable to communicate with Atlassian MCP"
    assert_closed(mcp)


def test_transport_entry_failure_closes_http_client(mcp):
    mcp.transport.__aenter__.side_effect = httpx.ConnectError("connection failed")
    with pytest.raises(MCPIntegrationError) as raised:
        invoke()
    assert raised.value.status_code == 502
    mcp.session_factory.assert_not_called()
    mcp.http.__aexit__.assert_awaited_once()


def test_context_exit_failure_is_reported_even_after_tool_success(mcp):
    mcp.transport.__aexit__.side_effect = httpx.ReadTimeout("close timed out")
    with pytest.raises(MCPIntegrationError) as raised:
        invoke()
    assert raised.value.status_code == 504
    mcp.session.call_tool.assert_awaited_once()
    assert_closed(mcp)


def test_missing_payload_is_rejected(mcp):
    mcp.result.model_dump.return_value = None
    with pytest.raises(MCPIntegrationError, match="Atlassian MCP returned no response") as raised:
        invoke()
    assert raised.value.status_code == 502
    assert_closed(mcp)


def test_find_http_error_searches_nested_groups():
    target = http_error(403)
    group = ExceptionGroup("outer", [ValueError("ignored"), ExceptionGroup("inner", [target])])
    assert client.find_http_error(group) is target
    assert client.find_http_error(target) is target
    assert client.find_http_error(ValueError("no HTTP error")) is None
