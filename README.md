# MCP Jira + GitHub Integration

A frontend prototype for a planned MCP (Model Context Protocol) workflow that turns requirements into Jira issues and uses existing Jira issues to guide development and draft GitHub pull requests.

The current application is a static HTML/CSS interface with TypeScript-based client-side validation. It does not connect to Jira, GitHub, an AI service, or an MCP server. The `backend/` directory is currently empty.

## Current functionality

- Jira issue inputs for project key, summary, issue type, parent issue, description, acceptance criteria, and attachments.
- Development inputs for Jira issue ID, GitHub repository URL, base branch (default: `main`), and additional instructions, with a draft PR checkbox.
- Jira ID format validation that enables the development fields and button when the input matches the expected pattern.
- Inline validation messages, an `aria-invalid` state, and a responsive two-column layout.

Validation trims whitespace and checks an uppercase copy of the input against `^[A-Z][A-Z0-9_]*-[1-9][0-9]*$`. For example, `PROJ-123` and ` proj-123 ` enable the development controls; `PROJ-0` and `123` do not. The displayed input is not rewritten, and matching the pattern does not verify that an issue exists.

The action buttons have no click handlers. Selecting attachments does not upload them, and form values are not saved or submitted.



## Run locally

Prerequisites: Node.js with npm to compile TypeScript, Python 3 to run the static server, and a modern browser. No service credentials are needed for this prototype.

From the repository root, run these commands in PowerShell:

```powershell
cd frontend
npm.cmd ci
npx.cmd tsc
py -m http.server 5500 --bind 127.0.0.1
```

Open [the local prototype](http://localhost:5500/jira-github-workspace.html). Keep the server terminal open; press `Ctrl+C` to stop it.

If the Python launcher `py` is unavailable, use `python -m http.server 5500 --bind 127.0.0.1` with a Python 3 installation. On platforms where npm runs directly, use `npm ci` and `npx tsc`.


