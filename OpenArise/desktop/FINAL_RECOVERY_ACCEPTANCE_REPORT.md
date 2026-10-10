# Final recovery acceptance — October 9, 2026

This report describes the current working tree. Earlier release hashes and human
checks remain historical. No commit, push, dependency installation, `.gitignore`
edit, or Windows policy bypass was performed.

## Root cause and changes

Qwen could return an incomplete or reordered tool batch despite an explicit
ordered request. Counting requested executions alone did not bind their order or
literal write content. Numbered procedural steps also became separate requirement
identities, making a single workflow harder to prove consistently. Ollama's
generic action schema offered every tool, with duplicated schema text, even when
the user explicitly named one tool or an ordered sequence.

The existing orchestrator now recognizes explicitly named tool instructions,
constrains real model generation to that requested sequence, and rejects missing,
extra, reordered, or changed literal arguments before asking for approval or
executing. Numbered ordered workflows retain one requirement identity. General
natural-language tasks remain model planned. No tool, result, evidence, repair,
or successful completion is synthesized by the instruction parser.

Every mutation and execution still goes through the existing exact tool-call
permission manager and tools. Recovery still uses the actual diagnosis/planner,
separate approvals, checkpoint, mandatory retest, evidence ledger and CompletionGate.
The gate still rejects stale or unresolved failed proof. Registered Python,
frontend, backend and full-stack capabilities remain available.

Changed production files in this continuation:

- `ai-engine/app/agent/requested_steps.py` (new)
- `ai-engine/app/agent/orchestrator.py`
- `ai-engine/app/llm/ollama.py`
- `ai-engine/app/verification/requirements.py`

Regression/QA files:

- `ai-engine/tests/test_requested_step_planning.py` (17 focused tests)
- `desktop/tests/electron-product-flow.cjs` (targeted rerun switches and accurate
  no-write recovery failure assertion; actual recovery writes still require rollback)

Only numeric token/time metrics are logged. Source, prompts, model prose and
credentials are excluded from those diagnostics. Timeout defaults are unchanged.
Electron IPC and contextIsolation/nodeIntegration/sandbox/webSecurity settings
were not changed.

## Tests

| Check | State | Actual result |
| --- | --- | --- |
| Full backend pytest after final production edits | VERIFIED | **278 passed**, 98.38 seconds |
| Desktop Python-host integration against updated backend | VERIFIED | **55 passed**, 18.125 seconds |
| Desktop renderer/main Vitest | VERIFIED, carried forward | **276 passed** in the preceding source validation; no renderer/main production changes in this continuation |
| Desktop total | VERIFIED with run provenance above | **331 = 276 Vitest + 55 Python host**; not represented as a fresh full npm test rerun |
| Previous production build / production and development smoke | VERIFIED, carried forward | No desktop bundle changes; intentionally not repeated |

Regressions cover exact sequence/literal arguments, no approval/no execution for
invalid plans, denied and unapproved real writes, exactly-once Allow, unchanged
requirement identity, strict scalar types, actual multiline content, and safe
numeric inference diagnostics. The full suite also retains fresh evidence,
recovery rollback and CompletionGate refusal tests. Assertions were not removed.

## Real Qwen evidence

All following model, backend, filesystem and test results are real, using
`qwen2.5-coder:7b` at `127.0.0.1:11434`. The Electron QA driver supplies disposable
projects/native picker selections and bounded Allow/Deny UI button decisions.
This is renderer → preload → main → Python/backend → Qwen validation, not a new
human-operated acceptance claim. `fixtureResponses` is false.

### Multi-step recovery and fresh verification — VERIFIED

Evidence: `.packaging/product-audit/run-1791550362869/evidence.json`.
Request: `52baa17b-46a9-49ab-853e-e24d9134a1be`.
Requirement: `4911849d-3314-4011-8f99-650fc2b66c74`.

The real initial batch executed in the requested order: baseline pytest exit 0,
approved literal addition fault in `backend/math_ops.py`, pytest exit 1. Real
diagnosis/recovery planning requested a separately approved correction and retest.
The mandatory fresh pytest exited 0. Backend returned RECOVERED / COMPLETED and
CompletionGate VERIFIED, 1/1 requirement covered, six evidence records, three
test executions and one recovery attempt.

- Old baseline proof `db0e711d-e9ba-49e7-9051-56701523ffef` is stale/superseded.
- Failed proof `7e06c1e5-8bc8-489a-9e1d-008690e3fec8` is retained and explicitly resolved.
- Fresh retest proof `62c568a5-d046-48c4-94f8-a30e3401e775` exited 0 and was current.

An actual later change to `frontend/src/main.tsx` invalidated that proof. Backend
refresh returned UNVERIFIED / CompletionGate NOT_VERIFIED. The UI never inferred
verification from historical RECOVERED. Settled real outcome screenshots and
geometry checks passed at 1320x880, 1050x740 and 760x540.

### Failure refusal — VERIFIED; failed recovery itself is not successful

In the same evidence file, request `065dbc00-f50a-4d5f-bf63-fb1aaaaf1974` returned
FAILED / CompletionGate NOT_VERIFIED after actual failing pytest and a mandatory
failing recovery retest. Qwen's recovery plan was read-only, so it made no recovery
writes. Recovery status FAILED is correct; ROLLED_BACK would falsely imply a
rollback occurred. Original tests, including the intentional always-failing test,
remained unchanged. The approved original addition fault remained in place.

