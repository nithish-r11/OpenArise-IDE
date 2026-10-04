# OpenArise desktop

Electron, React, TypeScript, Vite and Monaco, with Project Explorer, editing,
controlled Python execution, pytest, a session-based terminal, the AI workspace
and Project Intelligence.
All desktop work stays here. The backend and its contracts are unchanged.

## Run

Building from source requires Node 22.12+ and the backend Python environment at
`../ai-engine/.venv/`. The Windows distribution bundles the tested Python
runtime and backend modules; a separate system Python is not required.

```powershell
cd E:\OpenArise-IDE\OpenArise\desktop
npm run dev
# Production:
npm run build
npm start
```

Restart development mode after changing main/preload or desktop Python host code. Renderer edits use
Vite HMR at `127.0.0.1:5173`.

## Windows distribution

On a Windows x64 build host with the existing backend environment, use
`npm run package:win:dir` for an unpacked application,
`npm run package:win:zip` for a distributable archive, or
`npm run package:win:portable` for a single portable executable. Run
`OpenArise.exe` from the unpacked directory or extract the entire ZIP before
launching. The build copies the backend source and an isolated Python 3.13
runtime into Electron resources; it does not rely on the source checkout after
packaging. The existing OpenArise orbit image supplies the Windows icon.

`npm run package:win` targets an NSIS installer. Phase 8 produced a complete
Setup EXE, but Windows Application Control blocked its normal execution before
installation. The portable EXE was built and its contents inspected, but the
same policy blocked its normal launch. MSI failed required ICE validation with
LGHT1105. No validation or policy was bypassed in Phase 8. Only the ZIP has a
validated normal launch on this host. Blocked portable/Setup candidates are
retained under ignored `.packaging/phase8-blocked-artifacts/`, outside release
downloads. Publisher signing and install/launch/uninstall on a clean Windows
machine remain release acceptance items.

AI execution uses the existing backend Ollama provider and configured model.
Ollama and its model are separate prerequisites; neither is bundled or silently
installed. Project editing, controlled Python Run, and pytest work without it.
A missing Ollama service/model leaves AI requests failed and unverified; the
application must not present those requests as completed.

## Workspace

Choose **Open Project** using the native folder picker. Expand Explorer folders
and open files in Monaco. Python files support Save and Ctrl/Cmd+S; other UTF-8
text is read-only. Monaco includes highlighting, line numbers, minimap, Find,
Go to Line, folding and per-tab undo/view state. A language server is not included.

Explorer loads lazily. Runtime, dependency, Git and protected paths are excluded.
Files over 2 MiB, binary files, symbolic links, junctions and multiple hard links
are rejected. Each directory listing is limited to 2,000 entries. Collapse and
expand to refresh a folder. **Refresh project state** requests a factual snapshot
from the existing ProjectWorkspaceService; it is not a watcher.

Saving uses the existing backend ReadFileTool/WriteFileTool and production
PermissionManager. The explicit human Save grants a one-use approval only for
ASK; DENY remains authoritative. Approval is always revoked. No independent
writer or automatic agent approvals were added.

SHA-256 revisions are checked against the retained open revision and current disk
bytes. Conflicts retain the editor buffer. Edits made during a save remain dirty.
Closing dirty tabs or the window requires an explicit discard choice; project
switching is blocked while buffers are dirty. There is no autosave, Save As,
force overwrite, recovery or durable buffer storage.

## Python environment

Project Context displays interpreter path, probed version, environment status
and the reason for selection. **Refresh Python** repeats detection and the probe.

The desktop file host calls the existing EnvironmentDetector. Its .venv-before-venv
selection is preserved. A detected project environment selects that environment's
platform Python executable. A missing interpreter or linked environment directory
is unavailable; execution never silently falls back. If neither project environment
exists, the UI explicitly identifies the existing backend interpreter as the chosen
environment. No global PATH lookup or renderer-supplied executable is used.

Detection alone does not claim readiness. A supervised, five-second
`python -I -S --version` probe verifies startup and reports the actual version.
No dependencies are installed. A project environment without pytest reports
Python's real module error when Test is requested.

## Run and test

