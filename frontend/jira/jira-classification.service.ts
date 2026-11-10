
type IssueType = "auto" | "story" | "bug" | "task" | "subtask";

interface ClassifyResponse {
    issue_type: IssueType;
}

class JiraClassificationService {

    static async classify(
        summary: string,
        description: string
    ): Promise<IssueType> {

        const response = await fetch(
            `${ConfigService.apiBaseUrl}/jira/classify`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    summary,
                    description,
                    issue_type: "auto"
                })
            }
        );

        if (!response.ok) {
            throw new Error(
                `Issue classification failed: HTTP ${response.status}`
            );
        }

        const result: ClassifyResponse = await response.json();
        const classifiedType = String(result.issue_type)
            .trim()
            .toLowerCase() as IssueType;
        const validTypes: IssueType[] = [
            "story", "bug", "task", "subtask"
        ];

        if (!validTypes.includes(classifiedType)) {
            throw new Error("Invalid issue type returned by backend");
        }

        return classifiedType;
    }
}
