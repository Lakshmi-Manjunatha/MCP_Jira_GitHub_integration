import re
import json
import logging

import json
import httpx
from urllib.parse import urlparse

from fastapi import HTTPException, UploadFile

from app.config import get_settings
from app.integration.jira_mcp_client import call_jira_mcp_tool
from app.model.models import (
    ClassifyRequest,
    ClassifyResponse,
    JiraRequest,
    JiraResponse,
    IssueType,
    JiraIssueDetails
)
logger = logging.getLogger(__name__)

settings = get_settings()

def classify_jira_issue_type(request : ClassifyRequest) -> ClassifyResponse:
    if request.issue_type == IssueType.AUTO:
        return ClassifyResponse(
            issue_type=IssueType.STORY,
            source="LLM"
        )
    return ClassifyResponse(
        issue_type=request.issue_type,
        source="manual"
    )

async def create_jira(request: JiraRequest, attachments: list[UploadFile] | None = None) \
        -> JiraResponse :
    if request.issue_type == IssueType.AUTO:
        raise HTTPException(
            status_code=400,
            detail="Confirm issue type before creating Jira"
        )

    if request.issue_type == IssueType.SUBTASK:
        if not request.parent_jira_id:
            raise HTTPException(
                status_code=400,
                detail="Parent Jira ID is required for subtask"
        )

    description = request.description

    if request.acceptance_criteria:
        description += (
                "\n\n## Acceptance Criteria\n"
                + request.acceptance_criteria
        )

    arguments = {
        "cloudId": settings.atlassian_cloud_id,
        "projectKey": request.jira_project_key,
        "summary": request.summary,
        "issueType": request.issue_type.value.capitalize(),
        "description": description,
        "contentFormat": "markdown",
    }

    if request.issue_type == IssueType.SUBTASK:
        arguments["parent"] = request.parent_jira_id

    logger.info(
        "Creating Jira issue. Project: %s, Type: %s",
        request.jira_project_key,
        request.issue_type.value
    )

    result = await call_jira_mcp_tool(
        "createJiraIssue",
        arguments
    )

    return extract_jira_id_return_response(result,
                                           request.jira_project_key,
                                           settings.atlassian_cloud_id)

def extract_jira_id_return_response(result : dict,
                                    project_key: str,
                                    cloud_id: str)-> JiraResponse :

    structured = result.get("structuredContent") or {}

    jira_id = (
            structured.get("key")
            or structured.get("issueKey")
    )

    if not jira_id:
        for item in result.get("content", []):
            if item.get("type") != "text":
                continue

            text = item.get("text", "")

            # First try to parse JSON returned by MCP
            try:
                data = json.loads(text)

                if isinstance(data, dict):
                    jira_id = (
                            data.get("key")
                            or data.get("issueKey")
                    )
            except json.JSONDecodeError:
                pass

            # Fallback: find a Jira key in plain text
            if not jira_id:
                match = re.search(
                    rf"\b{re.escape(project_key)}-\d+\b",
                    text,
                    flags=re.IGNORECASE
                )

                if match:
                    jira_id = match.group(0).upper()

            if jira_id:
                break

    if not jira_id:
        logger.error(
            "Jira creation returned no recognizable issue key"
        )
        raise HTTPException(
            status_code=502,
            detail=(
                "Jira may already have created the issue, "
                "but its response could not be parsed. "
                "Check Jira before retrying."
            )
        )

    logger.info("Jira issue created: %s", jira_id)

    return JiraResponse(
        success=True,
        jira_id=jira_id,
        jira_url=f"{cloud_id.rstrip('/')}/browse/{jira_id}"
    )


async def get_jira_issue(jira_id: str) -> JiraIssueDetails:

    result = await call_jira_mcp_tool(
        tool_name="getJiraIssue",
        arguments={
            "cloudId": settings.atlassian_cloud_id,
            "issueIdOrKey": jira_id,
            "fields": [
                "summary",
                "description",
                "attachment",
                "subtasks",
                "project"
            ],
            "fieldsByKeys": True
        },
    )

    for block in result.get("content", []):
        if block.get("type") != "text":
            continue

        payload = json.loads(block["text"])
        issue = payload.get("data", {})
        fields = issue.get("fields") or {}

        return JiraIssueDetails(
            jira_id=issue["id"],
            issue_key=issue["key"],
            project_key=(fields.get("project") or {}).get("key"),
            summary=fields.get("summary"),
            description=fields.get("description"),
            attachment_ids=[
                str(a["id"])
                for a in fields.get("attachment", [])
                if a.get("id")
            ],
            subtasks=[
                {
                    "id": str(s["id"]),
                    "key": s["key"]
                }
                for s in fields.get("subtasks", [])
                if s.get("id") and s.get("key")
            ]
        )

    raise ValueError("No Jira issue data returned")


async def get_attachment_download_info(
        attachment_id: str,
) -> dict:
    settings = get_settings()

    return await call_jira_mcp_tool(
        tool_name="executeRead",
        arguments={
            "name": "downloadJiraIssueAttachment",
            "cloudId": settings.atlassian_cloud_id,
            "inputs": {
                "attachmentId": attachment_id,
            },
        },
    )

def extract_download_url(mcp_result: dict) -> str:
    for block in mcp_result.get("content", []):
        if block.get("type") != "text":
            continue

        payload = json.loads(block["text"])

        data = payload.get("data", payload)

        if isinstance(data, dict):
            url = data.get("downloadUrl")
            if isinstance(url, str) and url:
                return url

    raise ValueError(
        "MCP response does not contain downloadUrl"
    )


async def download_attachment_text(
        attachment_id: str,
) -> str:
    # Reuse the function we implemented earlier.
    mcp_result = await get_attachment_download_info(
        attachment_id
    )

    download_url = extract_download_url(mcp_result)

    parsed = urlparse(download_url)

    if (
            parsed.scheme != "https"
            or parsed.hostname != "api.media.atlassian.com"
            or parsed.username is not None
            or parsed.password is not None
    ):
        raise ValueError(
            "Unexpected attachment download URL"
        )

    async with httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=False,
    ) as client:
        async with client.stream(
                "GET",
                download_url,
        ) as response:
            response.raise_for_status()

            chunks = []
            total_size = 0
            max_size = 1024 * 1024  # 1 MB

            async for chunk in response.aiter_bytes():
                total_size += len(chunk)

                if total_size > max_size:
                    raise ValueError(
                        "Attachment exceeds 1 MB"
                    )

                chunks.append(chunk)

    return b"".join(chunks).decode("utf-8")