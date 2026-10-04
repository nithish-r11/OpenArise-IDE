# Person 3 Phase 8 — Final desktop polish and Windows packaging

Date: 2026-10-04 (Asia/Calcutta)
Repository: E:\OpenArise-IDE\OpenArise
Version: 0.1.0

Phase 8 implementation and validation are recorded below. **Full product
acceptance is NOT VERIFIED.** The final ZIP launches and its bundled runtime
works on this host. Normal portable/installer execution is BLOCKED by Windows
policy. Live Ollama/model behavior remains NOT VERIFIED.

## Final changes

Preserved the navy/black composition, electric blue/violet accents, Explorer,
Monaco, terminal, AI and intelligence panels, separate Arise Activity Visualizer,
and original static logo/icon. A shared finishing stylesheet adds consistent
controls, scrollbars, focus, error borders, readable muted text, and short-window
spacing. Welcome has local project guidance, safe overflow alignment and a
compact empty terminal. No demo project, request, success or activity is seeded.

Workspace errors/discard/loading messages now remain visible when intelligence
is selected. A missing desktop bridge has an explicit error instead of a browser
preview success label. App captures its actual bridge when mounting. A React
runtime boundary presents an understandable failure and requires a separate
explicit discard decision before reload. A stopped renderer shows a native
error. The native application menu is removed; dirty Ctrl+R/F5 reloads are blocked.
Existing safe-save, conflict, terminal and AI permission safeguards remain.

Normal npm start testing found an actual production bootstrap defect: the prior
require.main === module guard did not run startDesktop under Electron's loader.
Added electron/entry.ts and pointed package.main at its bundle. Tests continue
using the same main service export; production/development use the explicit
entry. The application and window are OpenArise; executable is OpenArise.exe;
Windows ProductName is OpenArise and ProductVersion is 0.1.0.0 (application
version 0.1.0). The original logo SHA-256 remains
7170A7B5A083B27FA852082E8AE42DB47419F52376AEFC1A281748EB2B6486E3.
The existing icon remains 8DF2DEDE7B4EE5CE0B5CA70159179F2CE958CC14223BAB5966E74522757FB419.

Vite excludes generated release/staging/build folders and Python hosts from
watching, preventing irrelevant packaging changes from reloading a development
workspace. Restart for main/preload/Python-host changes.

Packaging includes compiled bundles and the existing icon, protected backend
modules, desktop Python hosts, and an isolated CPython 3.13 runtime copied from
the existing environment. It excludes Node development packages, global Python
site-packages, pip, stdlib test/demo/IDLE/ensurepip tooling, bytecode, caches,
logs, secrets files and local project state. Pytest/runtime dependencies remain.
The fixed staging target and resolved parent are checked before replacement.
No dependency was installed. package-lock.json is unchanged.

Two source-only QA helpers inspect package contents/runtime and observe the
specified executable's native Windows window. They are absent from packages
and inaccessible through IPC. They do not create another backend or service.

## Exact changed source, test and documentation files

Measured against a SHA-256 snapshot taken at the start of Phase 8. The desktop
was already untracked and the root .gitignore already modified before this phase.

Modified (13):

- desktop/README.md
- desktop/RELEASE_VALIDATION.md
- desktop/electron-builder.config.cjs
- desktop/electron/main.ts
- desktop/index.html
- desktop/package.json
- desktop/scripts/build-electron.mjs
- desktop/scripts/prepare-windows-runtime.mjs
- desktop/src/App.tsx
- desktop/src/components/AppShell.tsx
- desktop/src/main.tsx
- desktop/tests/electron-real-flow.cjs
- desktop/vite.config.ts

Added (7):

- desktop/PHASE8_REPORT.md
- desktop/electron/entry.ts
- desktop/scripts/observe-windows-launch.ps1
- desktop/scripts/validate-windows-package.mjs
- desktop/src/components/RuntimeBoundary.tsx
- desktop/src/styles/polish.css
- desktop/tests/phase8.test.tsx

