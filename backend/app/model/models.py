from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator

class IssueType(str, Enum):
    AUTO = "auto"
    STORY = "story"
    BUG = "bug"
    TASK = "task"
    SUBTASK = "subtask"

class JiraResponse(BaseModel):
    success: bool
    jira_id: Annotated[
        str,
        Field(min_length=2, max_length=20)
    ]
    jira_url: str | None = None

class JiraRequest(BaseModel):
    summary: Annotated[str, Field(min_length=3, max_length=255)]
    description: Annotated[str, Field(min_length=3)]

    issue_type: IssueType

    jira_project_key: Annotated[
        str,
        Field(min_length=2, max_length=20)
    ]

    parent_jira_id: str | None = None

    acceptance_criteria: str | None = None

    @field_validator("jira_project_key")
    @classmethod
    def validate_project_key(cls, value: str) -> str:
        value = value.strip().upper()

        if not value.isalnum() or not value[0].isalpha():
            raise ValueError(
                "Jira project key must contain letters/numbers "
                "and start with a letter"
            )

        return value

    @model_validator(mode="after")
    def validate_issue(self):
        if self.issue_type == IssueType.AUTO:
            raise ValueError(
                "Issue type must be reviewed before Jira creation"
            )

        if (
                self.issue_type == IssueType.SUBTASK
                and not self.parent_jira_id
        ):
            raise ValueError(
                "Parent Jira ID is required for a subtask"
            )

        return self

class ClassifyResponse(BaseModel):
    issue_type: IssueType
    source: str

class ClassifyRequest(BaseModel):
    summary: Annotated[str, Field(min_length=3, max_length=255)]
    description: Annotated[str, Field(min_length=3)]
    issue_type: IssueType

class CodeGenerationRequest(BaseModel):
    jira_id: Annotated[str, Field(min_length=5, max_length=10)]
    repository_url: Annotated[str, Field(min_length=12, max_length=100)]
    base_branch:Annotated[str, Field(default="main", min_length=4, max_length=50)]
    additional_instructions: str

class CodeGenerationResponse(BaseModel):
    pr_url: str
    success: bool

class JiraSubtask(BaseModel):
    id: str
    key: str


class JiraIssueDetails(BaseModel):
    jira_id: str
    issue_key: str
    project_key: str | None = None
    summary: str | None = None
    description: str | None = None
    attachment_ids: list[str] = Field(default_factory=list)
    subtasks: list[JiraSubtask] = Field(default_factory=list)

