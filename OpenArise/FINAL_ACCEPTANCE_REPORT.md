# Final failure-path UI acceptance

Review: **October 8, 2026 (Asia/Calcutta)**. Recorded validation timestamps retain
actual October 7–8 dates. This section supersedes the historical report below.

**Targeted functional product acceptance: VERIFIED.** The latest installed
packaged application really completed both live Qwen cases and displayed the
corresponding results. **Distribution acceptance: BLOCKED** by this latest ZIP's
Application Control policy and current mandatory MSI validation (LGHT1105).
Publisher signing and clean-machine validation remain NOT VERIFIED.
No fully production-ready claim. No commit or push.

## Investigation and exact fix

The supplied `<actual result>` strings were placeholders in the human-check
replies, not established renderer output. Inspection of the production AIPanel,
useAI, validators, Python projection/host and Electron adapter found the actual
failure DTO already intact: failure / FAILED / ROLLED_BACK / NOT_VERIFIED. No
production demo/placeholder backend fallback was found or replaced. Input hints
and clearly labelled test fixtures remain appropriate.

The observed UI defect was **ROLLED_BACK grouped under "Recovery attempted"**.
The verification header also used a generic derived failure label rather than
the exact returned gate enum. RecoveryCard now treats ROLLED_BACK as failure,
shows **Recovery rolled back**, and retains the actual backend status/retest
message. VerificationCard shows the exact gate status and actual backend/action
states, marking retained values as earlier observations after transport error.
The existing defensive completion rule is unchanged: only consistent successful
execution plus CompletionGate VERIFIED can show a verified final result.
No backend/DTO/projection rewrite was necessary.

External QA also needed correction: it now waits for the matching request's
actual settled result/enum/idle controls, brings the QA window forward and waits
for painted frames. Earlier pending compositor frames are not final-state proof.
A heading assertion now tolerates the existing CSS uppercase rendering without
changing exact backend-enum assertions. WMI can omit a portable image path; the
native observer uses the exact Get-Process.Path fallback and retains the same
one-main/one-visible/one-renderer assertions.

## Real packaged evidence

Primary evidence:
`desktop/.packaging/failure-ui-fix/packaged-ui-1791388991512/evidence.json`.
The actual freshly installed application's isPackaged=true, current app.asar
path and secure preferences were inspected. Real renderer → preload → main →
bundled Python host → BackendService → AgentOrchestrator → OllamaProvider used
**qwen2.5-coder:7b**. All recorded IPC response sources are backend.

The external QA controller used a loopback Node inspector, an isolated profile
and supplied disposable folder-picker paths, then clicked existing UI controls.
It recorded unchanged real responses; no AI/provider/tool/evidence fixture.
Normal source/portable/installed launches were separately checked without these
QA flags. This is automated actual packaged UI validation, not a new
human-operated native-picker check.

| Case | Real result and corresponding renderer state |
| --- | --- |
| Deny model write | DENIED; math_ops.py unchanged |
| Approve intentional arithmetic fault, detect failure, recover, fresh retest | RECOVERED; COMPLETED; Final Result VERIFIED; CompletionGate VERIFIED, 1/1 |
| Preserve always-failing test, attempt repair, mandatory retest fails, rollback | ROLLED_BACK; FAILED; Final Result FAILED; CompletionGate NOT_VERIFIED, 0/1 |

Success request `d323cb55-ca20-4f9e-8b5c-cacc99ce33e4`, original requirement
`8d99e130-f097-473b-a7de-c19a629b0fa1`: eight real evidence records, four actual
test-tool executions and one recovery attempt. Baseline test proof
`263f0215-22f8-4f12-ac06-34932d9bac05` is stale/superseded. The real failed proof
`25b8b946-06b2-456d-8cf8-da703d8bbc51` remains linked to fresh mandatory passing
retest `e1b4fc06-51e6-4799-a09a-cfa7fd0d77a6`, exit 0. Requirement identity and
original tests are preserved; stale proof is not used as fresh passing proof.

Failure request `54c49e4b-bbef-449d-9896-f34e0ea9bdc1`, requirement
`f6ff4f59-c5fd-4eaa-ad86-c99450713ba4`: six evidence records, three actual
test-tool executions and one recovery attempt. The preserved deliberate failure
caused real mandatory pytest exit 1 and rollback. UI displays ROLLED_BACK and the
actual "Recovery retest failed. (Rolled back successfully)" message; rollback
success is not repair success. Final Result is FAILED, the gate is NOT_VERIFIED,
and failed/contradictory/changed-project evidence and remaining issues are shown.