**Run** executes the opened Python file, using its latest confirmed saved revision.
**Test** invokes the selected interpreter with `-m pytest` in the selected root.
This runs the installed pytest engine and its normal project discovery/configuration;
it adds no test engine and makes no Person 1 verification claims.

All unsaved buffers, in-flight saves and unresolved save failures disable Run/Test.
Main also checks dirty state. The file host revalidates the exact opened revision,
Python extension and protected path before execution. An external edit causes a
conflict and requires reopening/reviewing the file. The project ID is checked again
after asynchronous preflight. Running does not implicitly save or force overwrite.

## Terminal architecture

```text
React terminal / Run / Test
  → window.openarise.terminal.request (fixed typed wrapper)
  → sender + main-frame + exact-page validation
  → TerminalService (selected project, sessions, command allowlist)
  → desktop Python supervisor (existing backend interpreter)
  → selected Python executable / installed pytest
  → bounded stdout/stderr snapshots → terminal + Problems
```

This is a controlled command terminal, not a general interactive shell or PTY.
The complete command grammar is:

- `python --version`
- `python relative/path.py` (file must already be opened and saved)
- `pytest`

Paths with spaces are literal unquoted paths. No shell expansion, chaining,
redirection, arbitrary flags, executable paths, cwd overrides, pip or dependency
installation commands are accepted. stdin is closed to the executed program.
Interactive input, ANSI terminal emulation and command history are not implemented.

Requests validate exact keys, UUID-like IDs, command length, relative path and
revision size. Input is capped at 2,100 characters. Main derives cwd exclusively
from the native-picker project, never from the renderer. IPC does not expose
child_process, raw invoke, a generic shell, or filesystem access.

Up to six sessions can coexist. Each records its opaque ID, trusted root, start
time, command, state and exit code. States are starting, running, stopped, exited
and failed. New sessions are stopped/idle. Each session runs one process at a
time. Restart stops the process and resets the session; it deliberately does not
rerun old code. Clear removes displayed output. Close stops and removes a session.

Output is streamed from stdout/stderr and polled by the UI every 500 ms. Each
session retains at most 128 Ki UTF-16 code units and 512 output segments; truncation
is explicit. Output is rendered as text, never HTML or interpreted terminal escapes.
Session details are available by hovering the command/status row. Problems lists
actual command, file and process errors; tracebacks and syntax errors remain in
stderr. pytest status reflects running/passed/failed and its actual exit code.

## Process lifecycle and isolation

Windows runs each command inside a desktop-owned Python supervisor with a
non-inheritable Job Object handle and KILL_ON_JOB_CLOSE. The supervisor owns itself
and descendants before launching the selected interpreter. Failure to establish
ownership fails the launch. Stop terminates the supervisor; closing its job kills
the process tree. Normal supervisor exit also removes descendants. On POSIX the
supervisor owns a process group, which main kills on stop and completion.

Main serializes lifecycle requests, stops sessions before replacing a project,
and awaits terminal shutdown before closing the file host and quitting. Version
probes are bounded to five seconds. A normal running command has no time limit;
use Stop. Output is bounded, but CPU, memory, filesystem and network activity of
executed project code are not limited.

**Process supervision is not OS sandboxing.** Python files, imports, pytest
configuration/plugins and the selected interpreter run with the user's privileges.
They can access files and services outside the workspace. The UI contract restricts
the selected command/path/cwd, not what trusted project code can do once executed.
POSIX programs can detach from a process group; adversarial code is not contained.
Do not interpret a clean exit as safety, correctness or backend verification.

Path/revision checks are not filesystem locks. A concurrent external mutation
between validation and interpreter open is a remaining race. Save retains the
existing writer's non-atomic behavior; an interrupted write may be partial.
No backend safety policies for autonomous AI actions were changed.

## Electron boundary and identity

contextIsolation, sandbox and webSecurity stay enabled; nodeIntegration and
webviews stay disabled. Navigation, new windows and permission requests remain
blocked. Both project and terminal IPC use the existing sender/page checks.
The BackendClient now connects to the desktop-owned stdio adapter described below.

The desktop-only file-host protocol adds environment and validate_run to
info/list/read/save/observe/shutdown. The protected BackendService contract is
unchanged. The host imports backend modules from the fixed repository, not the
selected project. Its requests are bounded, correlated and response-validated.

