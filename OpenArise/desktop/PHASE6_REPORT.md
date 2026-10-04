# Person 3 — Phase 6 audit

Phase 6 only: Arise Activity Visualizer. Final audit date: 2026-10-04.

## Validation

| Check | Result |
| --- | --- |
| npm test | 195 passed: 167 Vitest tests across 14 files and 28 Python desktop-host tests |
| npm run build | Passed, including renderer/main TypeScript and Electron bundles |
| npm run test:smoke | Passed with final short-window layout and expanded activity visibility |
| npm run test:smoke:dev | Passed with final short-window layout and expanded activity visibility |
| Backend .venv/Scripts/python.exe -m pytest | 161 passed; 0 failed, 0 skipped, 0 warnings |

Production screenshots inspected at C:/Users/nithi/AppData/Local/Temp/openarise-phase6-tjKAk1/. Development smoke screenshots are at C:/Users/nithi/AppData/Local/Temp/openarise-phase6-Z21efn/. Both directories are transient OS test artifacts.

The build retains the existing non-failing size warning for the lazy local Monaco
bundle. No animation library, dependency or Python environment was installed.

## Implementation

The AI panel has a separate CSS activity orbit with a single light particle,
visible state text, request ID and collapsible scrollable activity history.
The original circular blue-violet logo remains unchanged and static.

The presentation adapter consumes the existing validated AI history/result types.
It copies allowlisted event/state labels, timestamps, IDs and safe tool outcomes.
It does not create backend events, poll, advance through timed stages, generate
percentages/ETA, or expose arbitrary metadata. Unknown states remain unavailable.

Three provenance labels distinguish:
- ACTUAL_STATE: the latest returned result, not live telemetry.
- RECORDED_ACTIVITY: a selected historical returned event.
- UNAVAILABLE_ACTIVITY: agent observation is absent; submitting is local transport.

All twelve requested visual states are supported. Running, recovering and
verifying are illustrated only from reported state/event data. A recorded
COMPLETED event remains separate from verification; it receives no verified check.
Current verified completion requires both agent success and CompletionGate
VERIFIED. Unverified, failure, denied, cancelled and unavailable are distinct.

History shows actual returned timestamps and request/tool IDs. Tool outcomes are
attached only to finished events and never retroactively to start events.
Permission cards and safely projected resources keep the existing workflow.
The visualizer introduces no permission or verification engine changes.

Keyboard-accessible native controls inspect recorded events and return to the
current result. Text carries state meaning; the decorative orbit is aria-hidden,
with polite accessible status updates. Reduced motion disables all activity
animations/transitions and retains static indicators. Completed motion runs
briefly once and settles; other states use restrained motion/borders.

At small heights, context/composer/history spacing contracts to preserve a
readable current activity area. The existing AI toggle retains editor usability.
Smoke checks three window sizes: 1440x900, 1050x740 and 760x540.

## Tests and final boundary

New tests cover idle/local submission, all result states, recorded running/
recovery/verifying/completion, unknown states, verification contradictions,
unavailable responses, timestamps, safe field selection, tool outcome timing,
foreign-event rejection, accessibility and reduced motion.

Electron smoke adds deterministic submission delay and permission/failure/
unverified/verified fixtures through the existing main/preload boundary.
It checks returned history, reduced motion with browser media emulation,
static logo style/hash, readable conversation height and horizontal overflow,
plus all earlier editor, AI, intelligence and terminal regressions.
Neither desktop tests nor smoke require Ollama.

No ai-engine source, backend contract, preload/main security settings, Person 1
system or Person 2 system was changed. Protected tracked-path diff/status are empty.
No fabricated production activity or live-streaming claim was introduced.
No WebSocket, Luminous, advanced recovery, cloud, installer or updater was added.

The future ActivityEvent DTO provides eventId, requestId, timestamp, state, title,
detail, toolId/toolName/resource, outcome and provenance. Future streaming needs
an explicit adapter and provenance update; no live channel exists in this phase.

Logo SHA-256:
7170a7b5a083b27fa852082e8ae42db47419f52376aefc1a281748eb2b6486e3

## Changed files

All twelve Phase 6 files are under desktop/. Previous phases' desktop files were
already untracked, so Git cannot provide a Phase-5-to-Phase-6 diff. Generated
ignored build/cache artifacts are excluded from this list.

| File | Change |
| --- | --- |
| src/types/activity.ts | New presentation/event contract |
| src/workspace/activity.ts | New factual, allowlisted presentation adapter |
| src/components/Activity/AriseActivityVisualizer.tsx | New orbit/state/history component |
| src/styles/activity.css | New restrained motion, state and reduced-motion styling |
| src/components/AI/AIPanel.tsx | Integrate visualizer and preserve permission/results |
| src/styles/ai.css | Improve short-window current activity visibility |
| tests/activity.test.tsx | New semantics, metadata, accessibility and motion tests |
| tests/ai-panel.test.tsx | Scope existing result assertions within the result card |
| tests/fixtures/smoke-backend.cjs | Offline delayed submission and distinct result fixtures |
| tests/electron-smoke.cjs | Activity/history/motion/logo/responsive smoke coverage |
| README.md | Phase 6 architecture, reality rule and extension documentation |
| PHASE6_REPORT.md | This audit |

No staging, commit or push performed. Stop after Phase 6.
