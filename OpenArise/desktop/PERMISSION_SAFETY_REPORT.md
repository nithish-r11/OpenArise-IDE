# Permission safety regression audit

Date: October 9, 2026. Scope: the reported unapproved AI write. No commit,
push, dependency installation or release rebuild was performed.

Subsequent real-Qwen source validation completed the missing-approval, Deny,
one-time Allow, successful recovery/gate and failed recovery/rollback checks.
See [LIVE_PERMISSION_RECOVERY_REPORT.md](LIVE_PERMISSION_RECOVERY_REPORT.md).
The fixture-only results below remain the historical permission repair audit.

## Result and limits

**VERIFIED: source permission regressions and real Electron/backend file operations.**
Denied, missing, stale, invalid and revoked approvals cannot execute the tested
actions. Exact Allow creates the intended file once. These checks use deterministic
model inference with production permission, backend and filesystem components.
They do not establish renewed live Qwen or packaged acceptance.

The earlier live incident left `denied_probe.py` containing `print(123)` without
an observed Allow action. The application and its in-memory request state were
gone after the interrupted session. No retained decision audit establishes its
exact execution chain. The defects below were independently reproduced before
the fix; attributing that original incident to one specific defect remains
**NOT VERIFIED**. Its disposable project and all four file hashes were preserved.
Further live approved-change and recovery acceptance remains **BLOCKED** pending
a new live validation run; it was not resumed during this repair.

## Permission flow

1. React `useAI` sends a request through `BackendClient`.
2. The frozen preload bridge admits only allowlisted methods. Approval, denial
   and resume accept request ID and tool call ID, not executable paths or new
   action arguments.
3. Electron main checks the trusted window/frame, request shape, current project
   scope and unsaved-buffer execution guard.
4. `DesktopBackendService` and the workspace adapter send the command to the
   supervised Python `agent_host` stdio transport.
5. `BackendService` dispatches through `ProjectWorkspaceService` to
   `AgentOrchestrator`. Production host construction uses
   `PermissionManager(test_mode=False)`.
6. The orchestrator retains the generated action. Allow records a decision for
   that pending request/call. Resume uses the retained action. Deny/cancel revoke
   approval and stop the pending workflow.
7. Registered tool risk is authoritative. WRITE/EXECUTE require both the approved
   pending action and a matching scoped grant. The grant is checked and consumed
   immediately before `tool.execute`, including recovery actions and retests.

## Reproduced defects and repairs

- Approval previously consisted of a boolean indexed only by `tool_call_id`.
  A preexisting bare grant authorized a new model action. Grants now bind request
  ID, call ID, registered tool name/risk and a canonical hash of full arguments.
  Legacy editor Save/Create grants cannot authorize agent actions.
- `test_mode=True` previously allowed agent writes without a pending decision.
  Agent WRITE/EXECUTE now require explicit scoped approval even in test mode.
  Integration tests that execute tools now approve the actual pending calls;
  their original execution, recovery and evidence assertions remain intact.
- Pending validation previously did not compare retained action arguments.
  Changing the target after Allow could spend the old approval. Validation now
  compares the retained call and registered tool; mismatches fail closed.
- Permission was checked before lifecycle callbacks and recovery checkpoints,
  but not again at execution. Revocation during those callbacks still wrote.
  Both execution paths now recheck after callbacks and consume the grant once.
- Resume now retains the approved pending decision through dispatch and requires
  it in addition to the scoped grant. A primed scoped grant alone cannot bypass
  the permission card. Completed calls clear the pending decision.
- The renderer previously accepted an approved response without matching its
  pending action to the reviewed action. It now rejects mismatched request/call,
  tool name, risk, resource, command metadata or approved flag before auto-resume.

## Validation

| Check | Actual result |
| --- | --- |
| Initial pre-fix permission regressions | **4 failed, 6 passed**; real unauthorized writes reproduced in disposable pytest projects |
| Final focused backend permission/agent/recovery suite | **60 passed**, 12.23 seconds |
| Focused desktop AI/boundary/Phase 7 tests | **68 passed**, 3 files |
| Focused Python agent-host tests | **18 passed** |
| Full desktop `npm test` | **330 passed**: 276 Vitest across 23 files plus 54 Python host; 0 failed |
| Full backend `.\.venv\Scripts\python.exe -m pytest` | **236 passed**, 0 failed, 59.07 seconds |
| `npm run build` | **PASSED**: TypeScript, renderer and Electron bundles; existing non-failing Monaco chunk-size advisory |
| Visible real Electron permission integration | **VERIFIED**; one visible window, real renderer/preload/main/stdio/backend, real file writes |
| Normal `git diff --check` | **PASSED**, exit 0; repository line-ending advisories only |

New backend regressions cover missing approval, bare and fully scoped stale
grants, test-mode bypass, wrong request/call, changed arguments/name/risk,
single-use approval, deny/cancel after Allow, late revocation, unapproved Python
execution and recovery revocation after a checkpoint. UI tests cover mismatched
approval responses. Host tests cover no-Allow resume, invalid IDs, denial followed
by a cached approval response, and stale legacy grants.

The Electron integration opens a new disposable project, checks that missing and
invalid approval do not create `unapproved.py`, then uses the actual Deny button
and confirms that neither it nor resume creates a file. Another Deny sends only
`deny_agent_action` and leaves `denied.py` absent. Actual Allow sends
`approve_agent_action` followed by `resume_agent_execution`, writes `allowed.py`
with exact expected content, and rejects replay. `original.py` remains unchanged.
The write result stays **Not verified** because no fresh test proof was supplied;
the test does not fabricate VERIFIED product completion.

Evidence is retained at:
`desktop/.packaging/permission-safety-1791524016624/evidence.json`.
Inference and native folder selection are fixtures, clearly marked as
`test_fixture` in the desktop and `fixtureInference: true` in the evidence.
Permission outcomes, execution flags, activity and file bytes are real.

## Files changed by this repair

- `ai-engine/app/tools/permissions.py`
- `ai-engine/app/agent/orchestrator.py`
- `ai-engine/app/recovery/engine.py`
- `ai-engine/tests/test_permission_safety.py` (new)
- `ai-engine/tests/test_agent_integration.py`
- `ai-engine/tests/test_hardening_security.py`
- `desktop/src/workspace/useAI.ts`
- `desktop/tests/ai-panel.test.tsx`
- `desktop/tests/test_agent_host.py`
- `desktop/tests/electron-permission-safety.cjs` (new)
- `desktop/tests/fixtures/permission-backend.py` (new)
- `desktop/PERMISSION_SAFETY_REPORT.md` (new)
- `desktop/PRODUCT_IMPROVEMENT_REPORT.md` (audit link)

Other preexisting uncommitted product changes were preserved. Generated test
evidence stays in the ignored `.packaging` directory. Nothing is staged.

## Security and preserved work

The real Electron integration asserted `contextIsolation=true`,
`nodeIntegration=false`, `sandbox=true` and `webSecurity=true`.
The existing narrow IPC, project containment, unsaved/conflict safeguards,
dependency-installation prohibition, recovery engine, evidence system and
CompletionGate remain in place. No renderer Node/filesystem/process access,
generic IPC or shell capability was added.

The local `.gitignore` remained unstaged with SHA256
`B5893FFA2C0F626837062FEA61A5AC23854059B87F6FFEEFB49A944258C4A4A6`.
`package-lock.json` and user projects were not modified. The original incident
project `desktop/.packaging/live-final-fe98cdee12fd4da0956205cfcc64a774` was only
read to confirm the three original hashes and the observed probe hash remained
unchanged. No reset, restore, checkout or deletion of user work was performed.