Monaco/grammar/worker are local assets. CSP permits the local blob worker, without
a CDN, unsafe-eval or disabled web security. Production network connections from
the renderer remain blocked. Development retains nonce-protected loopback HMR.

The supplied OpenArise orbit/logo JPEG is unchanged. Dark navy surfaces,
restrained blue/violet accents, thin borders, editor hierarchy and compact
terminal follow the approved references. Explorer resizes using its separator;
the terminal collapses and the right reserved region contracts at smaller sizes.

## Validation

```powershell
npm test
npm run build
npm run test:smoke
npm run test:real
npm run test:smoke:dev
cd ..\ai-engine
.\.venv\Scripts\python.exe -m pytest
```

Desktop tests cover UI, strict IPC, saved revisions, real Python stdout/stderr,
syntax failure, real pytest, unavailable environments, bounded output, sessions,
process-tree stop and shutdown. Python tests reuse the protected detector and file
tools. The Electron smoke uses real Monaco/preload/IPC/Python. The native
picker uses temporary project fixtures and the AI BackendProcessAdapter is replaced
with an explicit Node-side offline fixture; no real Ollama is needed. It checks save/conflict,
Python and pytest actions, sessions, three window sizes and quit-time cleanup.
The repeatable `test:real` flow uses the actual backend, Python supervisor,
pytest, real filesystem revisions, and a real AI request. It supplies only the
native picker result for unattended testing. Its temporary project and
screenshots stay in ignored `.packaging/`. Phase 8 separately observed and
inspected actual native visible windows from normal source and ZIP launches.
A full human native-picker/project workflow remains unverified.
Screenshots and smoke profiles live in OS temp or ignored packaging directories.

Vite retains the non-failing size warning for the local lazy Monaco bundle.
See RELEASE_VALIDATION.md for current package and real-flow evidence. PHASE6_REPORT.md records the earlier Phase 6 baseline.
PHASE4_REPORT.md retains the AI workspace audit.
PHASE3_REPORT.md retains the previous phase's audit.

## Deferred

WebSocket streaming, model-management UI, Luminous,
advanced semantic drift, advanced change impact, advanced recovery visualization,
persistent chat history, cloud, signed installers and updates remain deferred.
No commit or push is performed.

## AI workspace (Phase 4)

Open **AI** in the activity rail. Enter a multiline request, use Enter to send or
Shift+Enter for a newline. Refresh context displays bounded project/environment
observations. The request uses the existing BackendService and AgentOrchestrator;
no file dumps are sent by React. The production provider uses the backend's
existing Ollama configuration; no model or dependencies are installed.

The panel shows recorded lifecycle/tool activity, backend permission cards,
CompletionGate results, failure/unverified outcomes and session-only history.
Allow delegates approval then resume; Deny and Cancel delegate the existing
backend lifecycle. Only pending work can be cancelled. Synchronous in-flight work
cannot be guaranteed interruptible, and activity is not live streaming.

Outer dispatch success is never treated as verification. Verified is shown only
when the returned agent/CompletionGate states support it. Raw tool arguments,
code/output, model prose and stack traces are withheld. Secrets/configuration are
not exposed. Context counts and recovery states are shown only when reported.

See [AI_ARCHITECTURE.md](AI_ARCHITECTURE.md) for the integration path, request
lifecycle, permission/resume flow, exact presentation subset, process ownership,
verification semantics, security boundary, shutdown and cancellation limitations.

## Project Intelligence (Phase 5)

Open **Project Intelligence** from Explorer's project context, or use the existing
Blueprint, Traceability, Health and Timeline activity buttons. Nine detail tabs
share one observation bundle: Overview, Requirements, Blueprint, Traceability,
Environment, Health, Snapshot, Timeline and Drift. Explorer and AI restore the
editor; Monaco stays mounted so switching views retains buffers and undo history.
The existing logo, Electron security settings and editor/terminal actions remain.

### Data and architecture

The renderer's `useIntelligence` hook calls the existing BackendClient through
the scoped preload/main boundary and desktop-owned Python host. No renderer Node,
filesystem, subprocess, raw IPC, Python or network capability was added.