The QA driver initially incorrectly required ROLLED_BACK for every failed plan.
It now checks FAILED for a plan without recovery writes, and requires ROLLED_BACK
plus checkpoint restoration whenever recovery actually writes. The final targeted
UI rerun passed, exit 0, with evidence in
`.packaging/product-audit/run-1791551778275/evidence.json`. Backend and actual UI
returned FAILED / recovery BLOCKED / CompletionGate NOT_VERIFIED. The returned
reason was **Recovery action count is invalid.** That invalid model plan executed
no recovery actions. Original test bytes and the pre-recovery fault checkpoint
were preserved. The FAILED heading and blocked recovery explanation passed
responsive screenshot/geometry checks at all three requested sizes. This proves
safe refusal, not a successful repair or rollback in this no-write case.

### Frontend timeout investigation and real denial rerun — VERIFIED

Evidence: `.packaging/product-audit/run-1791551231648/evidence.json`.
Both frontend write and detected npm test command reached actual permission
requests; Deny prevented file mutation and command execution. Driver exit 0.
This run used the unchanged **180-second** Ollama timeout.

The model is CPU-loaded (`size_vram=0`, context 4096). A full ordered recovery
planning call logged 133.185 seconds prompt evaluation plus 50.963 seconds output
generation: **184.148 seconds** of inference alone. That exceeds the default
180-second request deadline before permission can even be requested. Narrow
explicit schemas reduce prompt/branch overhead: frontend denial generation logged
73.254 + 20.611 = **93.865 seconds**, and command denial 64.928 + 32.863 =
**97.790 seconds**. There is no timeout fallback that executes tools or pretends
success. Complex recovery QA used the existing supported 600-second environment
setting; the default was not raised and slower CPU requests can still time out.

## Latest NSIS acceptance

Current source rebuild: `.packaging/final-recovery-release-20261009/`.
NSIS build and per-user install are VERIFIED, both exit 0. Installed payload
comparison is VERIFIED: 30 ASAR entries, 1,599 files, all **82 backend** and **five
host** source files match current source bytes. Its isolated bundled runtime
passed real backend/project imports, read/save, supervised Python and pytest
(**1 passed**) with only Windows System32 on PATH. No development caches, secrets,
tests, node_modules, logs or local project state were included.

Installer: `OpenArise-0.1.0-win-x64-setup.exe`, **127,304,074 bytes**,
SHA-256 `D2EE868726D70F17574E5959F973402AF3FF2C855FF51B994ADD032D1BD1ADEE`.
Authenticode: **NotSigned**; builder's signing log is not publisher-signing proof.
Normal installed launch is **VERIFIED**: main process 21188 was launched with only
the executable path, no debug arguments, profile override or Vite server. Native
Computer Use returned exactly one installed OpenArise window (853278), and its
screenshot showed a rendered empty workspace, static identity, no selected project
and idle activity. Alt+F4 closed it normally; refreshed native inventory and process
checks confirmed no OpenArise window/process remained. Ordinary per-user NSIS
uninstall (`/currentuser /S`) is **VERIFIED**, exit 0; the installed executable was
removed and no OpenArise uninstall registration remained. The installer was also
tested with its ordinary silent per-user installation (`/S /D=<QA target>`).
No older installer is claimed to contain this continuation's new Python module.

## Final results for this continuation

| Requested check | State | Evidence |
| --- | --- | --- |
| Multi-step real Qwen recovery | VERIFIED | Requested ordered baseline/write/failure, real separately approved repair, fresh retest exit 0, CompletionGate VERIFIED |
| Stale proof refusal | VERIFIED | Real frontend mutation made proof stale; gate NOT_VERIFIED |
| Intentional unsuccessful recovery | VERIFIED refusal; recovery BLOCKED | Real failing tests and invalid model recovery plan; FAILED UI and gate NOT_VERIFIED, no recovery execution |
| Frontend real Qwen permission timeout rerun | VERIFIED | Write and command Deny passed at default 180 seconds; no mutation or command execution |
| Latest NSIS build/install/payload/normal visible launch/uninstall | VERIFIED | New installer, current source bytes, exactly one native visible window, normal close, uninstall exit 0 and registration removed |
| Publisher signing / clean independent Windows environment | BLOCKED acceptance items | No signing credential or independent clean test machine available; no success claim |

Documentation changed: this report, `FINAL_ACCEPTANCE_REPORT.md`,
`desktop/README.md`, and `desktop/RELEASE_VALIDATION.md`. The task's bounded checks
passed; this is not a claim of universal model reliability or full distribution
readiness. All prior user work and the `.gitignore` bytes were preserved.

## Limits

Earlier portable execution was BLOCKED by Windows Application Control, and MSI's
mandatory WiX validation was BLOCKED with LGHT1105. Neither was bypassed. Old ZIP
and portable artifacts predate this continuation and are not current releases.
Publisher signing and a clean Windows machine remain unverified. Latest installed
live AI was not repeated: the current-source live Qwen flow and exact installed
source-byte comparison are separate proofs, not a claim of a new installed AI run.
The bounded
current task does not repeat previously passed Python/frontend/full-stack editing,
build/API checks or add feature phases.