Settled UI text and captured final outcomes were checked at **1320x880,
1050x740 and 760x540**. No placeholder/demo output or false VERIFIED appeared.
Recovery shows actual diagnosis/failing tool IDs; unavailable severity says Not
reported. Activity uses actual returned recorded events and explicitly says last
returned data/no live streaming. No invented percentages or timed lifecycle.

Failed QA attempts are retained: the first stopped at the uppercase-heading
check after real backend success/refusal; a repeat hit a real **180-second model
timeout**. The passing run used the existing supported **300-second inference
timeout environment override** for the QA app. No default or backend settings
source was changed. Hardware-dependent inference duration remains a limitation.

## Exact current validation results

| Required validation | State | Result |
| --- | --- | --- |
| Full desktop tests | VERIFIED | **271 passed**, 0 failed = **234 Vitest** in 20 files + **37 Python host** |
| Full backend tests | VERIFIED | **188 passed**, 0 failed, **43.02 seconds** |
| Production build | VERIFIED | TypeScript/Vite/Electron; existing non-failing Monaco size warning |
| Production Electron smoke | VERIFIED | Real editor/save/conflict/Python/pytest/sessions/responsive/security/shutdown; AI fixtures labelled |
| Development Electron smoke | VERIFIED | Same real local operations and explicit AI fixtures; cleanup passed |
| Normal npm start | VERIFIED | Exactly one visible OpenArise main window/main process/renderer; no debug/Vite/profile override; normal close |
| Normal npm run dev | VERIFIED | Exactly one visible OpenArise main window/main process/renderer; managed dev server; normal close |
| Rebuilt ZIP | VERIFIED contents/runtime; BLOCKED launch | Fresh source matches; normal launch denied by actual Application Control |
| Rebuilt portable EXE | VERIFIED | Latest wrapper normal no-flag one-window launch; current payload/runtime validated |
| Rebuilt NSIS | VERIFIED on this host | Ordinary per-user install, current runtime, normal launch, both live UI cases, normal uninstall exit 0 |
| Fresh MSI mandatory validation | BLOCKED | WiX LGHT1105: Validation could not run due to system policy; light exit 1105/npm exit 1; no validated MSI |
| Publisher signing / clean Windows host | NOT VERIFIED | EXEs unsigned; no certificate or clean second host/VM available |

All three available release artifacts were rebuilt after the fixed source's
full suites/build/smokes. Each has the same current ASAR hash
`C62E0C24EA3FFBD8A9CB27C15DD179C1694D5F18D1C855669803EB8599282425`.
All 77 backend/five host modules and compiled/static files match current source.
Each actual bundled runtime passed imports/read/save/project/environment/Python/
pytest (1 passed) with PATH=System32 and no external PYTHONHOME/PYTHONPATH.
No development dependencies, secrets, caches, logs or project/test garbage are
included. See [desktop/RELEASE_VALIDATION.md](desktop/RELEASE_VALIDATION.md) for
current artifact sizes/hashes, policy events and exact evidence scopes.

Latest ZIP block: Enterprise signing policy
`{0283ac0f-fff1-49ae-ada1-8a933130cad6}`, Code Integrity 3033/3077, October 7
20:44:11.901 / 20:44:13.370 +05:30. No alternate caller, rename, debug launch or
policy bypass on the blocked ZIP. Separately built portable and installed NSIS
actually launched normally; old policy outcomes are not substituted for current
results. NSIS uninstall removed the owned QA executable and registration normally.
Fresh MSI retained mandatory `-pedantic -wx` validation and failed LGHT1105.
No ICE suppression, admin retry or policy change; MSI install/launch/uninstall
remain NOT VERIFIED. See desktop/.packaging/failure-ui-fix/msi-build.log.

## Exact files changed for this targeted task

1. `desktop/src/components/AI/RecoveryCard.tsx` — exact rolled-back failure presentation/status.
2. `desktop/src/components/AI/VerificationCard.tsx` — actual verification enum/backend/action states.
3. `desktop/tests/failure-result.test.tsx` — four labelled fixture UI/provenance regressions.
4. `desktop/tests/test_recovery_projection.py` — two deterministic-provider regressions using real permissions/files/pytest/backend projection; not live-model proof.
5. `desktop/tests/packaged-live-ui.cjs` — external actual packaged UI/model release QA; never packaged or exposed through IPC.
6. `desktop/scripts/observe-windows-launch.ps1` — exact native path fallback for WMI omissions; existing assertions retained.
7. `desktop/README.md` — current UI/release behavior and scope.
8. `desktop/RELEASE_VALIDATION.md` — current evidence/hashes/limitations.
9. `FINAL_ACCEPTANCE_REPORT.md` — this report; previous results preserved below.