| View | Existing backend methods |
| --- | --- |
| Overview / project files | get_project_information, get_project_state, get_intelligence_snapshot |
| Requirements | get_requirements, get_blueprint |
| Blueprint | get_blueprint |
| Traceability | get_traceability_graph |
| Environment / health | get_environment_status, get_project_state, get_health_report |
| Snapshot | get_intelligence_snapshot |
| Timeline | get_timeline |
| Drift | create_requirement_baseline, get_drift_report |

`python/intelligence_projection.py` selects bounded presentation fields, redacts
secrets/URLs/diagnostics and excludes source, module bodies, hashes, raw metadata,
environment variables and raw tool results. The existing backend traceability
validator supplies graph validation findings. Strict main-process DTO validation
rejects additional fields; React validates the same shapes before display.

There is no desktop scanner, blueprint generator, inference engine, traceability
engine, health engine, drift detector or AI-written conclusion generator.
Relationship joins in Requirements/Blueprint only display backend IDs. Ordinary
project reads initialize the existing workspace facade without creating agent
memory/checkpoint stores. The existing agent is initialized when an AI request
actually needs it. Tests verify reads/refresh preserve project bytes and create
no `.openarise` directory.

### Refresh and missing data

The first intelligence visit, and explicit **Refresh intelligence**, call
`refresh_workspace` once followed by the nine read methods serially. Read data
is shared across views; tab switches do not trigger another scan. The refresh
button is disabled while a refresh or baseline action runs. Per-source loading,
error and unavailable states prevent missing or malformed data becoming zeros.
Project identity/generation checks discard responses from an old selection.

Refresh observes saved files only; it never saves editor buffers, installs
packages, executes project code or starts an LLM. Backend timeline events are
shown only when the backend records them. Each empty collection has an empty
state. Content scrolls vertically; navigation wraps at smaller sizes and the
terminal takes less height while intelligence is open.

Presentation is bounded to 100 records per collection, 800 characters per text
field, 160 per reference/criterion and eight criteria per requirement. Truncated
top-level collections carry a visible partial-view notice. Large nested lists
and text are bounded too; this is an inspection surface, not a lossless export.
File/test counts are scanned files and test files, not executed test case counts.
Mapping coverage and pytest availability are explicitly not reported when the
backend does not supply them. Detected frameworks do not prove installation.
Dependency status is limited to the backend's stated inspection scope; a detected
project virtualenv may be uninspected.

### Verification, traceability and drift semantics

Requirement lifecycle (pending/in_progress/completed/blocked) is displayed
separately from its stored verification status. Completed lifecycle does not
imply VERIFIED. The AI panel retains its CompletionGate-based verification rule.

Traceability shows typed node groups and recorded directed edges. Observed means
a stored link without the inference/evidence flags; inferred links have dashed
borders and are not proof. Evidence-backed flags describe relationships, not
successful completion. If both flags are set, both are displayed. Invalid graph
findings come from the existing backend validator. Unresolved/absent mappings
are identified without guessing missing edges or inventing coverage scores.
Per-link invalid classifications are not supplied by this backend.

Drift requires an explicit **Capture baseline** for a backend requirement.
The host retains the complete baseline in memory; the renderer receives only an
acknowledgment and sends only its requirement ID for comparison. The existing
backend captures and evaluates relationships/hashes. Refresh preserves the host's
baseline; **Replace baseline** explicitly replaces it. Baselines are lost when
the backend session closes/restarts or the selected project changes.

A comparison reloads snapshot and timeline directly, without another refresh
that would clear the backend's drift cache. A later general refresh clears that
cache per backend behavior; the Drift view labels its retained result as the last
explicit comparison. Compare again after saved changes. No recorded finding
does not prove no drift. NO_DRIFT, POTENTIAL_DRIFT, CONFIRMED_STRUCTURAL_DRIFT and
UNRESOLVED are displayed unchanged with backend reasons and related IDs/paths.
Potential drift is not confirmed semantic failure; no LLM analysis is performed.

### Phase 5 validation

