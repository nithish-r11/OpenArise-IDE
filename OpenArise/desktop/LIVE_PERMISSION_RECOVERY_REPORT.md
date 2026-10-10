# Final live Python workflow acceptance

Date: October 9, 2026. Scope: the six requested source-application workflows.

**VERIFIED** with real local `qwen2.5-coder:7b`, the visible Electron application,
production renderer/preload/main/stdio/backend, registered filesystem/test tools,
recovery engine and CompletionGate. No inference or backend response fixtures
were used. No new product features were added.

## Actual results

| Requested check | Acceptance | Observed result |
| --- | --- | --- |
| Inspect actual project | VERIFIED | Qwen cited `main.py`, `math_ops.py`, `test_math_ops.py`, the real `LIVE_REAL_SOURCE` label, multiplication and both test examples. No tool execution; source hashes unchanged. |
| Missing approval and Deny | VERIFIED | No-Allow resume returned `permission_required`. Actual UI Deny returned `denied`, with `executed=false`; later resume was rejected. All source hashes and file membership unchanged; `denied_probe.py` absent. |
| Explicit Allow exactly once | VERIFIED | Actual Allow sent approval then resume for the same request/call ID. `approved_probe.py` contains exactly `print("APPROVED_ONCE")` plus newline. One executed result for that call; replay rejected without changing bytes. The write alone remained unverified. |
| Real failing test | VERIFIED | Baseline pytest exit 0; separately approved addition fault; real pytest exit 1 and persisted `TEST_FAILURE`. |
| Real recovery, retest, verification | VERIFIED | Qwen planned an implementation repair, approved write restored multiplication, fresh pytest exit 0, recovery `RECOVERED`, CompletionGate `VERIFIED`. Original tests unchanged. |
| Failed recovery and rollback | VERIFIED | Intentionally failing test preserved. Qwen read/repaired `math_ops.py`; real recovery test exited 1. Engine `ROLLED_BACK`; original pre-recovery bytes restored. Request `failure`, CompletionGate `NOT_VERIFIED`; UI explained Rolled Back and retained a failed outcome. |

The application had exactly one visible main window. Native Computer Use also
observed the current-source OpenArise window. The test asserted
`contextIsolation=true`, `nodeIntegration=false`, `sandbox=true` and
`webSecurity=true`. No Electron security settings or IPC capabilities changed.

## Evidence

Final run directory:
`desktop/.packaging/live-permission-recovery-1791526140015/`.

`evidence.json` records eight verified checks (including launch and separate
failure detection), 33 actual backend commands, exact approval request/call IDs,
timestamps, backend responses/events, source bytes and SHA256 values at every
response, and rendered UI text. `fixtureResponses=false`; every backend response
was required to have `source=backend`.

Success request: `96a93a1d-2830-4c0d-a773-7e654f1b3220`.
Its original requirement ID remains
`f145f8ee-f609-4958-9b92-fbb7a31f7a2d` throughout the evidence.
Actual test sequence: call `2` exit 0; call `4` exit 1; recovery retest
`rec_30478a76ff6d4e4cad3b2267212d6e73_retest` exit 0. Old passing proof was marked
stale and superseded; failed proof was resolved through the actual recovery link;
fresh passing proof was accepted by CompletionGate. Rendered UI text recorded
“Completed · verified” and “Verified.”

Failure request: `17067c71-9d3f-4fa5-a6d6-2917aded8c55`.
Original requirement ID:
`13fbde32-e294-4f79-bb43-194d63df2cfb`.
Initial test call `2` and recovery test
`rec_7a79b1aeee0a4d038077fe7c60892db8_2` both exited 1.
Intermediate snapshots show a real change to `return a * b`. Final bytes match
the pre-recovery checkpoint containing `return a + b`, SHA256
`f6d151f08f57894dd6a1db9d1ac9c51c69245c8c8b25989d0a130aaf0c79956d`.
This rollback restores the failed state immediately before recovery, rather than
undoing the earlier approved intentional fault. Both original test files were
preserved. Rendered UI text recorded “Failed” activity and “Rolled Back,” with the
explanation that recovery failed and the request remains failed.