Generated ignored outputs: new ZIP/portable/NSIS artifacts, release SHA256SUMS.txt
and RELEASE_NOTES.txt, and current .packaging/failure-ui-fix QA evidence. These
are not staged. Earlier uncommitted desktop/backend changes are preserved; this
list describes only the current targeted work.

## Final acceptance scope and preservation

The functional UI acceptance rule is satisfied by actual packaged recovery
success, actual failed-recovery refusal, no production placeholder output and
fresh rebuilt distributables containing the fixed UI. Distribution/clean-host/
signing limitations above prevent an unrestricted production-readiness claim.

All **77 backend module hashes** match the task's initial baseline; existing
backend tests/changes are untouched. Electron contextIsolation=true,
nodeIntegration=false, sandbox=true, webSecurity=true were observed in the actual
package. Narrow IPC, sender/page checks, controlled command grammar, main-owned
filesystem/model access and the same production backend architecture remain.
No dependency installation, config/lockfile/logo/.gitignore change, staging,
commit, push, branch/HEAD change, reset or user-work discard. Branch main and HEAD
2543fd185e54f2e39c5e0697ee0fd1d1a66982f5 are retained.
<details>
<summary>Historical acceptance checkpoints — superseded by the current targeted report</summary>

# Final release acceptance — October 6, 2026

Final review completed October 7, 2026 (Asia/Calcutta). Execution/test/package
timestamps below are the recorded October 6 checks, not new October 7 reruns.

**Final release acceptance: BLOCKED.** The latest portable wrapper is blocked by
Windows Application Control; MSI required validation is blocked by system policy.
Direct packaged failure UI remains NOT VERIFIED; no actual human result was
reported. No commit or push.
This section supersedes the earlier acceptance checkpoint retained below.

## Latest final regression and source launches

| Required check | State | Result |
| --- | --- | --- |
| Full desktop npm test | VERIFIED | **265 passed**, 0 failed: 230 Vitest in 19 files + 35 Python host |
| Full backend pytest | VERIFIED | **188 passed**, 0 failed, 25.91 seconds; all original 161 retained |
| npm run build | VERIFIED | TypeScript, Vite and Electron bundles; existing non-failing Monaco size warning |
| Production Electron smoke | VERIFIED | Rerun on final production source; actual file/Python/pytest paths; AI fixtures clearly labelled; cleanup passed |
| Development Electron smoke | VERIFIED | Rerun after the final activity fix; same real local operations and explicit AI fixtures; cleanup passed |
| Plain npm start | VERIFIED | Exactly one native visible OpenArise main window, one main process and one renderer; no debug flags, Vite or profile override; normal close |
| Normal npm run dev | VERIFIED | Exactly one native visible main window/main process/renderer; managed dev script/server; no debug port or profile override; normal close |

## Fresh packages and real bundled AI

All release targets were rebuilt **after** the final source suite/build/smokes.
Earlier wrappers/hashes are not presented as these final artifacts. No publishing.
The compiled ASAR remains byte-identical to the already validated source build.

| Check | State | Observed result |
| --- | --- | --- |
| Latest ZIP build/extract/contents/runtime | VERIFIED | 1,592 files, 16 ASAR entries; all 77 backend/five host source files match current checkout; actual bundled read/save/Python/pytest |
| Latest ZIP normal launch | VERIFIED | One visible OpenArise window, one main and one renderer; no debug flags, Vite or user-data override |
| Latest portable build/payload | VERIFIED | 1,593 files; every ZIP file matches byte-for-byte; only standard resources/elevate.exe extra; actual bundled runtime checks pass |
| Latest portable wrapper normal launch | BLOCKED | Normal Start-Process returned Application Control policy block; Code Integrity 3077 confirms Enterprise signing policy; no bypass |
| Latest NSIS install | VERIFIED | Standard per-user silent installation into isolated QA workspace directory; exit 0; no prior install/shortcuts overwritten |
| NSIS installed contents/runtime | VERIFIED | 1,594 files; current backend/host/bundles; actual bundled read/save/Python/pytest pass |
| NSIS installed normal launch | VERIFIED | Exactly one visible OpenArise main window/main process/renderer, no debug flags or Vite |
| NSIS normal uninstall | VERIFIED | Original per-user uninstaller exit 0 after normal guarded close; installed executable and registration removed; no forced removal |
| MSI required ICE validation | BLOCKED | Actual current attempt: WiX LGHT1105, Validation could not run due to system policy; no suppression or admin/policy bypass; no validated MSI produced |
| Human packaged open/edit/save/run/test | VERIFIED by user report | User replied All five steps work in the portable UI; its payload matches the final compiled app/runtime; raw output was not collected from this human exercise |
| Bundled real Qwen recovery / fresh evidence / gate | VERIFIED | Real latest ZIP Python/host/BackendService/model; RECOVERED, actual fresh pytest exit 0, CompletionGate VERIFIED 1/1 |
| Bundled real Qwen failed recovery refusal | VERIFIED | Actual attempt, mandatory pytest exit 1, ROLLED_BACK, lifecycle FAILED, CompletionGate NOT_VERIFIED 0/1 |
| Direct packaged UI AI success | VERIFIED by user report | In the installed application: Final Result VERIFIED, Recovery SUCCESS, CompletionGate VERIFIED; exact reported labels retained, no raw renderer capture/proof IDs from this human exercise |
| Direct packaged UI failed recovery refusal | NOT VERIFIED | Human failure check requested in the latest ZIP; replies contained placeholders, not actual values; bundled host API evidence does not replace this check |