Generated deliverables are listed separately below. Earlier/stale/interrupted
candidates and blocked artifacts are retained only under ignored .packaging/.
Build bundles, runtime staging, captures and test projects are ignored outputs.
No ai-engine source/test/config file was edited. No commit or push was made.

## Tests and build

| Validation | State | Exact result |
| --- | --- | --- |
| npm test — Vitest | VERIFIED | 207 passed across 16 files; 0 failed |
| npm test — desktop Python hosts | VERIFIED | 32 passed; 0 failed |
| Complete desktop test total | VERIFIED | 239 passed; 4 new Phase 8 Vitest cases |
| npm run build | VERIFIED | TypeScript, Vite production renderer and Electron entry/main/preload |
| npm run test:smoke | VERIFIED | Final production renderer/main/preload/IPC smoke passed |
| npm run test:smoke:dev | VERIFIED | Final development renderer/main/preload/IPC smoke passed |
| npm run test:real | VERIFIED | Real project/file/Python/pytest/failure/conflict/close/reopen probe passed |
| ai-engine/.venv/Scripts/python.exe -m pytest | VERIFIED | 161 collected, 161 passed in 8.79s; 0 failed |
| Backend source and test preservation | VERIFIED | Git diff empty; baseline content hashes unchanged |
| Dependency installation | VERIFIED | None; dependency versions/lockfile unchanged |

The existing local Monaco chunk warning remains non-failing (approximately
3.14 MB before gzip). Initial Phase 8 tests exposed an asynchronous startup
assertion that needed awaiting. Production smoke caught reduced activity reading
height at 760x540; CSS was corrected without changing its existing minimum
assertion. A new native-input probe assertion was corrected for Monaco's
non-breaking spaces. The new package QA helper was corrected for Windows path
normalization and the backend writer's existing CRLF behavior. No tests were
deleted and existing assertions were not weakened.

Final Electron geometry/captures cover 1320x880, 1050x740 and 760x540, including
welcome logo visibility, editing, intelligence, permission controls and verification.
Small panels scroll and AI retains its existing expandable overlay.

## Actual launch and real workflow

npm start was invoked normally: electron .; no debug flags, fixture adapter,
user-data override or Vite server. Windows observation found one main process,
one renderer, one native visible main window titled OpenArise. The full native
capture was visually inspected. Its close action was sent through the native
window, and subsequent normal launches worked.

npm run dev was invoked normally. It starts and stops its own Vite server and
launches Electron through the production entry with the existing development
mode selector. One visible native OpenArise window was captured and inspected.
No fixture or user-data override was used. This is actual source development
launch validation, not opening the Vite page in a browser.

The real-flow probe creates a genuine Python project with main.py, a pytest test,
and malformed Python. It supplies only the folder picker's selected path for
unattended execution. Explorer and Monaco read the actual files. Native input
edits are saved through the real backend file host; controlled Run prints
REAL_PYTHON_RUN; Test runs real pytest (1 passed); malformed Python displays a
SyntaxError. External disk edits cause a visible conflict without overwriting
the disk, dirty tab closing requires discard, Ctrl+R retains the unsaved editor,
and a second application launch reopens the project and reads persisted bytes.

The real AI request reached the real backend and returned FAILED with
INCONCLUSIVE verification, zero evidence/tests and no confirmed change. The
UI displayed FAILED and missing evidence, never DONE or VERIFIED. This is real
missing-provider/error handling, not live model validation.

The native folder picker was not operated end to end by a human in this task.
Windows accessibility inspection exposed only panes, so native picker interaction
was not claimed. Source workflow probes supply the picker result; packaged
full human project interaction remains NOT VERIFIED. Capturing and inspecting
actual normal windows is distinguished from a human manual workflow test.

## Windows artifacts and package validation

Built with the installed electron-builder 26.15.3/Electron 44.4.5 tooling on
Windows x64. Current artifacts contain Phase 7 and final Phase 8 changes.

