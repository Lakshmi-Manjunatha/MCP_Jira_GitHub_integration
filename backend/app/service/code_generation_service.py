import logging

from app.model.models import CodeGenerationRequest, CodeGenerationResponse, JiraIssueDetails
from app.service.jira_service import (get_jira_issue, download_attachment_text)
from app.service.github_service import create_feature_branch, create_github_pull_request


async def execute_code_generate_raise_pr(request : CodeGenerationRequest) -> CodeGenerationResponse :

    # Retrieve Jira details by Jira Id
    jira_issue_details = await get_jira_issue(request.jira_id)

    # Retrieve content of attchments.
    await get_contents(jira_issue_details.attachment_ids)



    # create branch.
    await create_branch(request)
    # raise PR
    pr_title = get_pr_title(jira_issue_details.issue_key, jira_issue_details.summary)
    await create_pull_request(request, pr_title)

    return CodeGenerationResponse (
        pr_url="url",
        success=True
    )

async def get_contents(attachment_ids : list[str]) -> dict[str, str]:
    contents = {}
    for attachment_id in  attachment_ids:
        content = await download_attachment_text(attachment_id)
        contents[attachment_id] = content

    return contents

async def create_branch(request : CodeGenerationRequest) -> str :
    branch_name = f"feature/{request.jira_id}"
    branch_details = await create_feature_branch(branch_name, request.base_branch, request.repository_url)

async def create_pull_request(request : CodeGenerationRequest, pr_title :str) -> str :
    branch_name = f"feature/{request.jira_id}"
    branch_details = await create_github_pull_request(request.repository_url,request.base_branch,
                                                      branch_name, pr_title, pr_title)

def get_pr_title(issue_key : str, summary: str) -> str :
   return f""" {issue_key}
                {summary}
                AI-generated changes. Please review before merging.
           """