Screenshots are retained alongside the JSON. Some captures from this run precede
Chromium's final compositor paint; the final statuses above are substantiated by
the recorded rendered DOM text and backend replies. The capture helper now waits
for animation frames before taking future screenshots. No image was edited or
used to fabricate a final state.

## Failure found and fixed

The pre-fix live run is preserved at
`desktop/.packaging/live-permission-recovery-1791525209530/`.
Inspection, missing approval, Deny and one-time Allow passed, but the recovery
plan targeted `test_math_ops.py`. The acceptance driver refused approval;
original assertions were not overwritten.

Root cause: recovery planning received failure output and diagnosis without fresh
project source observations. The pytest traceback named the test, while the actual
imported implementation was absent from planning context. A system instruction to
preserve tests was also not backed by a direct test-write guard.

Repairs in the existing architecture:

- `RecoveryPlanner` now reads current contained, bounded, redacted source context
  after the failure. It uses the existing scanner/context builder and is bound to
  the orchestrator's project root. It does not reuse the pre-mutation source or
  replay completed fault instructions.
- Planner instructions identify test tracebacks as checks and require following
  actual imports to the implementation.
- Both recovery entry points block direct writes/edits to recognized test paths,
  test fixtures and pytest configuration before permission or mutation. Unsafe
  plans return BLOCKED; paths are never silently rewritten to a guessed target.
- Eight regressions verify fresh source bytes and imports, secret exclusion,
  preserved tests and blocked test-path rewrites, including Windows separators.

Two earlier inspection attempts are retained in directories ending
`1791525025302` and `1791525128590`. The first response omitted two requested
filename citations; the next returned correct citations/facts but exposed an
incorrect QA wording matcher. The prompt and matcher were corrected; the final
run retained all source-byte, permission, execution and gate assertions.

## Regression validation after the repair

| Check | Result |
| --- | --- |
| New recovery-source safety regressions | 8 passed |
| Full desktop `npm test` | **330 passed**: 276 Vitest in 23 files plus 54 Python host; 0 failed |
| Full backend pytest | **244 passed**, 0 failed, 74.58 seconds |
| `npm run build` | PASSED; existing non-failing Monaco chunk-size advisory |
| Final real Qwen acceptance | VERIFIED, process exit 0 |

Full suites were rerun because backend code changed. Only the QA capture helper
and documentation changed afterward; no additional application changes were made.

## Changes made in this task

- `ai-engine/app/agent/orchestrator.py`
- `ai-engine/app/recovery/planner.py`
- `ai-engine/app/recovery/engine.py`
- `ai-engine/tests/test_recovery_source_safety.py` (new)
- `desktop/tests/electron-live-permissions-recovery.cjs` (new)
- `desktop/LIVE_PERMISSION_RECOVERY_REPORT.md` (new)
- `desktop/PERMISSION_SAFETY_REPORT.md` (follow-up link)
- `desktop/PRODUCT_IMPROVEMENT_REPORT.md` (follow-up link)

## Scope and preserved work

Only native folder choices and explicit, bounded UI approval decisions are supplied
by the QA driver. Projects, files, model output, failures, recovery, pytest results,
evidence and gate outcomes are real. The negative missing-approval/replay probes
use the existing narrow preload boundary. Activity comes from returned events,
with no simulated streaming or percentages.

The run used an isolated QA profile, production renderer assets, no debug flags or
Vite server, and the existing timeout override of 600 seconds for local inference.
It does not establish default-timeout performance, packaged acceptance, signing,
installer or clean-machine acceptance for this source. Release artifacts were not
rebuilt. No blanket production-ready or whole-product completion claim is made.

Existing unrelated work and the original interrupted permission-incident project
were preserved. `.gitignore` remained unstaged and unchanged, SHA256
`B5893FFA2C0F626837062FEA61A5AC23854059B87F6FFEEFB49A944258C4A4A6`.
No dependencies were installed, and nothing was staged, committed or pushed.
