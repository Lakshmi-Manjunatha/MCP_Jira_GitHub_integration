import logging
from typing import Annotated

from fastapi import APIRouter,File,Form,Body, HTTPException,UploadFile, Request
from app.model.models import( ClassifyResponse, ClassifyRequest,
                              JiraRequest, JiraResponse,
                              IssueType,)


from app.service.jira_service import (create_jira,
                                      classify_jira_issue_type,)

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
