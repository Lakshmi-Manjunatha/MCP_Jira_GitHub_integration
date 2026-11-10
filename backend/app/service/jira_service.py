from app.model.models import (
    ClassifyRequest,
    ClassifyResponse,
    JiraRequest,
    JiraResponse,
    IssueType,
)

from app.model.models import IssueType


def classify_jira_issue_type(request : ClassifyRequest) -> ClassifyResponse:
    if request.issue_type == IssueType.AUTO:
        return ClassifyResponse(
            issue_type=IssueType.TASK,
            source="LLM"
        )
    return ClassifyResponse(
        issue_type=request.issue_type,
        source="manual"
    )

async def create_jira_issue(request: JiraRequest) -> JiraResponse :
    return JiraResponse
