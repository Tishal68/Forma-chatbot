# Security notes

Forma is a student project. Automated tests and code review are not a security certification.

## Current protections

- Signed visitor cookies and ownership checks separate conversations, attachments and memories.
- Browser mutations require the CSRF cookie/header pair and pass the configured origin checks. Non-browser API clients without browser metadata remain supported.
- Python execution is disabled on the server and absent from Agent Mode's tool registry.
- The GitHub tool reads public repositories without server credentials, rejects traversal paths and does not follow redirects.
- Upload reads are bounded by the configured file limit. DOCX document XML is limited to 8 MiB after decompression; DTDs are rejected regardless of XML encoding.
- Deleting a conversation removes its tool audit records. Clearing session data also removes that visitor's orphaned audit records.
- Backend tests block socket connections and use mock provider transports.

## Deployment responsibilities and remaining limits

- Use HTTPS, a stable private session secret, persistent storage and explicit allowed origins.
- Add reverse-proxy request-body limits: the endpoint's bounded file read does not stop multipart data from being spooled before the handler runs.
- PDF parsing is not isolated in a separate process. Untrusted document processing needs CPU, memory and execution-time limits at the deployment layer.
- Rate limits are process-local and anonymous session limits can be reset by starting a new session. Use shared gateway limits and provider spending caps for a public deployment.
- Cloud providers receive submitted prompts and context. Keep sensitive files and credentials out of chat.
- If a broad GitHub token was configured on a publicly accessible older release, review its access logs and revoke or rotate it. The public inspection tool no longer uses it.
- Keep dependencies updated. The 2026-10-09 review checked frontend production dependencies with npm audit and selected credential patterns in tracked files; it was not a complete historical secret scan, Python advisory audit or live penetration test.

Report suspected vulnerabilities privately to the repository owner. Do not publish credentials or other users' data in issues.
