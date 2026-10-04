# Windows release validation — final Phase 8 (2026-10-04)

Application: OpenArise 0.1.0, Windows x64.
This records observed results. **Full product acceptance is NOT VERIFIED.**
Live Ollama/model validation is NOT VERIFIED. The ZIP launches on this host;
portable and installer execution are BLOCKED.

## Tests and production build

| Check | State | Result |
| --- | --- | --- |
| npm test / full desktop suite | VERIFIED | 207 Vitest in 16 files + 32 Python host = 239 passed, 0 failed |
| npm run build | VERIFIED | TypeScript, production Vite and Electron entry/main/preload bundles |
| npm run test:smoke | VERIFIED | Final production Electron smoke passed |
| npm run test:smoke:dev | VERIFIED | Final development Electron smoke passed |
| npm run test:real | VERIFIED | Real files, controlled Python, pytest, failures, conflicts, close/reopen |
| ai-engine/.venv/Scripts/python.exe -m pytest | VERIFIED | 161 collected, 161 passed, 0 failed |

The local Monaco bundle retains a non-failing size warning. No tests were deleted
or assertions weakened. Four focused Phase 8 Vitest tests were added. Backend
source/test/config hashes and Git diff remain unchanged; no dependencies were
installed and package-lock.json remains unchanged.

## Normal native launches

Normal npm start (electron .) launched the actual production application,
without debug flags, Vite, fixtures or a user-data override. Normal npm run dev
launched Electron and its managed development Vite server, without fixtures or
a user-data override. Each had one main process, one renderer and exactly one
native visible main window titled OpenArise. Native captures were visually
inspected; the windows were closed normally.

These checks found and fixed a production bootstrap defect hidden by the earlier
test bootstrap: require.main === module did not invoke startDesktop under
Electron's loader. The explicit bundled electron/entry.ts is now package.main.
The tested service architecture and security checks are preserved.

First-run screens have no selected project, seeded AI work, or fake activity.
The original static logo and icon are unchanged. App name/window title are
OpenArise; executable is OpenArise.exe; app version is 0.1.0, Windows
ProductVersion 0.1.0.0. Renderer/native captures and smoke geometry cover
1320x880, 1050x740 and 760x540. Small panels remain scrollable.

The real-flow probe supplied only the native folder picker's temporary project
path. Real Explorer/Monaco inspected and edited main.py; the production file
host saved it; controlled Run printed REAL_PYTHON_RUN; Test executed actual
pytest (1 passed). Malformed Python displayed SyntaxError. External edits caused
a visible conflict with no overwrite; dirty close required an explicit discard;
dirty Ctrl+R retained edits. A subsequent launch reopened the project and read
persisted file bytes.

The real AI request used the real backend and returned FAILED / INCONCLUSIVE,
zero evidence/tests and no confirmed change. UI showed failure/unverified
evidence, never DONE. This verifies missing-provider/error handling, not a
working live model. Positive permission/recovery/verification UI scenarios use
explicitly labelled TEST FIXTURE data and controlled providers; no live
streaming or success is invented.

Native Windows accessibility inspection exposed panes rather than actionable
renderer controls. The native picker was not operated through a full human
workflow. Source probes supply the picker result; packaged interactive
project/edit/run/test acceptance remains NOT VERIFIED.

## Final packages

Built with the existing electron-builder 26.15.3 / Electron 44.4.5 tooling.
Compiled application bundles, static icon, backend modules, desktop hosts and
isolated CPython 3.13 are included. Node development dependencies, global Python
site-packages, pip, stdlib test/demo/IDLE/ensurepip tooling, caches, bytecode, logs,
secrets files and local project state are excluded. Runtime pytest dependencies
remain included.

| Artifact/check | State | Result |
| --- | --- | --- |
| OpenArise-0.1.0-win-x64.zip | VERIFIED | Built; 171,395,150 bytes |
| ZIP extracted normal launch | VERIFIED | Fresh external temp directory, no flags/Vite/user-data override, one visible native OpenArise window |
| ZIP second launch | VERIFIED | New process exited 0; original main process/window stayed exactly one |
| ZIP contents/runtime | VERIFIED | 1,591 files / 16 ASAR entries; bundles match current build; real bundled imports/read/save/backend/Python/pytest (1 passed) |
| OpenArise-0.1.0-win-x64-portable.exe build/contents | VERIFIED | 112,854,955 bytes; 1,744 payload entries; ASAR equals validated ZIP |
| Portable normal launch | BLOCKED | Windows Application Control blocked the unsigned wrapper before execution |
| OpenArise-0.1.0-win-x64-setup.exe NSIS build | VERIFIED | Standard complete 126,881,751-byte installer; normal uninstaller helper generation completed |
| NSIS install/installed launch/uninstall | BLOCKED | Application Control blocked Setup before installation; no installed launch/uninstall verified |
| MSI required validation | BLOCKED | WiX light.exe exit 1105, LGHT1105: validation could not run due to system policy |
| Publisher signing | UNAVAILABLE | No certificate configured; portable and Setup status NotSigned |
| Clean Windows VM/second host | NOT VERIFIED | Not available in this task |

