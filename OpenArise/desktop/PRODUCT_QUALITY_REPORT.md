# OpenArise product-quality audit

Review: October 8, 2026 (Asia/Calcutta). Repository: E:\OpenArise-IDE\OpenArise.
Targeted source product acceptance: **VERIFIED** for the supported workflows below.
Distribution of these audit changes: **NOT VERIFIED**; release artifacts have not
been rebuilt. No fully production-ready claim. No commit, push, dependency
installation or architecture replacement. Existing .gitignore content is preserved
and unstaged.

## A. Audited

Inspected repository handovers/contracts, backend facade/context/agent/tools,
evidence snapshots and CompletionGate; desktop main/preload/IPC/process hosts,
Explorer/editor/terminal/AI/intelligence/outcome components; existing tests,
normal entry points, packaging configuration and historical release evidence.
Established the prior 271 desktop/188 backend regression baseline before changes.
The root cause was confirmed in code: counts-only intelligence and snippet counts
reached the agent, without the actual project structure or source contents.

## B. Fixed

- Workspace-owned source context now reaches the existing ContextManager and
  AgentOrchestrator; caller-provided fictional file context is overridden.
- Refresh context explicitly rescans; edited frontend sources/configs affect
  evidence freshness. Create/save/reload requests the retained gate again.
- Shared writes replace existing files atomically; new creation is exclusive.
  Failed atomic replacement preserves original bytes and cleans its temporary file.
- Reload synchronizes disk into the retained Monaco model, with dirty-buffer review
  and protection against edits made while reading/saving.
- Real JSON smoke exposed a Windows line-ending acknowledgement defect: the file
  was saved, but backend-normalized LF text differed from Monaco's CRLF buffer.
  A confirmed save now synchronizes the returned buffer only if no newer edit
  happened during the request. Two regression tests protect that acknowledgement
  and concurrent edits; the real smoke also verifies the inserted newline on disk.
  Monaco initializes its models with the same LF convention so a first save of an
  empty/single-line file does not unnecessarily reset native undo history. The real
  smoke now checks Ctrl+Z/Ctrl+Y after JSON save as well as persisted bytes.
- First development smoke exposed late Monaco dependency optimization invalidating
  the lazy editor import. Vite now includes the actual local Monaco registrations
  in initial optimization; this preserves the existing CSP and lazy editor design.
- Quoted secret keys are redacted; valid UTF-8 excerpt boundaries are retained.
- INCONCLUSIVE, DENIED and CANCELLED retain distinct returned meanings. Rollback
  remains ROLLED_BACK, not a generic recovery attempt. No success rule was relaxed.

## C–D. Capabilities and workspace UX

Actual lazy Explorer, filename search (200-result bound), refresh of expanded
folders, empty-file creation in existing folders and multiple Monaco tabs. Common
frontend/backend/config/document text can be edited with existing revision and
permission safeguards. Local bundled syntax registration/JSON worker; no CDN.
Ctrl/Cmd+P focuses filename search. Session-only recent projects use at most six
main-retained native-picker IDs, not renderer-controlled roots.
Existing panel composition, static logo and separate activity visualizer are
preserved. Controls have consistent focus/hover/disabled states, scrollable
capability details and bounded status labels. No fake project data or telemetry.

## E. Actual project context

Backend-only context contains at most 80 safe relative paths and 16 source/config/
test excerpts, at most 2,400 characters per file and 16,000 content characters.
Entry points/manifests/tests are prioritized; lockfile contents, protected,
dependency/runtime, linked and binary files are excluded. Common secret patterns
and quoted keys are redacted, not a guarantee of exhaustive secret discovery.
Coverage, truncation and unreadable files are explicit. React receives counts,
not the source-context payload, and performs no project intelligence analysis.
Source contents are untrusted data, never privileged instructions. Read-only
answers use the same real model/provider pipeline without tools or invented proof.

## F. Detection and execution scope

Static detection covers React/Vite, TypeScript/JavaScript, HTML/CSS, Python,
FastAPI/Flask/Django and Node.js/Express using actual files/imports/declarations.
Common package/pyproject/requirements/lock/tsconfig/Vite files are recognized.
Entry and run commands are candidates, not proof that frameworks/dependencies run.
Actual representative full-stack acceptance uses React/Vite/TS and a Python
standard-library API; framework detection fixtures cover the other named stacks.

Controlled execution retains Python checks, saved-file Run and pytest. Detected
npm test/build scripts require a native folder/script review; main rechecks the
manifest revision, uses installed Node/npm with fixed arguments and project cwd,
and disables pre/post lifecycle scripts. Existing supervision/output bounds/Stop
apply. Renderer cannot supply argv, executable or unrestricted shell commands.
These scripts still run project-defined code with user privileges, not an OS
sandbox. pnpm/yarn execution and npm dev/start execution are unavailable; no
fallback or dependency install is attempted. Manual Node results are not silently
converted into agent evidence. Agent tools remain read/write/Python/pytest.