| Artifact/check | State | Result |
| --- | --- | --- |
| ZIP build | VERIFIED | release/OpenArise-0.1.0-win-x64.zip; 171,395,150 bytes |
| ZIP extraction/normal launch | VERIFIED | Extracted to a fresh temp directory outside checkout; no flags, Vite or user-data override; one visible native OpenArise window |
| ZIP second launch | VERIFIED | New process exited 0; original main/window remained exactly one |
| ZIP contents and runtime | VERIFIED | 1,591 files; 16 ASAR entries; isolated imports, real read/save/backend inspection, supervised Python and 1 passing pytest test with PATH=System32 |
| Portable build/embedded contents | VERIFIED | 112,854,955 bytes; 1,744 payload entries; no excluded development content; ASAR matches validated ZIP |
| Portable normal launch | BLOCKED | Windows Application Control prevented starting the unsigned wrapper; no embedded application launch was confirmed |
| Standard NSIS build | VERIFIED | 126,881,751-byte Setup EXE; normal uninstaller generation completed; validation was not bypassed |
| NSIS install/installed launch/uninstall | BLOCKED | Windows Application Control prevented starting Setup; installation, installed launch and uninstall NOT VERIFIED |
| Standard MSI build | BLOCKED | WiX light.exe exit 1105/LGHT1105: ICE validation could not run due to system policy; no validated MSI |
| Clean Windows machine | NOT VERIFIED | No clean VM/second physical host was available; isolated PATH/external extraction checks are not a fresh OS install |
| Publisher signing | UNAVAILABLE | No publisher signing configuration; portable/Setup Authenticode status NotSigned |

ZIP SHA-256:
CBE285367BB6BDA1A5AD70573C7E94CC1978347E706BA15A96A863A2FA9B462F

Portable candidate SHA-256:
CE706D7242ED2C42F16C78CE2D2E19E0D213435463A92F31A9D4EC98D5B451FB

NSIS candidate SHA-256:
7004DD0C918EC094BDD77385C8730E9CBDFDBDFD5F90C3B2EB2B00E976628F66

Final app.asar SHA-256 (ZIP and portable payload):
0AE1B6185B195923322F7682056958FCC535AA0F42224FF0731316077F179F8B

Normal launch initially checked the ZIP before its cold native window was ready;
it subsequently became visible without changing flags. The QA observer now waits
up to 30 seconds for exactly one visible window; its assertion remains mandatory.

The first pre-fix bootstrap candidates and a stopped pre-welcome-polish build
were excluded from final release. Final ZIP/portable payload bundle bytes are
checked against the current production build, not merely their filenames.

Actual policy errors for portable and Setup were:
"An Application Control policy has blocked this file."
Windows CodeIntegrity event 3077 recorded that each executable did not meet
Enterprise signing level requirements or violated code integrity policy,
Policy ID {0283ac0f-fff1-49ae-ada1-8a933130cad6}.
Portable block: 2026-10-04 17:35:42 +05:30.
Setup block: 2026-10-04 17:37:47 +05:30.

MSI's exact required-validation error was:
"light.exe : error LGHT1105 : Validation could not run due to system policy."
The normal command retained -pedantic/-wx and did not use -sval. No policy,
UAC, signature or ICE bypass was attempted. No prior diagnostic MSI is presented
as a release. The portable contents check only reads its embedded archive;
it does not execute the blocked wrapper or extracted application.

Validated generated files:

- desktop/release/OpenArise-0.1.0-win-x64.zip
- desktop/release/SHA256SUMS.txt
- desktop/release/RELEASE_NOTES.txt

Blocked review candidates (not validated downloads):

- desktop/.packaging/phase8-blocked-artifacts/OpenArise-0.1.0-win-x64-portable.exe
- desktop/.packaging/phase8-blocked-artifacts/OpenArise-0.1.0-win-x64-setup.exe
- desktop/.packaging/phase8-blocked-artifacts/OpenArise-0.1.0-win-x64-setup.exe.blockmap

