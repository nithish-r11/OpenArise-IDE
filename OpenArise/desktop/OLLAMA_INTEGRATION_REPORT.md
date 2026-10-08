# Real Ollama integration and live recovery — 2026-10-06

**Real Qwen generation, permission gating, controlled recovery and fresh-evidence
CompletionGate verification: VERIFIED in the source-built Electron app.**
**Full product/release acceptance: NOT VERIFIED.** No commit or push.

## Original integration root cause

The desktop host inherited `llama3`, but the actual `/api/tags` response contained
only `qwen2.5-coder:7b`. Old effective settings were localhost:11434/llama3,
without a backend .env or OLLAMA_MODEL override. Actual generation returned
HTTP 404, model llama3 not found; the original stdio host returned nested failure
with no tools executed. Host logging was disabled, Electron discarded stderr,
valid text-only agent_message was omitted from presentation, and context needed
manual loading. A 60-second provider budget was insufficient for an observed
64.5-second inference.

DesktopSettings now uses the existing settings architecture with
127.0.0.1:11434/qwen2.5-coder:7b/180 seconds. Existing environment/.env overrides
remain; standalone defaults remain compatible. The existing OllamaProvider checks
the exact model tag, returns safe distinct failure reasons and generates using
JSON schema with stream=false. Answer only uses the same AgentOrchestrator with
zero permitted tools; Agent actions uses the existing tool/permission workflow.
Project context loads automatically through the existing bounded adapter.
Redacted literal answers are bounded to 8,000 characters; tool arguments/output
remain withheld. Startup/read transport is 30 seconds; agent/resume is 15 minutes.
Safe bounded diagnostics retain exception types/frames without raw values.
No model pull, fallback provider, direct renderer HTTP or second backend exists.

The earlier October 6 source checks returned real function/explanation text,
labelled BACKEND RESPONSE and UNVERIFIED with no execution evidence. A real write
proposal stopped for permission and Deny prevented creation. Full editing/save,
Python/pytest, failure/conflict/close/reopen and normal npm start/npm run dev
passed then. Their logs/native captures remain under ignored
`desktop/.packaging/ollama-integration/`; they are earlier-revision evidence,
not a rerun of final recovery changes.

## Live recovery defects fixed

The existing recovery engine now retains a resumable plan, pauses for each exact
write/execute approval, revokes one-use grants, checkpoints actual writes and
performs a mandatory whole-project pytest retest. It returns actual diagnosis,
RecoveryResult and RETESTING state through the existing response/IPC path.

Real Qwen recovery initially repeated completed intentional-fault instructions
included in failure evidence. Those attempts genuinely failed and rolled back;
no success was asserted. The planner now excludes completed user_request text
while retaining actual failure facts/diagnosis. Repair actions still come from
Qwen. Pytest also needed a fresh bytecode namespace to prevent rapid same-size
rewrites loading stale .pyc. Source/test/config fingerprints now bind test proof
to the actual project, and changed retained requests are rechecked by CompletionGate.

Failed proof remains recorded. Resolution requires an actual RECOVERED record,
linked fresh executed passing retest and matching original requirement. The UI
accepts only safe resolution references and still refuses inconsistent, stale,
failed or unverified gate results. Recovery activity uses returned timestamps and
states; a later outcome is not assigned to an earlier attempt. No streaming or
percentage progression is invented.

## Primary real application acceptance

`tests/electron-live-recovery.cjs` drives a visible actual Electron app. Only the
native picker result and QA profile are supplied; all IPC handlers, BackendService,
AgentOrchestrator, PermissionManager, recovery, pytest, evidence and Ollama are real.
The arithmetic-only temporary projects keep original tests unchanged.

Authoritative run: `.packaging/final-acceptance/live-1791295655369/evidence.json`.

| Check | Actual result |
| --- | --- |
| Deny model-proposed write | DENIED; executed=false; file unchanged |
| Approve fault/test/recovery/retest | Actual backend actions and file mutations |
| Detect intentional addition fault | Actual pytest exit 1; real model diagnosis |
| Recovery | RECOVERED; one attempt; real repair write and retest |
| Fresh passing proof and CompletionGate | VERIFIED, 1/1 requirement; 8 evidence records; 4 test-tool executions |
| External mutation after verification | Retained gate NOT_VERIFIED; stale proof rejected; UI withholds VERIFIED |
| Deliberately unsuccessful recovery | Actual attempt; scoped test passes but mandatory whole-project retest fails; ROLLED_BACK, FAILED, gate NOT_VERIFIED |
| Responsive VERIFIED view | Visible final heading at 1320x880, 1050x740, 760x540; screenshots inspected |

Success request: `0a8d6ac5-44f8-4c34-b369-74c029cbc17b`.
Requirement: `8034d60f-1a03-4264-b401-5526c377ec71` throughout execution and proof.
Failed evidence is retained and linked to fresh retest
`2c0d44b2-b02e-4b39-b1c5-39cb21b8a9bc` plus real recovery record
`5cc2b518-8200-4a00-9a16-03bb0c003b35`. Baseline proof is stale/superseded.
Failure request: `238e81e9-658c-49ec-8112-f83515814780`; the deliberate assert False
and original tests remained unchanged, and final gate refuses verification.

The failure screenshot captured an earlier pending/approved frame. It does not
prove the settled final FAILED UI, even though actual backend failure is proven.
The source probe now waits for exact request/final state/message and idle controls,
with no pending actions. Syntax validation passed; that stronger probe has not
been rerun. Deterministic failure rendering tests are separate fixture evidence.

## Final tests and packages

| Check | Result |
| --- | --- |
| npm test | **265 passed**: 230 Vitest in 19 files + 35 Python host; 0 failed |
| Backend full pytest | **188 passed**: original 161 + 19 preceding Ollama + 8 recovery tests; 0 failed |
| Production build | VERIFIED; existing non-failing Monaco chunk warning |
| Final production Electron smoke | VERIFIED; actual files/Python/pytest, AI fixtures explicitly labelled; shutdown cleanup |
| Development Electron smoke | Passed before final activity timestamp fix; latest rerun NOT VERIFIED |
| Latest ZIP, portable, NSIS builds | VERIFIED; rebuilt current application, no publishing |
| ZIP/unpacked source consistency and basic bundled runtime | VERIFIED; all 77 backend/5 host files match; actual bundled read/save/Python/pytest |
| Latest normal ZIP launch and packaged live recovery | NOT VERIFIED |
| Latest portable launch/payload | VERIFIED by user confirmation of exactly one visible window; actual extracted payload matches ZIP plus standard helper; interactive/live recovery NOT VERIFIED |
| Latest NSIS install/launch/uninstall | NOT VERIFIED |

No live Ollama limitation remains for the controlled source recovery case.
Packaged Ollama recovery, clean Windows and installer acceptance remain unverified.
Automatic approval review failed at the account usage limit on a privileged
archive listing, so additional privileged runtime/package checks are BLOCKED.
This was a review failure, not an unsafe-action determination; no check/policy
was bypassed. Historical October 4 policy blocks are documented separately from
current artifact behavior in RELEASE_VALIDATION.md.

See [../FINAL_ACCEPTANCE_REPORT.md](../FINAL_ACCEPTANCE_REPORT.md) for the exact
changed-file list, proof IDs, fixes, test/log details and final acceptance checklist,
and [RELEASE_VALIDATION.md](RELEASE_VALIDATION.md) for latest artifact hashes.
The existing .gitignore local change is preserved; package-lock, dependencies,
main/preload/security sources and logo are unchanged. No commit or push.
