
import logging

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.config import get_settings

logger = logging.getLogger(__name__)


class GitHubMCPError(Exception):
    """Error communicating with GitHub MCP."""


async def call_github_mcp_tool(
        tool_name: str,
        arguments: dict,
) -> dict:

    settings = get_settings()

    headers = {
        "Authorization": f"Bearer {settings.github_token}",
    }

    try:
        async with httpx.AsyncClient(
                headers=headers,
                timeout=httpx.Timeout(60.0, read=300.0),
                follow_redirects=True,
        ) as http_client:

            async with streamable_http_client(
                    settings.github_mcp_url,
                    http_client=http_client,
            ) as (read, write):

                async with ClientSession(read, write) as session:
                    await session.initialize()

                    result = await session.call_tool(
                        tool_name,
                        arguments=arguments,
                    )

                    if result.is_error:
                        error_message = "GitHub MCP tool execution failed"

                        for block in result.content:
                            if getattr(block, "type", None) == "text":
                                error_message = block.text
                                break

                        raise GitHubMCPError(error_message)

                    return result.model_dump(
                        mode="json",
                        by_alias=True,
                        exclude_none=True,
                    )

    except GitHubMCPError:
        raise

    except BaseExceptionGroup as exc:
        logger.error(
            "GitHub MCP connection failed: %s",
            exc,
        )
        raise

    except httpx.TimeoutException as exc:
        logger.error("GitHub MCP timeout: %s", exc)
        raise GitHubMCPError(
            "GitHub MCP request timed out"
        ) from exc

    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code

        logger.error(
            "GitHub MCP HTTP error: %s",
            status_code,
        )

        if status_code == 401:
            message = "GitHub authentication failed"
        elif status_code == 403:
            message = "GitHub access denied: check token permissions"
        elif status_code == 404:
            message = "GitHub MCP endpoint not found"
        elif status_code == 429:
            message = "GitHub rate limit exceeded"
        else:
            message = f"GitHub MCP HTTP error: {status_code}"

        raise GitHubMCPError(message) from exc

    except httpx.RequestError as exc:
        logger.error("GitHub MCP network error: %s", exc)
        raise GitHubMCPError(
            "Unable to connect to GitHub MCP"
        ) from exc

    except Exception as exc:
        logger.exception(
            "Unexpected GitHub MCP error calling %s",
            tool_name,
        )
        raise GitHubMCPError(
            "Unexpected GitHub MCP error"
        ) from exc