Success evidence: `desktop/.packaging/final-acceptance/packaged-live-1791297630488/evidence.json`.
Interpreter is inside the fresh extracted ZIP, with PATH=System32 and no
PYTHONHOME/PYTHONPATH. No provider, backend response or execution fixture.
Original requirement `f4dff277-81c2-4f33-9b0c-1a9c03864b00` retained; 7 actual
evidence records, 3 test-tool executions, one recovery attempt. Baseline proof
became stale/superseded; failed proof was retained and linked to fresh mandatory
retest proof `888c40d8-4eed-4e50-9f19-b83be53cdc8d`. Original tests unchanged.

Failure evidence: `desktop/.packaging/final-acceptance/packaged-live-1791298012946/evidence.json`.
Requirement `058e28a2-15d6-4e67-9c3e-b8273c936e11`; 6 evidence records, 3 test-tool
executions, one attempt. The intentionally failing test was preserved. A scoped
model-proposed test could not replace the mandatory whole-project retest. The
failed retest caused real rollback and gate refusal, never VERIFIED.

Native ZIP/installed first observations timed out at 30 seconds. Windows
subsequently appeared without changing the launch configuration; a second
observation confirmed exactly one. A later ZIP launch was captured minimized;
normal reopening restored the complete workspace and retained one main window.
The restored full window was visually inspected. No timeout/assertion was
weakened. These timing and minimized-window observations remain recorded.

Latest portable normal launch on October 6 at 20:31:52–53 +05:30 was rejected
with “An Application Control policy has blocked this file.” Code Integrity
events 3033 and 3077 identify Enterprise signing requirements and Policy ID
`{0283ac0f-fff1-49ae-ada1-8a933130cad6}`. The latest wrapper did not launch;
earlier portable user confirmation is not reused as this wrapper's launch proof.
Its offline payload comparison remains valid. ZIP and NSIS are separately built
targets and were tested normally; no blocked executable or policy was bypassed.

## Artifacts, security and evidence

See desktop/RELEASE_VALIDATION.md for final sizes/hashes and package evidence.
Current source and basic packaged runtime are verified on this existing Windows
host. Publisher signing and clean Windows VM/second-host acceptance remain
NOT VERIFIED; no signing certificate/clean VM was available. The historical
October 4 Application Control blocks do not describe current NSIS behavior:
this current installer actually installed and launched successfully.

Approval review became available again for this final task; the earlier usage
limit no longer blocks execution. Remaining MSI block is actual WiX system
policy, not automatic approval review. No validation/security/policy bypass.
contextIsolation=true, nodeIntegration=false, sandbox=true, webSecurity=true,
strict allowlisted IPC, fixed hosts and controlled command grammar are unchanged.
No backend/source refactor or application-code change in this final acceptance
pass; only the existing packaged QA helper and documentation were updated.
No dependencies, package-lock, logo, security sources, .gitignore, branch or HEAD
were changed. No staging, commit, push, reset or discard.

Logs/native captures/current manifests are under ignored desktop/.packaging/:
`final-release-desktop-tests.log`, `final-release-backend-tests.log`,
`final-release-build.log`, both `final-release-*-smoke.log`, target build logs,
`final-release-packaged-recovery.log`, `final-release-packaged-failure.log`, and
`final-release/` native observations/content/hash/human records.

## Current final acceptance checklist

