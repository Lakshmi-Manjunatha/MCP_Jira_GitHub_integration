import logging


from app.integration.github_mcp_client import call_github_mcp_tool

from app.config import get_settings

settings = get_settings()

async def get_github_file(
        owner: str,
        repo: str,
        path: str,
        ref: str = "refs/heads/main",
) -> dict:

    return await call_github_mcp_tool(
        tool_name="get_file_contents",
        arguments={
            "owner": owner,
            "repo": repo,
            "path": path,
            "ref": ref,
        },
    )

async def get_repository_structure(
        owner: str,
        repo: str,
        path: str = "",
) -> dict:
    return await call_github_mcp_tool(
        tool_name="get_file_contents",
        arguments={
            "owner": owner,
            "repo": repo,
            "path": path,
        },
    )

async def create_feature_branch(branch_name :str, from_branch: str, repo_url: str)\
        -> dict :
    print(branch_name)
    print(repo_url)
    print(from_branch)
    return await call_github_mcp_tool(
        tool_name="create_branch",
        arguments={
            "owner": settings.github_owner,
            "repo": repo_url,
            "branch": branch_name,
            "from_branch": from_branch,
        },
    )


async def create_github_pull_request(
        repo: str,
        head_branch: str,
        base_branch: str,
        title: str,
        body: str,
) -> dict:

    return await call_github_mcp_tool(
        tool_name="create_pull_request",
        arguments={
            "owner": settings.github_owner,
            "repo": repo,
            "head": head_branch,
            "base": base_branch,
            "title": title,
            "body": body,
            "draft": True,
        },
    )



