
import base64
import json
import logging

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.config import get_settings
from app.integration.mcp_exceptions import MCPIntegrationError

logger = logging.getLogger(__name__)


def build_auth_headers() -> dict[str, str]:
    settings = get_settings()

    credentials = (
        f"{settings.atlassian_email}:"
        f"{settings.atlassian_api_token}"
    )

    encoded = base64.b64encode(
        credentials.encode("utf-8")
    ).decode("ascii")

    return {
        "Authorization": f"Basic {encoded}"
    }


def extract_mcp_error(payload: dict) -> MCPIntegrationError:
    message = "Atlassian MCP operation failed"
    status_code = 502

    for item in payload.get("content", []):
        if item.get("type") != "text":
            continue

        try:
            data = json.loads(item.get("text", ""))

            if not isinstance(data, dict):
                continue

            upstream_status = data.get("statusCode")

            if upstream_status in (400, 401, 403, 404, 429):
                status_code = upstream_status

            # Avoid exposing arbitrary upstream error details.
            messages = {
                400: "Invalid Jira MCP request",
                401: "Atlassian authentication failed. Check your API token",
                403: "Atlassian access denied. Check token scopes and permissions",
                404: "Requested Atlassian resource was not found",
                429: "Atlassian rate limit exceeded. Try again later",
            }

            message = messages.get(
                status_code,
                "Atlassian MCP operation failed",
            )

            break

        except (json.JSONDecodeError, TypeError, ValueError):
            continue

    return MCPIntegrationError(message, status_code)


def find_http_error(exc: BaseException):
    """Find HTTP errors inside MCP/AnyIO ExceptionGroups."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc

    if isinstance(exc, httpx.RequestError):
        return exc

    if isinstance(exc, BaseExceptionGroup):
        for child in exc.exceptions:
            found = find_http_error(child)
            if found:
                return found

    return None


def map_connection_error(exc: BaseException) -> MCPIntegrationError:
    http_error = find_http_error(exc)

    if isinstance(http_error, httpx.TimeoutException):
        return MCPIntegrationError(
            "Atlassian MCP request timed out. "
            "Check Jira before retrying a create operation",
            504,
        )

    if isinstance(http_error, httpx.HTTPStatusError):
        upstream_status = http_error.response.status_code

        if upstream_status == 401:
            return MCPIntegrationError(
                "Atlassian authentication failed. Check your API token",
                401,
            )

        if upstream_status == 403:
            return MCPIntegrationError(
                "Atlassian access denied. Check token scopes and permissions",
                403,
            )

        if upstream_status == 429:
            return MCPIntegrationError(
                "Atlassian rate limit exceeded. Try again later",
                429,
            )

        return MCPIntegrationError(
            "Atlassian MCP returned an HTTP error",
            502,
        )

    return MCPIntegrationError(
        "Unable to communicate with Atlassian MCP",
        502,
    )


async def call_jira_mcp_tool(
        tool_name: str,
        arguments: dict,
) -> dict:

    settings = get_settings()
    payload = None
    connection_error = None

    try:
        async with httpx.AsyncClient(
                headers=build_auth_headers(),
                timeout=httpx.Timeout(60.0, read=300.0),
                follow_redirects=True,
        ) as http_client:

            async with streamable_http_client(
                    settings.atlassian_mcp_url,
                    http_client=http_client,
            ) as (read, write):

                async with ClientSession(read, write) as session:
                    await session.initialize()

                    logger.info(
                        "Calling Jira MCP tool: %s",
                        tool_name,
                    )

                    result = await session.call_tool(
                        tool_name,
                        arguments=arguments,
                    )

                    payload = result.model_dump(
                        mode="json",
                        by_alias=True,
                        exclude_none=True,
                    )

    except Exception as exc:
        connection_error = exc

    # Handle errors after MCP context managers close.
    if connection_error is not None:
        mapped_error = map_connection_error(connection_error)

        logger.error(
            "MCP connection failed. Tool=%s Status=%s",
            tool_name,
            mapped_error.status_code,
        )

        raise mapped_error from connection_error

    if payload is None:
        raise MCPIntegrationError(
            "Atlassian MCP returned no response",
            502,
        )

    if payload.get("isError"):
        error = extract_mcp_error(payload)

        logger.warning(
            "MCP tool failed. Tool=%s Status=%s",
            tool_name,
            error.status_code,
        )

        raise error

    return payload