Deterministic fixture data is confined to tests and explicitly injected in the
Node-side smoke adapter. Production imports no fixture and has no renderer mock
switch. Tests cover all views/states, lifecycle semantics, edge flags, validation,
baseline ordering, stale responses, refresh deduplication, redaction and real
host read-only behavior. Electron smoke exercises all nine views at 1440x900,
1050x740 and 760x540, no horizontal overflow, expanded-terminal readability,
activity navigation and baseline comparison, plus earlier phase regressions.
Neither tests nor smoke require Ollama. See PHASE5_REPORT.md for final results.

## Arise Activity Visualizer (Phase 6)

The AI workspace now presents a separate activity orbit above the current request.
The original OpenArise logo remains a static image, unchanged. Lightweight CSS
animates one activity particle; no animation package or backend service was added.

`src/workspace/activity.ts` projects the existing validated AI result and returned
events into `ActivityPresentation` and `ActivityEvent`. The component at
`src/components/Activity/AriseActivityVisualizer.tsx` only presents these DTOs.
It does not poll, generate events, infer progress, or advance through timed stages.

Three provenance labels make the synchronous limitation explicit:
- **ACTUAL_STATE** means the last returned result, not live telemetry.
- **RECORDED_ACTIVITY** means a user-selected event from returned history.
- **UNAVAILABLE_ACTIVITY** means no current agent observation is available.
  Submitting describes local transport only; it does not imply thinking/running.

Supported visuals are idle, submitting, running, waiting_for_permission, failure,
recovering, verifying, completed, unverified, denied, cancelled and unavailable.
Running/recovery/verification may be inspected from backend-recorded events;
no state is synthesized when it has not been returned. The exact recorded backend
state remains visible. Unknown states stay unavailable. No percentages or ETA
are generated.

Current completed/verified presentation requires both agent success and
CompletionGate VERIFIED. Unverified remains unverified even if another metadata
field suggests success. A recorded COMPLETED event is not a verification result
and does not receive the verified check mark. Tool success is independent of
request verification. Failure, denied, cancelled and unavailable remain distinct.

The bounded, scrollable history retains backend timestamps and request/tool IDs.
Tool names come only from the existing allowlisted result metadata; a tool outcome
is associated only with its finished event. Arbitrary event details, prompts,
arguments, source, environment variables and raw errors are not copied into the
visualizer. Missing outcomes are explicitly not supplied. Existing permission
cards and safe resource labels remain in the AI panel unchanged.

Native buttons select recorded observations or return to the current result;
history can be collapsed. State text uses a polite accessible status region.
The decorative orbit is hidden from assistive technology. Text, symbols and border
styles carry meaning without motion or color alone. Reduced-motion preferences
disable every activity animation/transition and leave static indicators.
The orbit and history shrink at short window heights; the existing AI panel
toggle preserves editor space at smaller widths.

`ActivityEvent` defines event ID, request ID, timestamp, state, title, detail,
optional tool/resource fields, outcome and provenance. A future streaming adapter
could feed this presentation contract, with explicit provenance/version changes,
without replacing the visual component. No WebSocket transport, fake stream,
live-progress claim or semantic activity generation is implemented.

Phase 6 tests use deterministic responses with no Ollama. Smoke coverage includes
local submission, permission, failure/unverified/verified distinctions, recorded
history, reduced-motion browser emulation, static logo hash/style, and overflow
checks at all three requested sizes. See PHASE6_REPORT.md for final validation.

## Permission, recovery and verification (Phase 7)

The AI panel displays a retained permission card with the action's allowlisted
tool name, risk, safe scope and decision state. Allow delegates approval and then
resume using the original request/tool IDs. Deny and Cancel use the existing
backend commands. Buttons remain disabled while a decision is pending; a
transport error requires refreshing the retained request before Allow/Resume.
Returned completed, denied, cancelled and failed decisions stay in session
history. No local permission policy or recovery execution was added.

Failure/recovery cards display returned category, severity, diagnosis, attempt
state and retry/retest details when supplied. Missing details say unavailable or
not reported. The current backend action response supplies recovery counts and
recorded lifecycle events, but does not emit a detailed RecoveryResult or
severity. A recorded recovery attempt therefore never implies recovery success.
The UI can present an explicitly returned RecoveryResult; that completed/blocked
presentation is exercised only with deterministic fixtures in this phase.

