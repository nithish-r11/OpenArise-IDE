// Real Qwen acceptance: production renderer/preload/main/Python, no backend fixtures.
// Only disposable project selection and bounded UI approval choices are supplied.
const { app, BrowserWindow, dialog, ipcMain } = require('electron');
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const { createHash, randomUUID } = require('node:crypto');
const base = path.resolve(__dirname, '../.packaging/live-permission-recovery-' + Date.now());
const roots = ['success', 'failure'].map(name => path.join(base, name));
const GOOD = 'def multiply(a, b):\n    return a * b\n';
const TEST = 'from math_ops import multiply\n\ndef test_multiply():\n    assert multiply(3, 4) == 12\n    assert multiply(-2, 5) == -10\n';
const ALWAYS_FAIL = 'def test_controlled_failure():\n    assert False, "Acceptance: preserve this always-failing test"\n';
for (const root of roots) {
  fs.mkdirSync(root, { recursive: true });
  fs.writeFileSync(path.join(root, 'main.py'), 'from math_ops import multiply\nprint("LIVE_REAL_SOURCE", multiply(3, 4))\n');
  fs.writeFileSync(path.join(root, 'math_ops.py'), GOOD);
  fs.writeFileSync(path.join(root, 'test_math_ops.py'), TEST);
}
fs.writeFileSync(path.join(roots[1], 'test_unrecoverable.py'), ALWAYS_FAIL);
const hash = bytes => createHash('sha256').update(bytes).digest('hex');
function snapshot(root) {
  return Object.fromEntries(fs.readdirSync(root).filter(name => !['.openarise', '.pytest_cache', '__pycache__'].includes(name)).sort().map(name => {
    const file = path.join(root, name); assert.equal(fs.statSync(file).isFile(), true, 'Only expected disposable source files');
    const bytes = fs.readFileSync(file); return [name, { sha256: hash(bytes), content: bytes.toString('utf8') }];
  }));
}
let rootIndex = 0, projectId;
const evidence = { fixtureResponses: false, model: process.env.OLLAMA_MODEL || 'qwen2.5-coder:7b', base,
  scope: 'Visible production Electron UI/preload/main/BackendService/AgentOrchestrator/Ollama; supplied disposable native picker and explicit UI approval choices',
  initial: roots.map(snapshot), results: [], records: [], stage: 'launch', status: 'RUNNING' };