| Required acceptance | State |
| --- | --- |
| Full desktop suite, 265 tests | VERIFIED |
| Full backend suite, 188 tests | VERIFIED |
| Production build | VERIFIED |
| Latest production Electron smoke | VERIFIED |
| Latest development Electron smoke | VERIFIED |
| Normal npm start, one visible usable main window | VERIFIED |
| Normal npm run dev, one visible usable main window | VERIFIED |
| Latest release rebuild after final source validation | VERIFIED |
| Latest ZIP extraction, contents/runtime, normal launch and reopen/focus | VERIFIED |
| Latest portable current embedded source/runtime | VERIFIED |
| Latest portable normal wrapper execution | BLOCKED, current Enterprise signing policy |
| Latest NSIS install, installed contents/runtime, normal launch and uninstall | VERIFIED on this host |
| Current MSI required validation | BLOCKED, LGHT1105; no validated MSI |
| Real packaged Qwen request, permission, mutation, failure, repair and fresh retest | VERIFIED at bundled backend API; success UI also user-reported |
| Original requirement/evidence freshness and CompletionGate VERIFIED | VERIFIED from actual returned records |
| Packaged failed recovery refuses VERIFIED | VERIFIED at bundled backend API; direct renderer outcome NOT VERIFIED |
| Human packaged project open/edit/save/Python/pytest | VERIFIED by user report; byte-identical application/runtime |
| Direct human packaged success Final Result/Recovery/CompletionGate | VERIFIED by user report, exact labels recorded |
| Direct human packaged failed-recovery final UI | NOT VERIFIED; placeholders cannot establish outcome |
| Current responsive UI, safeguards, controlled execution and shutdown regressions | VERIFIED; fixture AI states distinguished from live acceptance |
| Security/static identity/lockfile preserved | VERIFIED |
| Publisher signing and clean Windows host | NOT VERIFIED |
| No staging, commit, push or discarded user work | VERIFIED |

The required final release checks are not all satisfied. The latest ZIP was left
open for the human check; no OpenArise main process remained at final observation.
No forced close or work discard was performed. No fully complete
or production-ready declaration. Only the packaged QA helper and requested
documentation were changed during this final acceptance pass; earlier backend
and desktop fixes listed below were preserved.

A final read-only comparison still matched all 77 backend modules, five desktop
host modules and 11 compiled/static files in both ZIP and portable payload to the
current checkout. No application changes followed the validated build.

<details>
<summary>Earlier source recovery checkpoint and superseded release observations</summary>

The following preserves earlier root causes, source proof and complete changed
file list; its pending release statements are superseded by the current table.

# Final live recovery and verification acceptance — 2026-10-06

**Live source-app recovery and CompletionGate verification: VERIFIED.**
**Full product/release acceptance: NOT VERIFIED.** Latest ZIP launch, packaged workflows and a
settled live failure UI capture still require validation. No commit or push.

## Actual live results

The primary probe launched one visible actual Electron window and used real
`qwen2.5-coder:7b` at `127.0.0.1:11434`. It supplied only a disposable project
folder-picker result and an isolated QA profile. Existing IPC handlers were
observed, called unchanged, and their real responses returned unchanged. No AI
provider, backend response, test result, recovery outcome or evidence was mocked.
Requests followed renderer → preload → main → BackendService →
AgentOrchestrator → OllamaProvider. Permissions used the production manager.

Authoritative evidence is in:
`desktop/.packaging/final-acceptance/live-1791295655369/evidence.json`.
The probe exited 0. This is a real application exercise driven by DOM/native
input, not a full human-operated native-picker workflow or a normal packaged launch.

| Case | Actual result |
| --- | --- |
| Deny a model-proposed write | DENIED; write_file executed=false; original math_ops.py unchanged; gate INCONCLUSIVE |
| Approve baseline test, intentional fault, failing test and recovery | Real mutations and pytest executions; backend diagnosis identifies addition instead of multiplication; RECOVERED, one recovery attempt |
| Fresh retest and final gate | COMPLETED/success; CompletionGate VERIFIED, 1/1 requirement; 8 evidence records, 4 actual test-tool executions |
| Mutate the verified implementation externally and refresh retained request | unverified; CompletionGate NOT_VERIFIED; stale proof rejected, UI withholds VERIFIED |
| Unsuccessful recovery | FAILED/failure; one real attempt; ROLLED_BACK after mandatory whole-project pytest fails; CompletionGate NOT_VERIFIED, 0/1 requirement |
| Responsive verified result | VERIFIED heading visibly inside the conversation at 1320x880, 1050x740 and 760x540; screenshots captured |

