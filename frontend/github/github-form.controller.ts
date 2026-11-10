
class GitHubFormController {
    initialize(): void {
        const jiraInput = document.querySelector<HTMLInputElement>("#jiraid");

        jiraInput?.addEventListener("input", () => {
            this.updateDevelopmentAccess();
        });

        this.updateDevelopmentAccess();
    }

    setJiraId(jiraId: string): void {
        const jiraInput = document.querySelector<HTMLInputElement>("#jiraid");

        if (jiraInput) {
            jiraInput.value = jiraId;
            this.updateDevelopmentAccess();
        }
    }

    private updateDevelopmentAccess(): void {
        const jiraInput = document.querySelector<HTMLInputElement>("#jiraid");
        const fields = document.querySelector<HTMLFieldSetElement>("#development-fields");
        const button = document.querySelector<HTMLButtonElement>("#develop-button");
        const validation = document.querySelector<HTMLElement>("#jira-validation");

        if (!jiraInput || !fields || !button || !validation) return;

        const issueId = jiraInput.value.trim().toUpperCase();
        const validFormat = /^[A-Z][A-Z0-9_]*-[1-9][0-9]*$/.test(issueId);

        fields.disabled = !validFormat;
        button.disabled = !validFormat;

        jiraInput.setAttribute(
            "aria-invalid",
            String(jiraInput.value.trim().length > 0 && !validFormat)
        );

        if (!jiraInput.value.trim()) {
            validation.textContent = "Enter a Jira issue ID to enable the GitHub fields.";
        } else if (!validFormat) {
            validation.textContent = "Invalid format. Example: DEMO-123";
        } else {
            validation.textContent =
                "Valid Jira ID format. GitHub fields are enabled. " +
                "Issue existence has not yet been verified.";
        }
    }
}
