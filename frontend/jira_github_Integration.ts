// Client-side format validation only. Real Jira issue existence is checked later via MCP.
const jiraInput = document.querySelector<HTMLInputElement>('#jiraid');
const developmentFields = document.querySelector<HTMLFieldSetElement>('#development-fields');
const developmentButton = document.querySelector<HTMLButtonElement>('#develop-button');
const jiraValidation = document.querySelector<HTMLElement>('#jira-validation');

function updateDevelopmentAccess(): void {
  if (!jiraInput || !developmentFields || !developmentButton || !jiraValidation) return;
  const issueId = jiraInput.value.trim().toUpperCase();
  const validFormat = /^[A-Z][A-Z0-9_]*-[1-9][0-9]*$/.test(issueId);
  developmentFields.disabled = !validFormat;
  developmentButton.disabled = !validFormat;
  jiraInput.setAttribute('aria-invalid', String(jiraInput.value.trim().length > 0 && !validFormat));
  if (!jiraInput.value.trim()) {
    jiraValidation.textContent = 'Enter a Jira issue ID to enable the GitHub fields.';
  } else if (!validFormat) {
    jiraValidation.textContent = 'Invalid format. Example: PROJ-123';
  } else {
    jiraValidation.textContent = 'Valid Jira ID format. GitHub fields are enabled. Issue existence will be verified after MCP integration.';
  }
}

jiraInput?.addEventListener('input', updateDevelopmentAccess);
updateDevelopmentAccess();
