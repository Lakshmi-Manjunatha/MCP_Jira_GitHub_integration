
class JiraFormController {
    constructor(
        private attachments: JiraAttachmentManager,
        private onIssueCreated: (jiraId: string) => void
    ) {}

    initialize(): void {
        const issueType = document.querySelector<HTMLSelectElement>("#issue-type");
        const createButton = document.querySelector<HTMLButtonElement>("#create-jira-button");

        if (issueType) {
            issueType.value = "task";
            issueType.addEventListener("change", () => {
                void this.classifyIssue(issueType);
            });
        }

        createButton?.addEventListener("click", () => {
            void this.createIssue();
        });
    }

    private value(selector: string): string {
        return (
            document.querySelector<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>(
                selector
            )?.value.trim() ?? ""
        );
    }

    private async classifyIssue(select: HTMLSelectElement): Promise<void> {
        const status = document.querySelector<HTMLElement>("#issue-type-status");

        if (select.value !== "auto") {
            if (status) status.textContent = "";
            return;
        }

        const summary = this.value("#summary");
        const description = this.value("#description");

        if (summary.length < 3 || description.length < 3) {
            select.value = "task";
            if (status) {
                status.textContent = "Enter summary and description (minimum 3 characters).";
            }
            return;
        }

        select.disabled = true;
        if (status) status.textContent = "Classifying issue type...";

        try {
            const result = await JiraClassificationService.classify(
                summary, description
            );

            if (!Array.from(select.options).some(option => option.value === result)) {
                throw new Error(`Unsupported issue type: ${result}`);
            }

            select.value = result;

            if (status) {
                status.textContent = `AI classified this issue as ${result.toUpperCase()}.`;
            }
        } catch (error) {
            console.error("Classification failed:", error);
            select.value = "task";
            if (status) {
                status.textContent = "Unable to classify issue. Defaulted to Task.";
            }
        } finally {
            select.disabled = false;
        }
    }

    private async createIssue(): Promise<void> {
        const button = document.querySelector<HTMLButtonElement>("#create-jira-button");
        const status = document.querySelector<HTMLElement>("#jira-create-status");
        const issueTypeSelect = document.querySelector<HTMLSelectElement>("#issue-type");

        if (!button) return;

        const project = this.value("#project");
        const summary = this.value("#summary");
        const description = this.value("#description");
        const issueType = issueTypeSelect?.value ?? "task";
        const parent = this.value("#parent");
        const criteria = this.value("#criteria");

        if (!project || summary.length < 3 || description.length < 3) {
            if (status) status.textContent = "Enter a project, summary and description.";
            return;
        }

        if (issueType === "auto" || issueTypeSelect?.disabled) {
            if (status) status.textContent = "Wait for issue classification to finish.";
            return;
        }

        if (issueType === "subtask" && !parent) {
            if (status) status.textContent = "Parent Jira ID is required.";
            return;
        }

        button.disabled = true;
        if (status) status.textContent = "Creating Jira issue...";

        try {
            const result = await JiraIssueService.create({
                jira_project_key: project,
                summary,
                description,
                issue_type: issueType,
                parent_jira_id: parent || undefined,
                acceptance_criteria: criteria || undefined,
                attachments: this.attachments.getFiles()
            });

            if (!result.success || !result.jira_id) {
                throw new Error("Jira creation response did not contain an issue ID.");
            }

            if (status) {
                status.textContent = `Jira issue created: ${result.jira_id}`;
            }

            this.onIssueCreated(result.jira_id);
            this.attachments.clear();

        } catch (error) {
            console.error("Jira creation failed:", error);

            if (status) {
                status.textContent = error instanceof Error
                    ? error.message
                    : "Unable to create Jira issue.";
            }
        } finally {
            button.disabled = false;
        }
    }
}