Successful request: `0a8d6ac5-44f8-4c34-b369-74c029cbc17b`.
Original requirement: `8034d60f-1a03-4264-b401-5526c377ec71`; all returned evidence
keeps that identity. Baseline passing proof became stale and superseded after
mutation. Failed proof `495cf6de-fa18-40d6-b6e3-f840c3741a9e` remains in the
ledger, linked to fresh mandatory retest proof
`2c0d44b2-b02e-4b39-b1c5-39cb21b8a9bc` and real recovery record
`5cc2b518-8200-4a00-9a16-03bb0c003b35`. The retest tool returned executed=true,
success=true, exit_code=0. These are returned records, not synthetic fixture IDs.

Failed request: `238e81e9-658c-49ec-8112-f83515814780`. The disposable project also
contains an intentionally failing `test_unrecoverable.py`. Its assertion and the
original multiplication tests remained unchanged. Qwen's proposed scoped test
passed, but the engine's mandatory whole-project retest returned exit 1. Recovery
rolled back and the gate refused completion. A scoped passing test could not hide
the remaining failure. The model's root-cause summary is retained as a diagnosis,
not treated as proof that every failure was fixed.

The verified screenshots were visually inspected. Inspection of `failure.png`
found an earlier approved/pending frame, not the settled final FAILED view. Its
backend outcome is proven; its settled final live UI is **NOT VERIFIED**. The
probe now waits for the matching request, final failure message/state, idle
controls and absence of pending permission actions. That stricter probe passes
syntax validation but has not been rerun. Existing unit/fixture smoke tests cover
the FAILED rendering; they do not replace the missing live capture.

## Root causes and fixes

1. The desktop originally inherited `llama3`, while only `qwen2.5-coder:7b` was
   installed. Actual generation returned HTTP 404. DesktopSettings now selects
   the installed model through existing settings/env architecture; standalone
   defaults remain compatible. Exact model checks, safe distinct errors, bounded
   diagnostics, answer-only output and automatic bounded context loading were
   added in the preceding integration fix.
2. Recovery execution did not retain resumable exact-tool permission state or
   expose its actual result to the desktop. The existing recovery engine now
   retains the actual plan, checkpoints approved writes, pauses for each ASK,
   executes registered tools, revokes one-use approval, runs a mandatory pytest
   retest and returns actual recovery/failure/rollback state. Existing legacy
   recovery entry points remain compatible; no second recovery engine was added.
3. Recovery prompts included completed intentional-fault instructions inside
   failure evidence. Actual Qwen plans repeated them, causing real failed
   recovery. Planning now receives failure facts and diagnosis without that
   completed user_request field. Repair code still comes from real Qwen.
4. Rapid same-size source rewrites could reuse timestamp-valid .pyc and make
   pytest test old code. Actual test execution uses a fresh temporary bytecode
   namespace, with bytecode writes disabled. A passing baseline cannot mask a
   newly introduced fault.
5. Evidence needed project freshness and a verifiable recovery resolution.
   Source/test/config fingerprints are captured around actual pytest and checked
   by verification. Failed evidence is retained. Only linked real RECOVERED,
   fresh DIRECT TEST_PASS and actual executed passing retest for the same original
   requirement can resolve it. Changed retained requests are reevaluated through
   CompletionGate; restoring old bytes does not resurrect invalidated proof.
6. Desktop projection/DTOs expose bounded failure/recovery summaries and safe
   resolution IDs, withholding raw code/output/arguments/fingerprints. Final
   presentation still requires consistent backend VERIFIED gate and completed
   action, with no unresolved failure or active stale proof. RETESTING and
   recovery outcomes use actual returned events; later outcomes are not attached
   to earlier attempts. No live streaming or progress percentages are invented.
7. Package validation now compares every bundled backend/desktop-host source
   byte against the current checkout in addition to compiled bundles and identity.

## Final validation

| Check | State | Exact result/scope |
| --- | --- | --- |
| Full npm test | VERIFIED | 230 Vitest in 19 files + 35 Python host = **265 passed**, 0 failed |
| Full backend pytest | VERIFIED | **188 passed**, 0 failed, in 53.76 s; original 161 + 19 prior Ollama + 8 recovery regressions |
| npm run build | VERIFIED | TypeScript, Vite and Electron bundles passed; existing Monaco size warning only |
| Production Electron smoke | VERIFIED | Passed after final production-source changes; real editor/file/Python/pytest paths and clearly labelled AI fixtures; shutdown cleanup passed |
| Development Electron smoke | VERIFIED for its tested revision | Passed during this task before the final activity timestamp presentation fix; final rerun NOT VERIFIED |
| Real live Qwen success/stale/failure backend flow | VERIFIED | Actual IPC, model, permissions, writes, failures, recovery, retests and CompletionGate results above |
| Full npm run test:real editing/conflict/close/reopen rerun | NOT VERIFIED for latest revision | Passed in the preceding October 6 integration task; not rerun after recovery changes |
| Normal npm start / npm run dev rerun | NOT VERIFIED for latest revision | Preceding October 6 normal source launches each showed one native visible window; latest rerun pending |
| Stricter live failure UI probe | NOT VERIFIED | Corrected after screenshot review; node --check passed; full rerun pending |
| Packaged live recovery probe | NOT VERIFIED | Source helper added and syntax checked; not executed |

