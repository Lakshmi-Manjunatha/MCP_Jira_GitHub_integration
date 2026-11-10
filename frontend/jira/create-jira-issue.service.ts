
interface JiraCreateRequest {
    summary: string;
    description: string;
    jira_project_key: string;
    issue_type: string;
    parent_jira_id?: string;
    acceptance_criteria?: string;
    attachments: File[];
}

interface JiraCreateResponse {
    success: boolean;
    jira_id: string;
    jira_url?: string | null;
    attachments_uploaded?: boolean;
    attachment_count?: number;
}

class JiraIssueService {
    static async create(
        request: JiraCreateRequest
    ): Promise<JiraCreateResponse> {

        const formData = new FormData();

        formData.append("summary", request.summary);
        formData.append("description", request.description);
        formData.append("jira_project_key", request.jira_project_key);
        formData.append("issue_type", request.issue_type);

        if (request.parent_jira_id) {
            formData.append("parent_jira_id", request.parent_jira_id);
        }

        if (request.acceptance_criteria) {
            formData.append("acceptance_criteria", request.acceptance_criteria);
        }

        request.attachments.forEach(file => {
            formData.append("attachments", file);
        });

        const response = await fetch(
            `${ConfigService.apiBaseUrl}/jira/issues`,
            {
                method: "POST",
                body: formData
            }
        );

        const result = await response.json();

        if (!response.ok) {
            throw new Error(
                result.error ?? JSON.stringify(result.detail ?? "Jira creation failed")
            );
        }

        return result as JiraCreateResponse;
    }
}
