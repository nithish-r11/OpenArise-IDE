# OpenArise product improvement

Review: October 9, 2026 (Asia/Calcutta). Repository:
`E:\OpenArise-IDE\OpenArise`.

Current source acceptance: **NOT VERIFIED — final live workflow validation is in
progress**. Unit/regression checks and the completed real operations below are
reported separately. Existing release artifacts predate these source changes and
are **NOT VERIFIED** for this implementation. No commit, push, dependency
installation, package-lock change or architecture replacement. The existing local
`.gitignore` modification is preserved and unstaged.

The subsequent live permission check observed an unapproved probe file and stopped
further approved-change/recovery acceptance. The source permission repair and its
real Electron/backend regressions are recorded in
[PERMISSION_SAFETY_REPORT.md](PERMISSION_SAFETY_REPORT.md): **330 desktop tests**
and **236 backend tests** passed. Deterministic inference was used for this repair;
renewed live Qwen and packaged acceptance remain unverified.

Follow-up: the six requested real-Qwen Python source workflows are now **VERIFIED**,
including permission refusal, one-time Allow, fresh verified recovery and failed
recovery rollback. A live recovery-planning defect was fixed and retested; final
regressions are **330 desktop / 244 backend**. See
[LIVE_PERMISSION_RECOVERY_REPORT.md](LIVE_PERMISSION_RECOVERY_REPORT.md) for actual
evidence, the repair and scope. Other product/release acceptance is not implied.

## Changes and reasons

- The normal AI response previously exposed internal lifecycle, evidence, IDs and
  verification reports. It now presents a concise Answer, Verified, Not verified,
  Failed, Rolled back or Blocked result. Technical information remains under
  collapsed Details. A short model-response instruction is applied in the existing
  orchestrator; supplied file context remains the factual authority.
- Read-only answers do not imply execution or verification. Activity labels a
  returned answer clearly while retaining its actual unverified state. A pending
  request shows a wait, without guessing backend activity or a response source.
- Frontend AI work previously had Python/pytest execution tools only. The existing
  host now registers `execute_project_tests` and `build_project` for observed npm
  scripts. Shared backend resolution binds command ID, manifest revision, action
  and project directory. Permission review shows the exact observed script. Missing
  or stale metadata blocks approval/execution.
- Backend build evidence is distinct from test evidence. Recovery retests the
  original validation tool, including its original command descriptor. Failed,
  invalid or stale evidence continues to block the existing CompletionGate.
- Explorer adds real folder creation and file/folder rename. The existing FileHost,
  production PermissionManager, contained paths and disk revision checks remain in
  use. Rename preserves bytes, rejects existing destinations/protected or linked
  descendants, and is blocked while any editor buffer is unsaved. No force rename
  or overwrite was added.
- Project/connection diagnostics are collapsed. Activity is compact and separate
  from the static logo. Short-window spacing reserves usable conversation space;
  result scrolling accounts for the Activity panel rather than covering the result.
  A real production smoke caught the initial short-window regression before the
  spacing fix.

The October 8 actual-source context, multi-language editing, static capabilities,
safe saves/reloads and manual approved npm controls are retained. Their historical
audit is [PRODUCT_QUALITY_REPORT.md](PRODUCT_QUALITY_REPORT.md).

## Validation recorded so far