const persist = () => fs.writeFileSync(path.join(base, 'evidence.json'), JSON.stringify(evidence, null, 2));
const recordHandle = ipcMain.handle.bind(ipcMain);
ipcMain.handle = (channel, handler) => recordHandle(channel, async (...args) => {
  const result = await handler(...args);
  if (result?.kind === 'backend' || result?.kind === 'unavailable') {
    if (result.kind === 'backend') assert.equal(result.source, 'backend', 'Real production backend required');
    evidence.records.push({ timestamp: new Date().toISOString(), method: args[1]?.method, command: args[1], result, files: snapshot(roots[rootIndex]) }); persist();
  }
  return result;
});
app.setPath('userData', path.join(base, 'profile'));
dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [roots[rootIndex]] });
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const timer = setTimeout(() => { evidence.status = 'BLOCKED'; evidence.error = 'Acceptance deadline reached'; persist(); app.exit(1); }, 2700000);
app.once('browser-window-created', (_event, window) => {
  const js = code => window.webContents.executeJavaScript(code);
  function stage(name) { evidence.stage = name; persist(); console.log('LIVE ACCEPTANCE:', name); }
  function record(name, details) { evidence.results.push({ case: name, status: 'VERIFIED', timestamp: new Date().toISOString(), ...details }); persist(); }
  async function until(check, label, budget = 30000) {
    const end = Date.now() + budget;
    while (Date.now() < end) { if (await check()) return; await delay(100); }
    throw new Error('Timed out: ' + label);
  }
  async function click(text, selector = 'button') {
    const target = '[...document.querySelectorAll(' + JSON.stringify(selector) + ')].find(b=>b.textContent.trim()===' + JSON.stringify(text) + '&&!b.disabled)';
    await until(() => js('!!(' + target + ')'), 'enabled ' + text); await js(target + '.click()');
  }
  async function capture(name) {
    // DOM commits can precede Chromium's captured compositor frame.
    await js('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))');
    await delay(200);
    fs.writeFileSync(path.join(base, name + '.png'), (await window.webContents.capturePage()).toPNG());
    evidence[name + 'UI'] = await js('document.querySelector(".ai-workspace")?.innerText || document.body.innerText'); persist();
  }
  async function requestRecord(after, method, budget = 850000) {
    await until(() => Promise.resolve(evidence.records.slice(after).some(row => row.method === method)), method + ' response', budget);
    const row = evidence.records.slice(after).find(row => row.method === method);
    assert.equal(row.result.kind, 'backend', JSON.stringify(row.result));
    assert.equal(row.result.response.success, true, JSON.stringify(row.result.response.error));
    return row.result.response.data;
  }
  async function bridge(method, target, call) {
    return js('window.openarise.request(' + JSON.stringify({ request_id: randomUUID(), method, params: {request_id: target, tool_call_id: call} }) + ',' + JSON.stringify(projectId) + ')');
  }
  async function openProject(index) {
    rootIndex = index; stage('open-' + path.basename(roots[index])); await click('Open Project');
    await until(() => js('document.querySelector(".ai-context")?.textContent.includes(' + JSON.stringify(path.basename(roots[index])) + ') && !document.querySelector(".ai-mode button").disabled'), 'actual project context', 60000);
    const recent = await js('window.openarise.project.recentProjects()'); assert.equal(recent.ok, true);
    projectId = recent.data.find(project => project.rootPath === roots[index])?.id; assert.ok(projectId);
    await js('if(!document.querySelector(".ai-workspace").classList.contains("ai-expanded"))document.querySelector(".ai-toggle").click()');
  }
  async function ask(prompt, actions = false) {
    await until(() => js('!document.querySelector(".ai-mode button").disabled'), 'idle composer');
    await click(actions ? 'Make changes' : 'Answer only', '.ai-mode button');
    await js('document.querySelector("#ai-prompt").focus()'); await window.webContents.insertText(prompt);
    assert.equal(await js('document.querySelector("#ai-prompt").value'), prompt, 'Exact UI prompt');
    const before = evidence.records.length; await click('Send ↗');
    return requestRecord(before, 'request_agent_execution');
  }
  async function decide(result, choice, resource) {
    const pending = result.pending_action; assert.ok(pending, 'Real model must generate a pending action');
    assert.ok(['write_file', 'execute_tests'].includes(pending.tool_name), 'No unrelated tools may be approved');
    if (pending.tool_name === 'write_file') assert.equal(pending.resource, resource);
    const root = roots[rootIndex]; assert.equal(fs.readFileSync(path.join(root, 'test_math_ops.py'), 'utf8'), TEST);
    if (rootIndex === 1) assert.equal(fs.readFileSync(path.join(root, 'test_unrecoverable.py'), 'utf8'), ALWAYS_FAIL);
    await until(() => js('document.querySelector(".ai-permission[data-state=permission_required]")?.textContent.includes(' + JSON.stringify(pending.tool_call_id) + ') && !![...document.querySelectorAll(".permission-actions button")].find(b=>b.textContent===' + JSON.stringify(choice) + '&&!b.disabled)'), 'exact reviewed permission');
    const before = evidence.records.length; await click(choice, '.permission-actions button');
    const next = await requestRecord(before, choice === 'Allow' ? 'resume_agent_execution' : 'deny_agent_action');
    const methods = evidence.records.slice(before).map(row => row.method);
    assert.deepEqual(methods, choice === 'Allow' ? ['approve_agent_action', 'resume_agent_execution'] : ['deny_agent_action']);
    for (const row of evidence.records.slice(before)) {
      assert.equal(row.command.params.request_id, pending.request_id);
      assert.equal(row.command.params.tool_call_id, pending.tool_call_id);
    }
    console.log('ACTUAL RESULT:', next.status, next.current_state, next.pending_action?.tool_name || '-', next.data.recovery?.status || '-');
    return next;
  }
  async function finish(result, name) {
    let steps = 0, recoveryCheckpoint;
    while (result.pending_action) {
      assert.ok(++steps <= 12, 'Bounded approval sequence');
      if (result.data.recovery && result.pending_action.tool_name === 'write_file' && recoveryCheckpoint === undefined) {
        recoveryCheckpoint = fs.readFileSync(path.join(roots[rootIndex], 'math_ops.py'), 'utf8');
        evidence[name + 'Checkpoint'] = { content: recoveryCheckpoint, sha256: hash(Buffer.from(recoveryCheckpoint)) }; persist();
      }
      result = await decide(result, 'Allow', 'math_ops.py');
      assert.equal(fs.readFileSync(path.join(roots[rootIndex], 'test_math_ops.py'), 'utf8'), TEST);
      if (rootIndex === 1) assert.equal(fs.readFileSync(path.join(roots[1], 'test_unrecoverable.py'), 'utf8'), ALWAYS_FAIL);
    }
    return { result, recoveryCheckpoint };
  }
  window.webContents.once('did-finish-load', async () => {
    try {
      await until(() => js('!!document.querySelector(".open-project") && document.visibilityState==="visible"'), 'visible OpenArise');
      assert.equal(window.isVisible(), true); assert.equal(BrowserWindow.getAllWindows().length, 1);
      assert.deepEqual(Object.fromEntries(['contextIsolation','nodeIntegration','sandbox','webSecurity'].map(key => [key,window.webContents.getLastWebPreferences()[key]])), {contextIsolation:true,nodeIntegration:false,sandbox:true,webSecurity:true});
      record('one-visible-secure-window', { title: window.getTitle() }); await capture('launch');
      await openProject(0); await until(() => js('document.querySelector(".ollama-status")?.textContent.includes("Ollama detected")'), 'real Ollama availability', 60000);
      stage('real-qwen-readonly');
      const initial = snapshot(roots[0]);
      const read = await ask('Inspect the actual supplied project without modifying files or running code. Return exactly three concise lines, each beginning with its actual filename: main.py: identify this entry point and the exact printed label; math_ops.py: describe what multiply computes; test_math_ops.py: list both actual test input/output examples. Do not omit the filenames. State only facts supported by the supplied source.');
      assert.equal(read.data.tool_results.length, 0); assert.equal(read.pending_action, null);
      assert.match(read.data.model_response, /main\.py/); assert.match(read.data.model_response, /math_ops\.py/); assert.match(read.data.model_response, /test_math_ops\.py/);
      assert.match(read.data.model_response, /LIVE_REAL_SOURCE/); assert.match(read.data.model_response, /multipl|product|a\s*\*\s*b/i);
      assert.match(read.data.model_response, /12/); assert.match(read.data.model_response, /-10/);
      assert.deepEqual(snapshot(roots[0]), initial); record('actual-project-readonly', { result: read, files: snapshot(roots[0]) }); await capture('readonly');
      stage('no-approval-and-deny');
      let pending = await ask('Use exactly one write_file tool call to CREATE denied_probe.py containing exactly print("DENIED_PROBE") followed by a newline. Do not execute code or use other tools. This is a request to propose the file action for the desktop permission card.', true);
      assert.equal(pending.status, 'permission_required'); assert.equal(pending.pending_action.tool_name, 'write_file'); assert.equal(pending.pending_action.resource, 'denied_probe.py');
      assert.deepEqual(snapshot(roots[0]), initial);
      const missing = await bridge('resume_agent_execution', pending.request_id, pending.pending_action.tool_call_id);
      assert.equal(missing.kind, 'backend'); assert.equal(missing.response.data.status, 'permission_required');
      assert.deepEqual(snapshot(roots[0]), initial); record('missing-approval-no-mutation', { result: missing.response.data, files: snapshot(roots[0]) });
      const denied = await decide(pending, 'Deny', 'denied_probe.py'); assert.equal(denied.status, 'denied');
      assert.ok(denied.data.tool_results.every(tool => !tool.executed)); assert.deepEqual(snapshot(roots[0]), initial);
      const deniedReplay = await bridge('resume_agent_execution', pending.request_id, pending.pending_action.tool_call_id);
      assert.equal(deniedReplay.response.success, false); assert.deepEqual(snapshot(roots[0]), initial);
      record('explicit-deny-no-mutation', { result: denied, rejectedResume: deniedReplay, files: snapshot(roots[0]) }); await capture('denied');
      stage('explicit-allow-exactly-once');
      pending = await ask('Use exactly one write_file tool call to CREATE approved_probe.py containing exactly print("APPROVED_ONCE") followed by a newline. Do not execute code or use other tools. Propose the actual file action for desktop approval.', true);
      assert.deepEqual(snapshot(roots[0]), initial);
      const allowed = await decide(pending, 'Allow', 'approved_probe.py');
      assert.equal(fs.readFileSync(path.join(roots[0], 'approved_probe.py'), 'utf8'), 'print("APPROVED_ONCE")\n');
      assert.equal(allowed.data.tool_results.filter(tool => tool.executed && tool.tool_call_id === pending.pending_action.tool_call_id).length, 1);
      const afterAllow = snapshot(roots[0]); const replay = await bridge('resume_agent_execution', pending.request_id, pending.pending_action.tool_call_id);
      assert.equal(replay.response.success, false); assert.deepEqual(snapshot(roots[0]), afterAllow);
      for (const [name, content] of Object.entries(initial)) assert.deepEqual(afterAllow[name], content);
      record('explicit-allow-once', { result: allowed, rejectedReplay: replay, files: afterAllow }); await capture('allowed');
      stage('real-failure-recovery-retest-gate');
      let outcome = await finish(await ask('Demonstrate controlled recovery and finish with correct multiplication and original tests passing. Produce ONE tool_call action with all THREE ordered calls: execute_tests to capture baseline; write_file path math_ops.py overwrite=true content "def multiply(a, b):\\n    return a + b\\n" introducing a fault; execute_tests exposing that fault. Then let the recovery engine repair only math_ops.py to return a * b and retest. Never modify main.py, approved_probe.py or any tests. Original tests require multiply(3,4)==12 and multiply(-2,5)==-10. Do not claim completion without fresh passing proof.', true), 'success');
      const success = outcome.result;
      assert.equal(success.status, 'success'); assert.equal(success.data.recovery?.status, 'RECOVERED'); assert.equal(success.data.verification.overall_status, 'VERIFIED');
      assert.ok(success.data.tool_results.some(tool => tool.executed && tool.tool_name === 'execute_tests' && !tool.success && tool.exit_code !== 0));
      assert.ok(success.data.evidence.some(proof => proof.evidence_type === 'TEST_FAIL' && proof.resolved_by));
      assert.ok(success.data.evidence.some(proof => proof.evidence_type === 'TEST_PASS' && proof.stale && proof.superseded));
      assert.ok(success.data.evidence.some(proof => proof.evidence_type === 'TEST_PASS' && !proof.stale && !proof.superseded && proof.exit_code === 0));
      assert.equal(new Set(success.data.evidence.map(proof => proof.requirement_id)).size, 1);
      await until(() => js('document.querySelector(".ai-completion>strong")?.textContent==="VERIFIED"'), 'authoritative gate UI');
      record('real-failure-detected', { failedTools: success.data.tool_results.filter(tool => tool.executed && !tool.success) });
      record('real-recovery-fresh-retest-verified', { result: success, files: snapshot(roots[0]) }); await capture('recovered');
      await openProject(1); stage('failed-recovery-and-real-rollback');
      outcome = await finish(await ask('Demonstrate unsuccessful recovery. Produce ONE tool_call action with BOTH ordered calls: write_file path math_ops.py overwrite=true content "def multiply(a, b):\\n    return a + b\\n"; execute_tests on the whole project. Recovery may repair only math_ops.py to multiplication. Preserve main.py and every test unchanged, including deliberately always-failing test_unrecoverable.py. Let the real recovery engine attempt repair and retest; return actual failed or unverified CompletionGate outcome. Never remove or edit tests.', true), 'failure');
      const failure = outcome.result;
      assert.equal(failure.status, 'failure'); assert.equal(failure.data.recovery?.status, 'ROLLED_BACK'); assert.equal(failure.data.verification.overall_status, 'NOT_VERIFIED');
      assert.ok(failure.data.tool_results.filter(tool => tool.executed && tool.tool_name === 'execute_tests' && !tool.success && tool.exit_code !== 0).length >= 2);
      assert.ok(outcome.recoveryCheckpoint); assert.equal(fs.readFileSync(path.join(roots[1], 'math_ops.py'), 'utf8'), outcome.recoveryCheckpoint);
      assert.notEqual(outcome.recoveryCheckpoint, GOOD, 'Rollback must restore the failed pre-recovery checkpoint');
      await until(() => js('document.querySelector(".ai-completion>strong")?.textContent==="FAILED" && document.querySelector(".ai-recovery")?.textContent.includes("Recovery rolled back")'), 'failed rollback UI');
      record('failed-recovery-rollback-refuses-success', { result: failure, checkpoint: evidence.failureCheckpoint, files: snapshot(roots[1]) }); await capture('rolled-back');
      assert.ok(evidence.records.filter(row => row.result.kind === 'backend').every(row => row.result.source === 'backend'));
      evidence.status = 'VERIFIED'; stage('complete'); clearTimeout(timer); console.log('REAL LIVE ACCEPTANCE VERIFIED:', base); app.quit();
    } catch (error) {
      evidence.status = /Timed out|unavailable|transport|deadline/i.test(String(error)) ? 'BLOCKED' : 'FAILED'; evidence.error = String(error);
      try { await capture('failure-at-stop'); } catch { /* Keep the original error. */ }
      persist(); clearTimeout(timer); console.error(error, base); app.exit(1);
    }
  });
});
require('../dist-electron/main.cjs').startDesktop();