## G. Error paths

Reviewed and regression-covered missing project, invalid/protected/linked paths,
unreadable/binary/large files, conflicts, missing runtime/environment, unavailable
Ollama/model, invalid host responses, transport/timeout, tool/test failure, denied
permissions, stale/failed proof, recovery failure and actual rollback.
Important unsaved-guard connection failures now surface. New command/create/reload
errors retain buffers and give a retry/review action. Raw tracebacks remain in
diagnostic logs, not primary renderer messages. Optional session shortcuts may
fail without disabling native Open Project; they are not durable project history.

## H. Verification and recovery

CompletionGate remains authoritative. Backend dispatch/COMPLETED/model text is
not proof of VERIFIED. Returned failures, stale evidence, unresolved contradictions
and inconsistent gate fields refuse verified display. Baseline/failed/fresh proof,
original requirement identity and real recovery links are retained. Activity uses
returned synchronous states/events only, never inferred progress or live streaming.
Actual visible Electron and qwen2.5-coder:7b completed the disposable full-stack
workflow, including baseline pytest, an approved intentional mutation, actual
failure, backend recovery and mandatory fresh retest. The backend returned
RECOVERED and CompletionGate VERIFIED. The original requirement remained
`c8d48495-3d0b-4f5f-8453-f2ca3e54e81f`; fresh mandatory test evidence
`aee08c94-2729-46c7-bc4f-e30640a82096` followed recovery and resolved the failed
proof. A subsequent frontend source mutation made that proof stale and the real
gate returned NOT_VERIFIED.

The separate immutable failing-test project returned failure, actual ROLLED_BACK
and CompletionGate NOT_VERIFIED. A recovery-selected narrow test passed, but the
mandatory whole-project retest failed; the passing subset could not override it.
Original tests were never edited. The final UI displayed FAILED and rollback.
Read-only full-stack and the exact requested Python-only prompt both returned
answers citing actual files, used zero tools and retained INCONCLUSIVE gates.
Permission denial prevented mutation; approval allowed only the reviewed writes
and pytest. Recorded activity is the actual returned lifecycle, not live progress.

Primary evidence (generated and excluded from source):
`desktop/.packaging/product-audit/run-1791455717753/evidence.json`.
Request IDs: success `28911836-6b2c-47e5-8106-64a43b785ed7`; refusal
`c9875f1f-38c2-4161-8471-d3e2228a8433`. This run also exercised actual Explorer,
new TypeScript file, native Monaco editing/save, external conflict/reload, filename
search, controlled Python API start/HTTP response/Stop, denied npm script launch,
real npm test and Vite build. No AI/backend/tool response was replaced.

Additional real outcome run completed with status VERIFIED and no fixture
responses: `desktop/.packaging/product-audit/run-1791473731368/evidence.json`.
Success request `1f94fd5a-044e-406a-955f-78f7ed438bd3` returned RECOVERED/VERIFIED
with eight evidence records and four test-tool executions; the same requirement
`de1a8e51-0cfe-49f8-89cd-c843f9394028` remained attached after frontend mutation
made the gate return NOT_VERIFIED. Failure request
`f4b8fc8d-6e80-4df8-a15f-bb40c328037d` returned FAILED/ROLLED_BACK/NOT_VERIFIED,
with six evidence records and three test-tool executions. These are execution
counts, not pytest test-case totals.

The run expanded the actual AI panel and checked the final heading's nonzero
rectangle inside its visible scrolling panel, plus no horizontal page overflow,
at requested outer window sizes 1320x880, 1050x740 and 760x540. Actual screenshots
were inspected, including the small VERIFIED and FAILED panels. Windows 125% DPI
rounds actual outer sizes by one/two DIP; inner content is smaller. Both requested
and measured sizes/DPI are recorded in the evidence, not relabelled as identical.
One earlier additional run was interrupted before recovery returned; it is not
counted as passed or substituted for this completed run.

## I–J. Validation

| Check | Result |
| --- | --- |
| Full backend suite | 205 passed, 0 failed, 40.60 seconds |
| Desktop focused workspace/context tests | 40 passed, 3 files |
| Python host suite | 41 passed, 0 failed, 9.651 seconds in the final npm test run |
| Full desktop suite | 299 passed, 0 failed: 258 Vitest tests in 22 files (33.04 seconds), plus 41 Python host tests |
| Production build | Passed TypeScript, Vite and Electron bundles; non-failing large Monaco/JSON chunk warning |
| Production Electron smoke | VERIFIED, final exit 0: actual JSON save/undo/redo and Python file operations, Python/pytest, conflicts, narrow IPC/security and shutdown; AI states are labelled deterministic fixtures |
| Development Electron smoke | VERIFIED, final exit 0 including native JSON save/undo/redo; first run after Vite config change also passed fresh optimization; same real file/process/security and labelled fixture UI checks |
| Real source full-stack/Python/Qwen flow | VERIFIED: actual context, read-only answer, approved mutation, failed pytest, recovered fresh proof, stale refusal and failed recovery/rollback |
| Normal npm start / npm run dev | VERIFIED: native observer recorded exactly one visible main window, title OpenArise, capture succeeded; no debug flags or separate manually launched Vite |
| Real project close/reopen | VERIFIED, npm run test:real exit 0: persisted bytes visible after actual app restart; unsaved reload/discard and conflict guards, Python syntax failure, real Run and pytest also passed |
| Release artifacts | Historical, not rebuilt for this audit |