Native capture/launch records and renderer captures are retained under
.packaging/phase8-validation/. The fresh extracted ZIP root is recorded in
.packaging/phase8-zip-directory.txt. The unpacked build remains in
release/win-unpacked/; packaging diagnostics are kept outside the release files.

## Security and UI provenance

contextIsolation=true; nodeIntegration=false; sandbox=true; webSecurity=true.
Existing sender/main-frame/exact-page/project checks, narrow allowlisted IPC,
fixed Python hosts, command grammar, no-shell execution, ownership cleanup,
revision/conflict checks, pending-permission behavior and bounded projections
remain. No renderer Node/filesystem access, generic IPC, executable override,
new backend or network service was added. Entry wiring does not bypass main.

Permission/recovery/verified/unverified UI scenarios use deterministic fixtures
and controlled providers. Smoke fixture responses are main-tagged TEST FIXTURE
and visibly say no live AI validation. Recorded activity stays recorded; no fake
streaming or inferred recovery success was added. Real backend absence/failure
is shown as such. PermissionManager, RecoveryEngine, evidence/verification and
CompletionGate retain their original authority.

## Exact final acceptance checklist

VERIFIED below means the specified observed/automated check, with scope limits
stated explicitly; it does not imply live Ollama or human/clean-machine acceptance.

| # | Acceptance criterion | Final state and scope |
| --- | --- | --- |
| 1 | OpenArise launches normally without special debug flags. | VERIFIED: npm start and extracted ZIP |
| 2 | Exactly one visible main window appears. | VERIFIED: native Windows window observation/captures |
| 3 | A Python project can be opened. | VERIFIED: actual desktop probe with native picker result supplied; human picker NOT VERIFIED |
| 4 | Files can be inspected and edited. | VERIFIED: real Explorer/Monaco probe |
| 5 | Changes can be saved safely. | VERIFIED: real save, revision/conflict and unsaved safeguards |
| 6 | Python code can actually be run through the controlled terminal workflow. | VERIFIED: source desktop flow; packaged supervised runtime |
| 7 | pytest can actually be run. | VERIFIED: source UI and bundled runtime; each executes one real passing test |
| 8 | AI requests use the real backend architecture. | VERIFIED: real unavailable-provider failure returned through main/preload/host |
| 9 | Permission-required actions actually stop for approval. | VERIFIED with deterministic UI fixtures/controlled backend providers; live model NOT VERIFIED |
| 10 | Approve/deny/cancel actually affect execution. | VERIFIED with fixtures/controlled providers; live model NOT VERIFIED |
| 11 | Real failures are detected and shown. | VERIFIED: SyntaxError, save conflict and actual backend failure |
| 12 | Recovery is attempted through the real recovery engine. | NOT VERIFIED in live desktop model flow; fixture presentation/backend controlled tests only |
| 13 | Verification is based on real evidence. | NOT VERIFIED for successful live AI completion; missing evidence correctly blocks real request |
| 14 | The completion gate prevents false DONE states. | VERIFIED: real failure plus fixture contradiction/stale/failed evidence checks |
| 15 | The final state is understandable to a normal user. | VERIFIED for inspected idle/error/fixture outcome screens; broader human usability acceptance NOT VERIFIED |
| 16 | The application can be packaged as a Windows executable/installer. | VERIFIED builds; portable/NSIS execution BLOCKED; validated ZIP available |
| 17 | The packaged application launches correctly on a clean test environment as far as the available environment allows. | VERIFIED external ZIP launch/isolated PATH checks on this host; clean Windows VM and installer acceptance NOT VERIFIED |

Remaining acceptance: live configured Ollama permission/decisions/failure/recovery
and evidence-backed verified completion; full human native-picker/project flow
in the packaged application; code/publisher signing and a policy-permitted
portable/installer launch; proper installer install/launch/uninstall; clean
Windows test-machine acceptance. No production-ready, installer-verified or
live-AI-verified claim is made. Work stops at Phase 8; no commit or push.