| Check | State | Result/scope |
| --- | --- | --- |
| Full desktop `npm test` | VERIFIED | **321 passed**: 271 Vitest across 23 files, 50 Python host; 0 failed |
| Full backend pytest | VERIFIED | **216 passed**, 0 failed; 64.88 seconds |
| Production build | VERIFIED | TypeScript, Vite and Electron bundles; existing non-failing Monaco chunk-size advisory |
| Final production/development smoke | NOT VERIFIED | Both passed before the last wording adjustment; final exact-source reruns remain pending |
| Normal `npm start` | VERIFIED | Actual native visible OpenArise window, exactly one window; ordinary `electron .`, no debug/profile flags; normal close exited zero |
| Direct UI Python workflow | VERIFIED | Native folder picker → real files → Monaco edit → unsaved execution guard → safe save; disk bytes confirmed; Run output `12`; actual pytest **1 passed**, exit 0 |
| Direct UI read-only Qwen | VERIFIED | Real local `qwen2.5-coder:7b` returned the actual entry point, multiplication behavior and test filename; concise Answer, Local AI source, Details collapsed |
| First broad live run | NOT VERIFIED | Real read-only/full-stack context, frontend creation/save/conflict/reload, folder/file rename, Python API run/stop, npm test/build and write denial passed; recovery-action generation then timed out |
| Longer-timeout live retry | NOT VERIFIED | Stopped at a QA input-selection defect; malformed destination was rejected and the original folder retained. Harness selection/value assertions are corrected; no final recovery/gate claim yet |
| Normal development launch/reopen | NOT VERIFIED | Pending after live harness finishes |
| Latest Windows distribution | NOT VERIFIED | Not rebuilt for this task; historical package evidence is kept separate |

Direct native UI checks use the installed computer-use skill. The broader
`tests/electron-product-flow.cjs` uses the actual renderer/preload/main/Python/Qwen
path and disposable projects. It supplies native picker paths and bounded approval
choices for unattended QA. Model output, file operations, commands, evidence,
recovery and gate responses are real; no AI/provider/backend fixture responses.
Tool-specific controlled acceptance prompts are not a claim that arbitrary
natural-language requests are always successful.

First-run evidence:
`desktop/.packaging/product-audit/run-1791504843713/evidence.json`.
The timed-out request returned **failure / FAILED / INCONCLUSIVE**, with **zero
tool results** and the explicit 180-second Ollama timeout message. It did not
become VERIFIED. Ollama reported zero VRAM and approximately 4.3 output tokens per
second in the local runner log. The retry uses the existing
`OLLAMA_TIMEOUT_SECONDS=600` setting for that validation process only; production
defaults and `.env` files are unchanged. Retry evidence is retained separately in
`desktop/.packaging/product-audit/run-1791505395599/`.
That retry's screenshot showed the old and new folder paths concatenated by the
QA helper's unconfirmed Ctrl+A. The application returned "The destination folder
does not exist" without renaming the original folder. The helper now selects the
real input directly, verifies its selection and asserts the exact entered value
before submitting; filesystem acceptance assertions remain unchanged.

## Security and support scope

The existing React → BackendClient → preload → trusted allowlisted Electron IPC →
Python host → ProjectWorkspaceService/AgentOrchestrator path is retained.
`contextIsolation=true`, `nodeIntegration=false`, `sandbox=true` and
`webSecurity=true` remain in force. React receives no Node filesystem/process
access, generic IPC or executable/argv selector. The existing PermissionManager,
recovery engine, evidence system and CompletionGate remain authoritative.

Approved npm scripts are project code running with user privileges. Backend
execution uses fixed installed Node/npm invocation, disabled pre/post hooks,
120-second timeout and bounded captured output. This is not an OS sandbox.
pnpm/yarn execution, automatic dependency installation and npm dev/start execution
remain unavailable. Manual terminal results remain separate from AI proof.

Detection covers common Python/Node/frontend manifests and named frameworks, but
static framework detection is not runtime validation. FastAPI is absent from the
current backend environment; no FastAPI package was installed. Flask, Django and
Express server runtime acceptance is also not claimed. Representative full-stack
QA uses React/Vite/TypeScript plus a Python standard-library API. Python execution
and pytest still use the displayed, controlled workflow.

Rename is implemented for Windows and fails closed on other platforms. Evidence
supports the associated validated command; passing a build/test invocation does
not prove arbitrary semantic correctness. No fake streaming, progress percentages,
tool activity, recovery success, stale-proof success or model-only verification is
introduced. Historical release/policy/signing/clean-machine limitations remain in
[RELEASE_VALIDATION.md](RELEASE_VALIDATION.md).
