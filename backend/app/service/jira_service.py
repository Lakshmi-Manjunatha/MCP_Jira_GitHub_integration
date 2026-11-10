import re
import json
import logging

from fastapi import HTTPException, UploadFile

from app.config import get_settings
from app.integration.jira_mcp_client import call_jira_mcp_tool

from app.model.models import (
    ClassifyRequest,
    ClassifyResponse,
    JiraRequest,
    JiraResponse,
    IssueType,
)

from app.model.models import IssueType

logger = logging.getLogger(__name__)

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

    settings = get_settings()

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