New focused regressions: eight backend recovery tests use deterministic model
plans with real files and real pytest; thirteen desktop tests use explicit
fixtures for resolution links, stale/foreign/missing evidence, failed recovery,
Gate refusal, RETESTING and recorded activity. Existing approval/denial/cancel
and duplicate prevention tests remain. These fixtures do not prove live model
behavior; the separate primary live run provides that evidence. Original test
assertions/timeouts were not weakened. An initial heavily concurrent desktop
run hit four test timeouts; an unchanged rerun passed all 265.

Logs are under ignored `desktop/.packaging/`: `final-desktop-tests.log`,
`final-backend-tests.log`, `final-build.log`, `final-production-smoke.log`,
`final-development-smoke.log` and the three `final-package-*.log` files.

## Latest packages

All three Windows targets were rebuilt after final application changes, using
existing tooling and `--publish never`. They replace the old artifact hashes;
old Phase 8 launch evidence does not prove these new packages launch.

| Artifact | Build | Current validation |
| --- | --- | --- |
| OpenArise-0.1.0-win-x64.zip | VERIFIED, 171,404,848 bytes | Extracted; ASAR/executable match final unpacked build; all 77 backend and 5 host source files match; latest normal Electron launch NOT VERIFIED |
| OpenArise-0.1.0-win-x64-portable.exe | VERIFIED, 112,859,978 bytes | Normal wrapper started; user confirmed exactly one visible OpenArise window; all 1,592 ZIP files match extracted payload, plus standard elevate.exe; interactive workflow NOT VERIFIED |
| OpenArise-0.1.0-win-x64-setup.exe | VERIFIED, 126,888,734 bytes | Standard NSIS build completed; latest install/installed launch/uninstall NOT VERIFIED |
| MSI | NOT VERIFIED | Not rebuilt in this task; previous required ICE validation was policy-blocked |

The current unpacked package passed clean-content/identity validation, isolated
bundled imports, real read/save, backend project/environment, controlled Python
and real pytest (1 passed), with PATH=System32 and no PYTHONHOME/PYTHONPATH.
It contained 1,592 files/16 ASAR entries at validation. Backend/host source bytes
were current. Later NSIS staging added its standard elevation helper; current
ASAR/executable still match the extracted ZIP byte-for-byte. This is runtime
module validation, not an interactive packaged Electron/Ollama workflow.

Current portable visible launch is **VERIFIED by user observation**, not a new
Windows-policy block. Start-Process launched the normal wrapper; the user replied
"One OpenArise window is visible." Process checks could not expose a window
handle and CIM inspection was access-denied; user observation supplies the visible
window evidence. A read-only comparison of the payload already extracted by the
actual launch found every one of the 1,592 ZIP files byte-identical, plus only
resources/elevate.exe (the standard packaging helper). No privileged archive
listing or policy bypass was used. Packaged project/live recovery workflows are
still NOT VERIFIED. No current CodeIntegrity block was established.
Historical October 4 portable/Setup Application Control blocks and MSI LGHT1105
are preserved in RELEASE_VALIDATION.md, clearly labelled historical.

## Approval-review blocker

A privileged archive-listing request was not executed because automatic approval
review failed at the account usage limit. The tool explicitly said this was a
review failure, not a decision that the action was unsafe. It reported a reset
at October 7, 2026 12:00 AM. No approval check or Windows policy was bypassed.
Further privileged launch/package checks remain BLOCKED until review is available.
Read-only byte checks and documentation continued; earlier approved builds/tests
were polled to their actual completions.

## Final acceptance checklist

