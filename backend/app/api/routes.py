import logging
from typing import Annotated

from fastapi import APIRouter,File,Form,Body, HTTPException,UploadFile, Request
from app.model.models import( ClassifyResponse, ClassifyRequest,
                              JiraRequest, JiraResponse,
                              IssueType, CodeGenerationRequest, CodeGenerationResponse)


from app.service.jira_service import (create_jira,
                                      classify_jira_issue_type,)
from app.service.code_generation_service import (execute_code_generate_raise_pr,)


router = APIRouter(prefix="/api/v1",  tags=["Jira"])
logger = logging.getLogger(__name__)


@router.get("/health")
def health():
    logger.info("Health check requested")
    return {"status": "service is up"}


@router.post(
    "/jira/classify",
    response_model=ClassifyResponse
)
def classify_jira_issue(request: Annotated[ClassifyRequest, Body()]):
    logger.info(
        "Jira issue classification requested. Issue type: %s",
        request.issue_type.value
    )
    return  classify_jira_issue_type(request)

@router.post(
    "/jira/issues",
    response_model=JiraResponse
)

async def create_jira_issue(
        request: Annotated[JiraRequest, Form()],
        http_request: Request,
):
    logger.info("Jira creation requested. Summary: %s", request.summary)

    form = await http_request.form()
    attachments = [
        value
        for value in form.getlist("attachments")
        if isinstance(value, UploadFile) and value.filename
    ]
    return await create_jira(request, attachments)

@router.post(
    "/code-generations",
    response_model=CodeGenerationResponse
)
async def code_generations(request: Annotated[CodeGenerationRequest, Body()]):
    logger.info(
        "Generate code request raised: %s", request.jira_id
    )
    return await execute_code_generate_raise_pr(request)

from app.service.github_service import get_repository_structure


@router.get("/github/debug/readme")
async def debug_github_readme():
    return await get_repository_structure(
        owner="",
        repo="MCP_Jira_GitHub_integration",
        path="",
    )


# # TO DELETE
# @router.get("/jira/debug/get-issue-schema")
# async def get_issue_schema():
#     return await get_jira_mcp_tool_schema("getJiraIssue")
# # TO DELETE
# @router.get("/jira/debug/issue/{jira_id}")
# async def debug_get_jira_issue(jira_id: str):
#     settings = get_settings()
#
#     result = await call_jira_mcp_tool(
#         tool_name="getJiraIssue",
#         arguments={
#             "cloudId": settings.atlassian_cloud_id,
#             "issueIdOrKey": jira_id,
#         },
#     )
#
#     return result

