# Windows release validation — final failure UI fix

**October 9 latest source:** the explicit Qwen tool-sequence/recovery fix is
validated by 278 backend tests, 55 rerun Python-host tests and real Qwen evidence.
The 276 unchanged Vitest tests and desktop build/smokes are carried forward.
New NSIS output: `.packaging/final-recovery-release-20261009/`; build, per-user
install, source-matching payload and one visible normal launch are VERIFIED.
Ordinary uninstall exited 0 and removed the executable and registration: VERIFIED.
Installer SHA-256: `D2EE868726D70F17574E5959F973402AF3FF2C855FF51B994ADD032D1BD1ADEE`
(127,304,074 bytes; Authenticode NotSigned). Installed payload: 30 ASAR entries,
1,599 files, 82 backend and five host files identical to current source. Bundled
runtime read/save/run/pytest passed; current-source live AI and the package's
visible launch are separate checks. Old hashes below do
not represent the new backend. See
[FINAL_RECOVERY_ACCEPTANCE_REPORT.md](FINAL_RECOVERY_ACCEPTANCE_REPORT.md).

**October 8 product-audit update:** the release hashes, payload comparisons and
packaged acceptance recorded below predate the new actual-source context,
frontend editing and approved npm capabilities. Existing artifacts are historical,
not current with this working tree. No new release build is claimed in this audit.
See [PRODUCT_QUALITY_REPORT.md](PRODUCT_QUALITY_REPORT.md) for latest source tests
and real full-stack/Python desktop validation. Packaging and policy results below
must be repeated against a future rebuilt release before distribution claims.
The subsequent October 9 Explorer/AI/npm verification source changes are recorded
in [PRODUCT_IMPROVEMENT_REPORT.md](PRODUCT_IMPROVEMENT_REPORT.md). No new Windows
artifact was rebuilt or validated for that source improvement.

Review: **October 8, 2026 (Asia/Calcutta)**. OpenArise 0.1.0, Windows x64.
Recorded tests, model responses and artifact timestamps retain their actual
October 7–8 dates; they are not all claimed as October 8 reruns.

**Targeted functional product acceptance: VERIFIED.** The latest installed
packaged UI displays real recovery success and failure/gate refusal. **Distribution
acceptance: BLOCKED** by current ZIP execution and MSI validation policy.
Publisher signing and a clean Windows host remain NOT VERIFIED.
No production-readiness claim, commit or push.

## Current source validation

| Check | State | Actual result |
| --- | --- | --- |
| Full desktop npm test | VERIFIED | **271 passed**, 0 failed: **234 Vitest**, 20 files; **37 Python host**, 10.092 seconds |
| Full backend pytest | VERIFIED | **188 passed**, 0 failed, **43.02 seconds** |
| npm run build | VERIFIED | TypeScript, Vite and Electron bundles; existing non-failing Monaco size warning |
| Production Electron smoke | VERIFIED | Real read/save/conflict, Python/pytest, terminal sessions, security, responsive checks and shutdown; AI fixtures visibly labelled |
| Development Electron smoke | VERIFIED | Same real local operations and explicit AI fixtures; shutdown passed |
| Normal npm start | VERIFIED | One native visible OpenArise main window/main process/renderer; no debug flags, Vite or profile override; normal close |
| Normal npm run dev | VERIFIED | One native visible window/main process/renderer; ordinary managed dev script/server, no debug/profile override; normal close |
| Real packaged Qwen/UI success | VERIFIED | Denial prevented mutation; approved real mutation/failure/repair/fresh retest; RECOVERED; CompletionGate VERIFIED |
| Real packaged Qwen/UI failure | VERIFIED | Actual failure/recovery/mandatory failing retest/rollback; FAILED, ROLLED_BACK and CompletionGate NOT_VERIFIED displayed |
| Responsive real final outcomes | VERIFIED | Actual settled VERIFIED/FAILED headings visible at 1320x880, 1050x740 and 760x540; screenshots inspected |

Logs and native observations are under `.packaging/failure-ui-fix/`: desktop-tests.log,
backend-tests.log, build.log, production-smoke.log, development-smoke.log,
npm-start.log, npm-dev.log, source-normal-launch/ and dev-normal-launch/.
The first dev observation preceded Electron spawning and saw zero processes;
after the managed dev server/Electron started, the unchanged observer found one.
The installed first window observation timed out; a later unchanged observation
found exactly one visible full window. No count/timeout assertion was weakened.

## Fresh artifacts

ZIP, portable and NSIS were rebuilt from the fixed application after full source
suites/build/smokes, with existing tooling and `--publish never`. MSI is a fresh
mandatory-validation attempt, which returned LGHT1105. Old hashes/launch results
are not reused as current.