ZIP extraction was outside the checkout. Its OpenArise.exe launched normally
and a full native screenshot showed the same first-run UI. Package validation
used bundled interpreter/resource paths with PATH restricted to System32 and
PYTHONHOME/PYTHONPATH removed. It exercised actual backend project/environment
responses, production file-host read/save and the packaged supervisor running
Python and one real pytest case. These are isolated runtime checks on this
existing Windows host, not clean-OS acceptance.

The observer waits up to 30 seconds for a cold native window and still requires
exactly one. No debug port or manually started Vite was used for final packaged
normal-launch validation. Contents checks compare entry/main/preload/renderer/
icon bytes against the final production build. Portable inspection reads its
embedded archive only; neither the blocked wrapper nor extracted payload was
executed during that inspection.

### Exact policy blocks

Portable and Setup normal launch both returned:
"An Application Control policy has blocked this file."

Windows CodeIntegrity event 3077 records Enterprise signing level requirements
or a code integrity policy violation, Policy ID
{0283ac0f-fff1-49ae-ada1-8a933130cad6}.
Portable: 2026-10-04 17:35:42 +05:30.
Setup: 2026-10-04 17:37:47 +05:30.

MSI's mandatory ICE validation returned:
"light.exe : error LGHT1105 : Validation could not run due to system policy."

The standard WiX validation command retained -pedantic/-wx and did not use
-sval. No policy, signature, UAC or ICE bypass was attempted in Phase 8.
Earlier diagnostic/stale packages are excluded from the final release.

### Final SHA-256

| File | SHA-256 |
| --- | --- |
| ZIP | CBE285367BB6BDA1A5AD70573C7E94CC1978347E706BA15A96A863A2FA9B462F |
| Portable candidate | CE706D7242ED2C42F16C78CE2D2E19E0D213435463A92F31A9D4EC98D5B451FB |
| NSIS candidate | 7004DD0C918EC094BDD77385C8730E9CBDFDBDFD5F90C3B2EB2B00E976628F66 |
| app.asar, ZIP and portable payload | 0AE1B6185B195923322F7682056958FCC535AA0F42224FF0731316077F179F8B |

Validated release files:

- release/OpenArise-0.1.0-win-x64.zip
- release/SHA256SUMS.txt
- release/RELEASE_NOTES.txt

Blocked candidates, retained separately for review:

- .packaging/phase8-blocked-artifacts/OpenArise-0.1.0-win-x64-portable.exe
- .packaging/phase8-blocked-artifacts/OpenArise-0.1.0-win-x64-setup.exe
- .packaging/phase8-blocked-artifacts/OpenArise-0.1.0-win-x64-setup.exe.blockmap

The unpacked final stage remains release/win-unpacked/. Native observations,
screenshots and portable contents inspection are under
.packaging/phase8-validation/. The extracted ZIP root is recorded in
.packaging/phase8-zip-directory.txt. QA helpers are not packaged or exposed
through IPC.

## Security and remaining acceptance

contextIsolation=true, nodeIntegration=false, sandbox=true, webSecurity=true;
allowlisted sender/frame/page/project-validated IPC; fixed Python hosts and
command grammar; no renderer Node/filesystem access, generic IPC, arbitrary
executable override, or unrestricted shell. PermissionManager, recovery,
evidence/verification and CompletionGate remain the backend authorities.

Remaining: full human native-picker/project workflow in the packaged app;
live configured Ollama permission decisions, real recovery and evidence-backed
verified completion; publisher signing and policy-permitted portable/installer
launch; installer install/launch/uninstall; clean Windows machine acceptance.

See [PHASE8_REPORT.md](PHASE8_REPORT.md) for the exact 20 changed files and the
17-item final acceptance checklist. This is not a production-ready,
installer-verified or live-AI-verified declaration. Stop at Phase 8; no commit
or push.
