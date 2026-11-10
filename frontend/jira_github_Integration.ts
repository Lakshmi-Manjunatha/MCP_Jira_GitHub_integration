
async function initializeApp(): Promise<void> {
  try {
    await ConfigService.load();

    console.log("Frontend configuration loaded");

    const attachmentManager = new JiraAttachmentManager();
    const githubController = new GitHubFormController();

    const jiraController = new JiraFormController(
        attachmentManager,
        (jiraId: string) => githubController.setJiraId(jiraId)
    );

    attachmentManager.initialize();
    githubController.initialize();
    jiraController.initialize();

    console.log("Application initialized successfully");

  } catch (error) {
    console.error("Application initialization failed:", error);
    alert("Unable to initialize application.");
  }
}

document.addEventListener("DOMContentLoaded", () => {
  void initializeApp();
});