| Artifact | Bytes | Build/contents | Normal execution |
| --- | ---: | --- | --- |
| release/OpenArise-0.1.0-win-x64.zip | 171,405,089 | VERIFIED | **BLOCKED**, current Application Control policy |
| release/OpenArise-0.1.0-win-x64-portable.exe | 112,860,018 | VERIFIED | **VERIFIED**, latest wrapper produced one visible main window |
| release/OpenArise-0.1.0-win-x64-setup.exe | 126,889,754 | VERIFIED | **VERIFIED**, per-user install, normal launch and uninstall |
| MSI | — | **BLOCKED**, current required WiX validation, LGHT1105 | No validated MSI; install/launch/uninstall NOT VERIFIED |
| Publisher signing | — | **NOT VERIFIED**, EXEs are NotSigned | No certificate supplied |
| Clean Windows VM/second host | — | **NOT VERIFIED** | No clean environment available |

SHA-256, current targets:

```text
A7CB1A30D19101EE58F2C041C3E3ECF1B20D910FC78EBCC09A6CFF19BF86FB52  OpenArise-0.1.0-win-x64.zip
40E6847BA0F524FFFF0F04BB906FE6AE130D239A923CB3EC9036086C901A5FFD  OpenArise-0.1.0-win-x64-portable.exe
7F141AE3036208304FC5FE5A293157CFB737CD77427A0A5A7846972FA820FE1B  OpenArise-0.1.0-win-x64-setup.exe
```

Current app.asar SHA-256 in all three validated payloads:
`C62E0C24EA3FFBD8A9CB27C15DD179C1694D5F18D1C855669803EB8599282425`.
The subsequent MSI build's ASAR still matches that exact validated build.

ZIP contains 1,592 files, portable 1,593, installed NSIS 1,594; each has 16 ASAR
entries. All **77 backend** and **five desktop host** source files match the
checkout, as do compiled bundles, metadata and the unchanged icon. Identity is
OpenArise/0.1.0/OpenArise.exe. No Node development dependency tree, secrets/.env,
caches, bytecode, logs, local project state or test garbage appear in the payloads.
The isolated Python/pytest runtime under resources/ai-engine/.venv/Scripts is
intentional product content, not the complete development virtual environment.
Each actual bundled interpreter passed imports/read/save/backend project and
environment/supervised Python/pytest (**1 passed**) with PATH=System32 and no
PYTHONHOME/PYTHONPATH. These runtime checks do not themselves prove live AI.

Evidence: zip-contents.json, portable-contents.json, installed-contents.json,
artifact-hashes.json, zip-root.txt, portable-launch.json and installed-root.txt.
QA scripts, profiles and disposable projects are excluded from packages.

## Actual Windows policy and installer outcomes

Latest extracted ZIP launch without arguments returned **"An Application Control
policy has blocked this file."** Code Integrity events **3033** and **3077** on
October 7 at **20:44:11.901 / 20:44:13.370 +05:30** identify Enterprise signing
requirements and Policy ID **{0283ac0f-fff1-49ae-ada1-8a933130cad6}**.
See zip-policy-events.json. No alternate launch method/flags/caller, renamed
executable, signature exception or policy change was used on that blocked ZIP.
Its offline source/runtime validation remains valid.

The separately built latest portable wrapper was launched normally without
arguments and actually opened one visible OpenArise window. Its extracted image
path was obtained from Get-Process.Path where WMI omitted ExecutablePath; the
observer still matched the exact native image and asserted one main/visible
window/renderer. Full native capture was inspected. Payload/runtime match the
fixed source; ordinary close was requested. Historical portable policy blocks
are not claimed for this latest wrapper.

NSIS used ordinary per-user `/S /D=<owned QA workspace directory>`. Initial
inspection recorded zero existing OpenArise installs/shortcuts. Its current
registration was exactly OpenArise 0.1.0, with UninstallString pointing to the new
QA directory. Installed launch had no arguments, debug flags, Vite or special
user-data directory and showed one visible full window. After the live QA app
closed, the original uninstaller `/currentuser /S` returned **0**; installed
OpenArise.exe and the matching registry entry were removed. No forced deletion,
user installation overwrite or policy change. See nsis-install.json,
installed-normal-launch/launch.json and nsis-uninstall.json.

Fresh MSI required WiX ICE validation returned **LGHT1105**, light.exe exit
**1105**; the npm build command exited **1**: "Validation could not run due to
system policy." The exact invocation retained `-pedantic -wx`; no `-sval`, ICE
suppression, admin retry or policy change. See msi-build.log. No validated MSI
was produced or installed; MSI install/launch/uninstall remain NOT VERIFIED.
Existing non-failing manufacturer/author metadata warnings were not changed.