The live product QA script uses disposable repository-contained sample projects
and supplied native picker/approval decisions. All of its model/tool/recovery/
test/gate responses are real.
This is automated real-application validation, not a claim of human-operated QA.
The live QA uses the existing configurable 300-second generation timeout; shipped
defaults remain 180 seconds. Deterministic edge fixtures and smoke AI states are
explicitly marked as fixtures and do not prove live model behavior.

Normal launch evidence: `desktop/.packaging/product-audit/normal-source/launch.json`
and `normal-dev/launch.json`, with native screenshots. Source command line was
`electron.exe .`; the normal managed development script used only its existing
`--openarise-dev` environment selector. Both windows were closed gracefully after
observation. The development smoke confirmed the editor loaded on the first run
after the optimizer configuration changed, not merely from an old warm cache.
The real project reopen probe used the existing generated
`desktop/.packaging/real-flow/` project/profile and retained real saved disk bytes.
Its Qwen explanation returned INCONCLUSIVE, not a fabricated verified outcome.

## K. Remaining limits

No framework-specific language server, dependency installation, package-manager
fallback, frontend agent execution/recovery engine, unrestricted shell or new
service. No full-text search, folder creation/rename/delete, watcher, autosave,
durable buffers/recents/history or cross-crash exactly-once execution. Synchronous
model work cannot be cancelled mid-generation from the UI; pending approval can.
The source context is deliberately partial. Model conclusions may be inaccurate
and must not be confused with actual test evidence. Existing scanner refreshes
still hash source files; very large-workspace performance has not been benchmarked.
Signing, clean-host acceptance and policy-limited distribution are not newly
verified. Current packages predate these changes and need a separate rebuild and
validation before shipping. No fully production-ready claim.

## Change manifest

54 source/test/documentation files changed or added by this audit, relative to
the OpenArise repository folder. The pre-existing .gitignore modification is not
part of the implementation and remains unchanged/unstaged. No dependency manifest,
lockfile, static logo, packaging icon or Electron security options changed.

```text
FINAL_ACCEPTANCE_REPORT.md
ai-engine/README.md
ai-engine/app/agent/orchestrator.py
ai-engine/app/api/backend.py
ai-engine/app/api/services.py
ai-engine/app/context/manager.py
ai-engine/app/context/project.py
ai-engine/app/project/capabilities.py
ai-engine/app/project/scanner.py
ai-engine/app/tools/fs.py
ai-engine/tests/test_project_capabilities.py
desktop/AI_ARCHITECTURE.md
desktop/PRODUCT_QUALITY_REPORT.md
desktop/README.md
desktop/RELEASE_VALIDATION.md
desktop/electron/main.ts
desktop/electron/project-ipc.ts
desktop/electron/project-service.ts
desktop/electron/terminal-service.ts
desktop/python/file_host.py
desktop/python/intelligence_projection.py
desktop/shared/capabilities.ts
desktop/shared/intelligence-response.ts
desktop/shared/project-ipc.ts
desktop/shared/terminal-ipc.ts
desktop/src/components/AI/AIPanel.tsx
desktop/src/components/AppShell.tsx
desktop/src/components/Explorer.tsx
desktop/src/components/ProjectCapabilities.tsx
desktop/src/components/Terminal/TerminalPanel.tsx
desktop/src/editor/MonacoEditor.tsx
desktop/src/editor/language.ts
desktop/src/styles/polish.css
desktop/src/types/project.ts
desktop/src/types/terminal.ts
desktop/src/workspace/completion.ts
desktop/src/workspace/useAI.ts
desktop/src/workspace/useTerminal.ts
desktop/src/workspace/useWorkspace.ts
desktop/tests/ai-panel.test.tsx
desktop/tests/app.test.tsx
desktop/tests/electron-product-flow.cjs
desktop/tests/electron-smoke.cjs
desktop/tests/ollama-ui.test.tsx
desktop/tests/phase7.test.tsx
desktop/tests/phase8.test.tsx
desktop/tests/product-capabilities.test.tsx
desktop/tests/project-commands.test.ts
desktop/tests/project-ipc.test.ts
desktop/tests/project-security.test.ts
desktop/tests/test_file_host.py
desktop/vite.config.ts
docs/BACKEND_PROCESS_CONTRACT.md
docs/INTEGRATION_HANDOVER.md
```

Generated QA evidence, builds, caches, dependencies and local state stay excluded.
