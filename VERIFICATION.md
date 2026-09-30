# Verification — 29 September 2026

## Deployment preparation — 30 September 2026

- Eight backend tests passed, including production password requirements, credential checking, protected routes, database health and Render/Railway/custom-domain origins.
- Added Docker, Render and Railway configuration plus Linux container smoke tests in GitHub Actions.
- Docker is not installed on the development computer. Container build/runtime verification is delegated to the repository CI; no claim of local Docker execution is made.
- Actual hosting still requires a persistent disk/volume, credentials and a reachable Ollama endpoint. No hosting service has been provisioned by this preparation step.

## Usability refinement

- Production build passed after UI changes.
- Verified automatic installed-model selection, Ready to chat status, Quick guide dialog, and restoration of the last opened conversation after browser refresh.
- New Chat is accessible directly in the header, even with the sidebar closed. Send and Stop now have visible text labels.
- Browser checks confirmed Ctrl+K focuses chat search and Ctrl+Shift+O opens a new chat from an existing conversation.
- Rechecked the updated mobile layout at 390×844: page width remains 390 pixels with no horizontal overflow.
- Added a Windows launcher that reuses an existing server, can start Ollama and FastAPI in the background, and opens the browser. The PowerShell parser and reuse-existing-server path were checked; cold-start behavior uses the same previously verified uvicorn command.

## Passed

- Dependency installation in a project virtual environment and npm lockfile.
- TypeScript check and Vite production build.
- Five backend tests: conversation CRUD/search/validation; streamed events, full follow-up history, regenerate, edit-and-replace and isolation; friendly connection failure with persisted error; bounded memory summarization; origin protection. These use temporary SQLite and a controlled Ollama transport.
- Running FastAPI `/api/health` and actual local Ollama `/api/tags` connectivity.
- Installed and used `llama3.2:latest` (approximately 2 GB).
- Live model generated a Python fenced code block. Browser displayed syntax colors, a Python label and copy confirmation.
- Live follow-up asked for the earlier project codename; model answered `Cedar` correctly. Regeneration retained two user messages.
- Browser refresh, reopening saved chat, renaming to `Cedar workspace`, and title search.
- In-app deletion confirmation and successful deletion of the disposable cancellation-test conversation.
- Multiple conversations and live generation in a second independent chat.
- Actual SSE timing: eight token events; first at 1.47 seconds, eighth at 2.61 seconds. Explicit stop persisted 27 characters with `stopped` status. Test conversation then deleted via the API.
- Browser Stop button halted a longer response and retained visible partial content with “Response stopped”.
- Light and dark settings, installed-model selection, desktop rendering at 1440×900 and mobile at 390×844. Mobile document width equaled viewport width (390), with accessible composer and drawer.

## Scope and caveats

- A first automated browser run exposed an accessible-label mismatch in its Regenerate locator; it was interrupted, corrected, and the corresponding flows were verified in the embedded browser. The full reusable Playwright scenario has not been reported as a passing suite.
- Long-history summary behavior was tested with a controlled model response, not a prolonged live conversation. Summaries are lossy and conservative byte budgeting can summarize earlier than necessary.
- Clipboard UI confirmation was observed. Clipboard permissions depend on the browser and host; manual selection remains available on failure.
- Vite reports a non-blocking approximately 510 kB uncompressed entry bundle warning, mostly Markdown/highlighting dependencies. The gzip size is approximately 158 kB.
- The test client reports a dependency deprecation warning about HTTPX, with all five tests passing.
- The application is a local, single-user service and is intentionally bound to loopback. It does not include public-hosting authentication, uploads, RAG or voice.
- Small live verification conversations may remain in local history; the downloadable archive excludes the database and `.env`.