## Real packaged renderer/backend/model evidence

Primary evidence:
`.packaging/failure-ui-fix/packaged-ui-1791388991512/evidence.json`.
Application isPackaged=true; appPath is the freshly installed resources/app.asar.
Every observed transport response is source=backend. Production renderer →
preload → main → bundled Python host → BackendService → AgentOrchestrator →
OllamaProvider used **real qwen2.5-coder:7b** at 127.0.0.1:11434.

The external QA controller uses a loopback Node inspector, an isolated profile
and only disposable native-folder-picker paths. It clicks existing DOM controls,
approves only math_ops.py writes/pytest, and records unchanged real IPC responses.
It injects no model/provider/tool/result/evidence fixture. This is **automated
real packaged UI validation**, not a new human-operated native-picker check.
Normal no-flag source/portable/installed launches were separately observed.

| Case | Actual backend result and corresponding renderer display |
| --- | --- |
| Deny proposed write | DENIED; original math_ops.py unchanged; no permission approval/mutation fabricated |
| Recovery success | COMPLETED / success, RECOVERED, Final Result VERIFIED, CompletionGate VERIFIED, 1/1 requirement |
| Recovery failure | FAILED / failure, ROLLED_BACK, Final Result FAILED, CompletionGate NOT_VERIFIED, 0/1 requirement |

Success request `d323cb55-ca20-4f9e-8b5c-cacc99ce33e4`, requirement
`8d99e130-f097-473b-a7de-c19a629b0fa1`: **8 real evidence records**, **4 actual
test-tool executions**, **one recovery attempt**. Baseline proof
`263f0215-22f8-4f12-ac06-34932d9bac05` became stale/superseded. Failed proof
`25b8b946-06b2-456d-8cf8-da703d8bbc51` was retained and linked to fresh mandatory
passing retest proof `e1b4fc06-51e6-4799-a09a-cfa7fd0d77a6`, exit 0.
All evidence preserved the original requirement identity; original tests unchanged.

Failure request `54c49e4b-bbef-449d-9896-f34e0ea9bdc1`, requirement
`f6ff4f59-c5fd-4eaa-ad86-c99450713ba4`: **6 evidence records**, **3 actual test-tool
executions**, **one recovery attempt**. The always-failing test was preserved.
Recovery's mandatory whole-project retest really failed, exit 1, and rollback
returned ROLLED_BACK. UI shows the actual failure message, diagnosis, failed tool
IDs and "Recovery retest failed. (Rolled back successfully)". That successful
rollback is not a successful repair: Final Result remains FAILED and the gate
remains NOT_VERIFIED, with failed/contradictory and changed-project evidence shown.

Actual settled DOM text, raw projected DTOs, recorded backend activity and
success/failure captures at all three sizes are retained. No `<actual result>`,
demo output or fabricated VERIFIED appeared. Activity says BACKEND RESPONSE /
last returned data / no live streaming and uses actual returned events only.
The screenshot helper waits for the matching final request/enum/idle controls
and painted frames; it does not infer progress or completion from elapsed time.

One earlier QA attempt passed both real backend cases but stopped at a
case-sensitive heading assertion because CSS uppercases the badge. Another
repeat hit a real **180-second Ollama generation timeout**, preserved in its log.
The passing run used the existing supported **OLLAMA_TIMEOUT_SECONDS=300**
environment override for that QA child only. Defaults were not changed.
Model inference timing remains hardware dependent. Earlier failures/pending
compositor captures are retained and are not presented as final passing proof.

## Scope and security

Only two production UI components changed for this target: RecoveryCard and
VerificationCard. Real backend projection was already intact; exact statuses
now remain explicit. Focused fixture-labelled UI/provenance regressions and real
permission/file/pytest projection regressions were added, plus external release QA.
See [../FINAL_ACCEPTANCE_REPORT.md](../FINAL_ACCEPTANCE_REPORT.md) for all nine
changed source/test/doc files and the investigation findings.

Backend source is unchanged from this task's hash baseline, including earlier
uncommitted backend work. contextIsolation=true, nodeIntegration=false,
sandbox=true, webSecurity=true were inspected in the actual packaged window.
Narrow allowlisted IPC, sender/page checks, controlled Python command grammar,
main-owned filesystem/model access and production transport are unchanged.
No dependency install, packaging configuration/lockfile/logo/.gitignore change,
staging, commit, push, reset or discarded user work.