Verification shows the CompletionGate status, requirement coverage, evidence
summaries, stale/superseded flags, missing/invalid evidence and contradictory
evidence. Test executions are backend test-tool calls, not test case counts.
Final states are VERIFIED, UNVERIFIED, FAILED, BLOCKED and UNAVAILABLE. Only a
consistent returned successful action and VERIFIED gate result can display
VERIFIED. Transport errors, permission decisions, failed tools/evidence,
active stale evidence or contradictory gate fields withhold verified completion.
The Phase 6 activity visualizer uses the same completion presentation rule.

Main tags its injected test adapter's responses as test_fixture. The AI panel
and activity visualizer visibly label TEST FIXTURE and say no live AI validation.
Normal production transport is labelled BACKEND RESPONSE / last returned data.
An absent source label is shown as SOURCE NOT REPORTED. There is no renderer
fixture switch, new IPC method, network service or alternate production backend.

Phase 7 tests use deterministic fixtures and controlled providers.
**Live Ollama permission, recovery and verification flows remain unverified.**
See [PHASE7_REPORT.md](PHASE7_REPORT.md) for exact files, counts and validation.
Phase 7 did not repackage the application. Phase 8 rebuilds the current desktop;
its release results are recorded below.

## Final desktop polish and release (Phase 8)

The application, native window and executable are named **OpenArise**, version
**0.1.0**. The supplied static orbit logo and its existing Windows icon are
preserved. The production entry is `dist-electron/entry.cjs`; it starts the same
main/preload/backend architecture used by the desktop. A production launch needs
no Vite server, debug flags or user-data override.

Fresh launch shows an empty local workspace with three steps for opening a
Python project, editing/saving, and using Run/Test. No demo project or AI
activity is supplied. There is no new-project generator: create a Python folder
normally in Windows, then use Open Project. Ollama remains optional for the
local editor/Python/pytest workflow and required for model-driven AI requests.

Keyboard focus covers buttons, inputs, selects, summaries and resize controls.
Shared scrollbars and button/error styles keep the existing navy/blue/violet
panels consistent. Short windows retain scrolling access to permissions and
verification; the empty welcome terminal is compact. Workspace errors remain
visible when intelligence is selected. Renderer failures show an explicit
fallback with a separate discard confirmation before reload. A crashed renderer
shows a native error. Native close and unsaved/conflict guards remain in place;
Ctrl+R/F5 cannot reload a dirty workspace.

The validated release file is `release/OpenArise-0.1.0-win-x64.zip`, accompanied
by `SHA256SUMS.txt` and `RELEASE_NOTES.txt`. Extract the complete ZIP to a writable
folder and run `OpenArise.exe`; do not run from inside the archive. Preserve the
full application folder and its resources when copying it. The portable and
Setup EXEs under `.packaging/phase8-blocked-artifacts/` are review candidates:
their execution is BLOCKED on this host, not validated.

Packaging copies only the compiled application, existing icon, backend modules,
desktop Python hosts and isolated runtime. It excludes Node development
packages, global Python site-packages, pip, standard-library demo/test tooling,
bytecode, caches, logs and local project state. Pytest and its runtime dependencies
remain included. No dependency was installed for Phase 8.

Release QA can be repeated with the existing installed tooling:

```powershell
node scripts/validate-windows-package.mjs release/win-unpacked
# Also accepts an extracted ZIP or portable application directory.
```

This validates archive contents against the current build, bundled imports,
real file read/save, backend project/environment responses and supervised Python
and pytest with PATH restricted to System32. It does not prove live Ollama or an
interactive packaged project workflow. The Windows observation helper records
only the selected executable's native visible window and first-run capture;
neither helper is packaged or accessible through IPC.

See [PHASE8_REPORT.md](PHASE8_REPORT.md) and
[RELEASE_VALIDATION.md](RELEASE_VALIDATION.md) for exact test totals, artifact
hashes, launch evidence, installer results and remaining acceptance items.
**Live Ollama/model permission, recovery and verified completion remain
NOT VERIFIED.** No full production-readiness claim is made.