| Required acceptance | State |
| --- | --- |
| Real Ollama model requests through existing architecture | VERIFIED in actual source Electron app |
| Real permission required/denial blocks mutation/approval executes intended mutation | VERIFIED in disposable live projects |
| Intentional failure detected | VERIFIED, real pytest exit 1 |
| Recovery planning and execution actually attempted | VERIFIED, real Qwen plan and registered tools |
| Controlled recovery succeeds | VERIFIED, backend RECOVERED |
| Retest executes and fresh evidence accepted | VERIFIED, mandatory real pytest exit 0 |
| Requirement identity preserved; failed/stale evidence cannot independently satisfy gate | VERIFIED by actual records, mutation check and focused regressions |
| CompletionGate final authority returns VERIFIED | VERIFIED, 1/1 requirement |
| Failed recovery refuses VERIFIED | VERIFIED at backend; FAILED/ROLLED_BACK/NOT_VERIFIED |
| Settled final failed live UI explains outcome | NOT VERIFIED after screenshot timing defect; regression/fixture rendering verified |
| Activity uses real recorded states, no invented streaming | VERIFIED in source live flow and regressions |
| VERIFIED UI at all three requested sizes | VERIFIED |
| Current full desktop/backend suites and production build/smoke | VERIFIED |
| Final development smoke and complete file/conflict/close/reopen/normal launch reruns | NOT VERIFIED; earlier revision passed |
| Latest ZIP/portable/installer rebuilt | VERIFIED |
| Latest source/package bytes consistent | VERIFIED for ZIP/unpacked and actual extracted portable payload; installer embedded payload inspection NOT VERIFIED |
| Latest normal portable visible launch | VERIFIED by user confirmation; exactly one window, no debug flags |
| Latest normal ZIP launch, packaged live recovery and interactive workflow | NOT VERIFIED; further execution BLOCKED by approval-review availability |
| Installer install/launch/uninstall, signing and clean Windows environment | NOT VERIFIED; signing UNAVAILABLE |
| Electron security and original identity preserved | VERIFIED by unchanged boundary sources and regression/production smoke |

The required final release criteria are not all satisfied. This report does not
claim the product is fully complete, production ready or installer verified.

</details>

## Exact current uncommitted files

The following list is relative to the repository root and includes the preceding
Ollama integration fix plus this acceptance work against saved HEAD
`2543fd185e54f2e39c5e0697ee0fd1d1a66982f5`. The existing `.gitignore` change is
preserved separately and was not modified by this work. No dependency install,
package-lock change, staging, commit, push, reset or discard occurred; branch main.

- `ai-engine/app/agent/orchestrator.py`
- `ai-engine/app/agent/state.py`
- `ai-engine/app/config.py`
- `ai-engine/app/llm/ollama.py`
- `ai-engine/app/models/schemas.py`
- `ai-engine/app/recovery/engine.py`
- `ai-engine/app/recovery/planner.py`
- `ai-engine/app/tools/execution.py`
- `ai-engine/app/verification/engine.py`
- `desktop/AI_ARCHITECTURE.md`
- `desktop/README.md`
- `desktop/RELEASE_VALIDATION.md`
- `desktop/electron/agent-process.ts`
- `desktop/python/agent_host.py`
- `desktop/python/agent_projection.py`
- `desktop/scripts/validate-windows-package.mjs`
- `desktop/shared/agent-response.ts`
- `desktop/shared/intelligence-response.ts`
- `desktop/src/components/AI/AIPanel.tsx`
- `desktop/src/components/AI/RecoveryCard.tsx`
- `desktop/src/components/AppShell.tsx`
- `desktop/src/styles/ai.css`
- `desktop/src/types/activity.ts`
- `desktop/src/types/ai.ts`
- `desktop/src/types/backend.ts`
- `desktop/src/workspace/activity.ts`
- `desktop/src/workspace/completion.ts`
- `desktop/src/workspace/useAI.ts`
- `desktop/tests/electron-real-flow.cjs`
- `FINAL_ACCEPTANCE_REPORT.md`
- `ai-engine/app/verification/snapshot.py`
- `ai-engine/tests/test_desktop_ollama.py`
- `ai-engine/tests/test_resumable_recovery.py`
- `desktop/OLLAMA_INTEGRATION_REPORT.md`
- `desktop/tests/agent-timeouts.test.ts`
- `desktop/tests/electron-live-ollama.cjs`
- `desktop/tests/electron-live-recovery.cjs`
- `desktop/tests/ollama-ui.test.tsx`
- `desktop/tests/packaged-live-recovery.cjs`
- `desktop/tests/recovery-completion.test.tsx`
- `desktop/tests/test_ollama_host.py`

Generated logs, disposable projects, profiles, screenshots, extraction directories
and release packages are ignored validation artifacts, not committed source.
The portable QA processes may still be running; no forced termination or user
process deletion was performed after approval review became unavailable.

</details>

