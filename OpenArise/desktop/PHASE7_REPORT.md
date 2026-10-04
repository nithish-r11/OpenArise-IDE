# Person 3 Phase 7 — Permission, Recovery and Verification UI

Date: 2026-10-04
Repository: E:\OpenArise-IDE\OpenArise

Phase 7 implements desktop presentation and existing command delegation.
AI UI validation uses deterministic fixtures/controlled providers.
**Live Ollama permission, recovery and verification flow remains unverified.**
This report does not declare full product/release acceptance.

## Implemented behavior

Permission cards display the returned safe tool name, risk and scope, with
Allow, Deny and Cancel. Allow sends the existing approve command and resumes
only after confirmed approval, preserving the original request/tool IDs.
Commands lock before awaiting transport. Disabled controls and that lock prevent
duplicate decisions. Pending command stages are explicit; completed, failed,
denied and cancelled decisions remain in session history. A failed transport
does not confirm a decision or permit another Allow until the request is
refreshed. A response for a changed project never triggers resume.

Failure/recovery cards display returned failure summary, category, severity,
diagnosis/root cause, recovery state and retry/retest details when available.
Missing fields say not reported/unavailable. A recovery count or recorded
RECOVERING/recovery_finished event says attempted with outcome unavailable.
Only an explicit RECOVERED result can show recovery completed; it never verifies
the task by itself. BLOCKED, FAILED, RETRYING and RETESTING are presented from
returned recovery state, without timers or invented progress.

Verification cards display overall status, CompletionGate result, requirement
coverage, evidence records, stale/superseded flags, missing/invalid evidence,
failed/contradictory evidence, remaining issues and performed test-tool results.
Counts belong to the backend. Test executions mean test-tool calls, not pytest
test case counts. Final result is VERIFIED, UNVERIFIED, FAILED, BLOCKED or
UNAVAILABLE. The result, session-history label and Phase 6 activity visualizer
share a defensive completion presentation rule: successful dispatch/tool/recovery
does not establish verification. Contradictory metadata, failed evidence,
active stale evidence, missing coverage, remaining issues or transport errors
withhold verified completion. No independent verifier or CompletionGate was
implemented in the renderer.

The main process tags injected test-adapter responses as test_fixture, overriding
adapter source claims. The AI panel and activity visualizer visibly show
TEST FIXTURE / mocked UI validation / no live AI validation. Production
transport is labelled BACKEND RESPONSE / last returned data. Missing provenance
is SOURCE NOT REPORTED. No renderer-selectable fixture mode was added.

The real development Electron smoke exposed a hidden-window issue when
ready-to-show did not fire. Main now also shows the existing window after a
successful renderer page load; failures still show the existing error dialog.
The smoke checks visibility without forcing the window to show.

## Existing backend contracts and limits

The protected backend remains unchanged. PermissionManager, RecoveryEngine,
the evidence/verification system and CompletionGate retain authority.

The current AgentResponse action data returns requirements, evidence,
VerificationResult and tool results. Its internal-error field can include a
FailureEvent. Normal tool failures do not expose a full diagnosis through this
action contract. FailureEvent has no severity field, so actual projection
reports severity unavailable rather than inferring it.

RecoveryResult is an existing backend model, but the current action response
does not emit a detailed recovery result. The desktop can project a bounded
optional RecoveryResult if returned in action data; the completed/blocked/retest
presentation is exercised with fixtures in this phase. It does not read agent
internals, persistent memory or recovery logs to manufacture such a result.

The desktop-only projection copies safe existing verification/evidence fields.
Raw tool arguments, source/code/output, file hashes, arbitrary metadata,
exception traces and unrelated model prose remain withheld. It reuses
SecretRedactor and existing backend models. Evidence is limited to 40 records,
requirements and requirement results to 30, evidence-reference/contradiction
lists to 20, and missing/remaining-issue lists to 10. Text is bounded. Partial
collections are visibly labelled; no dropped record is represented as a zero.
These are retained synchronous observations, not streaming or file watching.

## Exact files changed in this phase

The list is relative to the repository and measured against file contents at
the start of Phase 7. The desktop tree was already untracked at that point.

Modified:

- desktop/AI_ARCHITECTURE.md
- desktop/README.md
- desktop/electron/backend-service.ts
- desktop/electron/main.ts
- desktop/python/agent_projection.py
- desktop/shared/agent-response.ts
- desktop/src/components/AI/AIPanel.tsx
- desktop/src/components/Activity/AriseActivityVisualizer.tsx
- desktop/src/types/activity.ts
- desktop/src/types/ai.ts
- desktop/src/types/backend.ts
- desktop/src/workspace/activity.ts
- desktop/src/workspace/useAI.ts
- desktop/tests/ai-fixtures.ts
- desktop/tests/ai-panel.test.tsx
- desktop/tests/electron-smoke.cjs
- desktop/tests/fixtures/smoke-backend.cjs
- desktop/tests/test_agent_host.py

Added:

- desktop/PHASE7_REPORT.md
- desktop/src/components/AI/PermissionCard.tsx
- desktop/src/components/AI/RecoveryCard.tsx
- desktop/src/components/AI/VerificationCard.tsx
- desktop/src/styles/outcomes.css
- desktop/src/workspace/completion.ts
- desktop/tests/phase7.test.tsx

Generated build/screenshots/test profiles remain ignored. package.json and
package-lock.json were not changed; no dependency was installed. The existing
root .gitignore modification predates this phase.

## Validation

| Check | Result |
| --- | --- |
| npm test — Vitest | 203 passed across 15 files, 0 failed |
| npm test — desktop Python hosts | 32 passed, 0 failed |
| Desktop test total | 235 passed; 36 new Vitest cases and 4 new host cases |
| npm run build | Passed: TypeScript, Vite renderer and Electron main/preload bundles |
| npm run test:smoke | Passed with final application code; actual production renderer/main/preload/IPC and fixture AI flows |
| npm run test:smoke:dev | Passed; development renderer/main/preload/IPC and fixture AI flows |
| ai-engine/.venv/Scripts/python.exe -m pytest tests -q | 161 passed in 12.41s, 0 failed |
| Backend source diff | Empty |
| Dependency manifest/lockfile changes | None |
| Original logo SHA-256 | 7170a7b5a083b27fa852082e8ae42db47419f52376aefc1a281748eb2b6486e3 |

Vite retains its existing non-failing warning for the large local Monaco chunk.
Initial restricted-sandbox runs denied Vite worker spawning and Python temporary
files. The listed passing runs used approved normal subprocess/temp access.
A malformed denial fixture was corrected after strict DTO validation rejected it.
The first development smoke failed its window visibility assertion; main's
successful-page-load show fallback addresses that actual application issue.
A subsequent development smoke timed out because native Ctrl+A did not reliably
replace the previous prompt. The harness now explicitly selects the textarea
and verifies the exact prompt before sending; the development smoke then passed.
This changes test input only. Production passed with the final application code
before that harness adjustment. An additional production rerun was not executed:
automatic approval review could not complete because of the account usage limit,
not because it determined the command was unsafe. No approval check was bypassed.

The Electron smokes use the actual renderer, preload, main process and guarded
IPC with a main-only deterministic AI/intelligence adapter and supplied native
picker responses. File reads/Monaco edits/saves, controlled Python stdout/stderr,
real pytest (one passing temporary test), conflicts, terminal sessions and
owned-process shutdown use the real desktop Python hosts. AI permission,
recovery, verification and completion results in these smokes are fixtures.
They do not prove live model behavior.

Phase 7 scenarios cover write/execute permission required, Allow and separate
resume, Deny, Cancel, pending and returned decisions, duplicate prevention,
failure, recovery unavailable/attempted/completed/blocked/retest, unverified and
verified results, stale/invalid/failed evidence, provenance and false DONE guards.
Unit tests also cover loss of transport and changed-project responses.

Production and development launch checks assert exactly one BrowserWindow and
isVisible() true. Captured Electron pages are visually inspected; the native
Windows picker is supplied a fixture path, and human interaction/OS desktop
visibility is not claimed from those assertions.

Responsive geometry is checked in Electron at 1320x880, 1050x740 and 760x540.
Permission controls remain reachable in the scrolling panel, cards have no
horizontal overflow, the fixture banner stays visible, and verification keeps
a usable scroll area. Medium/small widths use the existing expandable overlay.
Dark navy surfaces, blue/violet accents and the static orbit/logo are preserved.
Screenshots are stored under ignored .packaging/phase7-validation/.

## Security checks

Electron assertions retain contextIsolation=true, nodeIntegration=false,
sandbox=true and webSecurity=true. Renderer require/process are unavailable.
Navigation, popup, webview and browser-permission restrictions remain in place.
IPC channels and allowed method/parameter shapes are unchanged. Permission
commands accept retained IDs only; they cannot replace arguments or select an
executable/root. New response fields have exact-key, enum, type, text and array
bounds; tests reject raw recovery command metadata and malformed evidence.
React renders text, without HTML execution. No filesystem/Node import, generic
IPC, unrestricted shell, another backend or new service was added to the UI.

## Phase boundary

Live Ollama flow remains unverified. This phase does not establish installer,
clean-machine or full product acceptance; existing release artifacts predate
Phase 7. Backend source and the static logo remain unchanged. No dependency
installation, commit, push or Phase 8 work was performed.