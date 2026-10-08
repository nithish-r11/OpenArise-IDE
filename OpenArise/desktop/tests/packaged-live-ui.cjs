// External release QA only; never packaged or exposed through renderer IPC.
// Launches the real packaged entry/backend/runtime. A loopback Node inspector
// drives existing DOM controls and supplies only disposable native-picker paths.
// It records unchanged real IPC results; no provider/response/tool fixture.
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const root = fs.realpathSync(process.argv[2]);
const base = path.resolve(__dirname, '../.packaging/failure-ui-fix/packaged-ui-' + Date.now());
const GOOD = 'def multiply(a, b):\n    return a * b\n';
const TEST = 'from math_ops import multiply\n\ndef test_multiply():\n    assert multiply(3, 4) == 12\n    assert multiply(-2, 5) == -10\n';
const IMPOSSIBLE = 'def test_controlled_failure():\n    assert False, "Intentional acceptance failure: preserve this test"\n';
const projects = ['success', 'failure'].map(name => path.join(base, name));
for (const project of projects) {
  fs.mkdirSync(project, { recursive: true });
  fs.writeFileSync(path.join(project, 'math_ops.py'), GOOD);
  fs.writeFileSync(path.join(project, 'test_math_ops.py'), TEST);
}
fs.writeFileSync(path.join(projects[1], 'test_unrecoverable.py'), IMPOSSIBLE);
const evidence = { fixture: false, scope: 'Actual packaged renderer/preload/main/bundled backend/real Qwen; external loopback inspector QA, isolated profile and supplied native-picker paths', root, base, results: [] };
const save = () => fs.writeFileSync(path.join(base, 'evidence.json'), JSON.stringify(evidence, null, 2));
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const launchEnv = { ...process.env };
delete launchEnv.ELECTRON_RUN_AS_NODE;
delete launchEnv.NODE_OPTIONS;
const child = spawn(path.join(root, 'OpenArise.exe'), ['--inspect=0', '--user-data-dir=' + path.join(base, 'profile')], { cwd: root, env: launchEnv, windowsHide: false, stdio: ['ignore', 'pipe', 'pipe'] });
let stderr = '', exited = false;
child.stdout.on('data', data => fs.appendFileSync(path.join(base, 'app.log'), data));
child.on('close', code => { exited = true; evidence.exitCode = code; });
let endpointResolve, endpointReject;
const endpoint = new Promise((resolve, reject) => { endpointResolve = resolve; endpointReject = reject; });
child.on('error', endpointReject);
child.stderr.on('data', data => {
  const text = data.toString(); stderr = (stderr + text).slice(-262144);
  fs.appendFileSync(path.join(base, 'app.log'), text);
  const match = stderr.match(/Debugger listening on (ws:\/\/[^\s]+)/);
  if (match) endpointResolve(match[1]);
});
const endpointTimer = setTimeout(() => endpointReject(new Error('Packaged inspector unavailable; cannot infer UI acceptance')), 45000);
let socket, sequence = 0;
const pending = new Map();
function call(method, params) {
  return new Promise((resolve, reject) => {
    const id = ++sequence;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error('Inspector observation timed out')); }, 900000);
    pending.set(id, { resolve, reject, timer }); socket.send(JSON.stringify({ id, method, params }));
  });
}
async function main(expression) {
  const response = await call('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (response.exceptionDetails) throw new Error(response.exceptionDetails.exception?.description ?? response.exceptionDetails.text);
  return response.result.value;
}
const js = expression => main('globalThis.__openariseQa.window.webContents.executeJavaScript(' + JSON.stringify(expression) + ')');
async function until(read, name, budget = 45000) {
  const end = Date.now() + budget;
  while (Date.now() < end) { if (exited) throw new Error('Application exited during ' + name); if (await read()) return; await delay(150); }
  throw new Error('Timed out: ' + name);
}
const responses = () => main('globalThis.__openariseQa.responses');
async function waitResponse(before, method, budget = 750000) {
  let answer;
  await until(async () => { answer = (await responses()).slice(before).find(x => x.method === method); return !!answer; }, 'real ' + method, budget);
  assert.equal(answer.source, 'backend'); assert.equal(answer.response.success, true);
  return answer.response.data;
}
async function ask(prompt) {
  const before = (await responses()).length;
  await js('document.querySelector(".ai-mode button:nth-child(2)").click(); document.querySelector("#ai-prompt").focus()');
  await main('globalThis.__openariseQa.window.webContents.insertText(' + JSON.stringify(prompt) + ')');
  await until(() => js('!document.querySelector(".ai-submit").disabled'), 'send control ready');
  await js('document.querySelector(".ai-submit").click()');
  return waitResponse(before, 'request_agent_execution');
}
async function decide(r, project, deny = false) {
  const p = r.pending_action; assert.ok(p, 'Actual permission must be returned');
  assert.ok(['write_file', 'execute_tests'].includes(p.tool_name), 'Refuse other tool permissions');
  if (p.tool_name === 'write_file') assert.equal(p.resource, 'math_ops.py', 'Refuse edits to tests/unrelated files');
  assert.equal(fs.readFileSync(path.join(project, 'test_math_ops.py'), 'utf8'), TEST);
  if (project === projects[1]) assert.equal(fs.readFileSync(path.join(project, 'test_unrecoverable.py'), 'utf8'), IMPOSSIBLE);
  assert.doesNotMatch(fs.readFileSync(path.join(project, 'math_ops.py'), 'utf8'), /\b(?:import|open|exec|eval|subprocess|os\.|sys\.)\b/);
  await until(() => js('document.querySelector("#ai-history")?.value === ' + JSON.stringify(r.request_id) + ' && document.querySelector(".ai-permission[data-state=permission_required]")?.textContent.includes(' + JSON.stringify(p.tool_call_id) + ') && !![...document.querySelectorAll(".permission-actions button")].find(b => b.textContent === "Allow" && !b.disabled)'), 'matching permission UI');
  const before = (await responses()).length;
  await js('[...document.querySelectorAll(".permission-actions button")].find(b => b.textContent === ' + JSON.stringify(deny ? 'Deny' : 'Allow') + ').click()');
  const next = await waitResponse(before, deny ? 'deny_agent_action' : 'resume_agent_execution');
  assert.equal(fs.readFileSync(path.join(project, 'test_math_ops.py'), 'utf8'), TEST);
  console.log('Actual packaged permission result:', next.status, next.current_state, next.data.recovery?.status);
  return next;
}
async function finish(r, project) {
  let count = 0;
  while (r.pending_action) { assert.ok(++count <= 10, 'Bounded controlled actions'); r = await decide(r, project); }
  return r;
}
async function settled(r, final) {
  await until(() => js('document.querySelector("#ai-history")?.value === ' + JSON.stringify(r.request_id) + ' && document.querySelector(".ai-completion>strong")?.textContent === ' + JSON.stringify(final) + ' && document.querySelector(".ai-recovery")?.dataset.recoveryStatus === ' + JSON.stringify(r.data.recovery.status) + ' && document.querySelector(".ai-verification")?.dataset.verificationStatus === ' + JSON.stringify(r.data.verification.overall_status) + ' && !document.querySelector(".ai-mode button").disabled && !document.querySelector(".permission-actions")'), 'matching settled real final UI');
  const ui = await js('({ result:document.querySelector(".ai-result").innerText, recovery:document.querySelector(".ai-recovery").innerText, verification:document.querySelector(".ai-verification").innerText, source:document.querySelector(".ai-data-source").innerText, activity:document.querySelector(".arise-activity").innerText })');
  assert.ok(ui.result.includes(r.message)); assert.ok(ui.source.includes('BACKEND RESPONSE')); assert.ok(!ui.source.includes('TEST FIXTURE'));
  assert.ok(ui.recovery.includes(r.data.recovery.status)); assert.ok(ui.verification.includes('CompletionGate result: ' + r.data.verification.overall_status));
  for (const value of Object.values(ui)) assert.doesNotMatch(value, /<actual result>|placeholder|demo result/i);
  return ui;
}
async function screenshots(name, selector) {
  // Windows may retain an occluded compositor frame although DOM observations
  // are current. Bring the QA window forward and wait for actual painted frames.
  await main('globalThis.__openariseQa.window.show(); globalThis.__openariseQa.window.focus(); true');
  for (const [width, height] of [[1320,880],[1050,740],[760,540]]) {
    await main('globalThis.__openariseQa.window.setSize(' + width + ',' + height + ')'); await delay(500);
    await js('document.querySelector(' + JSON.stringify(selector) + ').scrollIntoView({block:"center"})'); await delay(300);
    await js('new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(()=>resolve(true))))');
    assert.equal(await js('(()=>{const h=document.querySelector(' + JSON.stringify(selector + '>strong') + ').getBoundingClientRect(), p=document.querySelector(".ai-conversation").getBoundingClientRect();return h.top>=p.top && h.bottom<=p.bottom && h.right<=innerWidth})()'), true, 'Final state remains visible');
    await main('(async()=>{ const image=await globalThis.__openariseQa.window.webContents.capturePage(); globalThis.__openariseQa.require("node:fs").writeFileSync(' + JSON.stringify(path.join(base, name + '-' + width + 'x' + height + '.png')) + ',image.toPNG());return true;})()');
  }
  await js('document.querySelector(".ai-recovery").scrollIntoView({block:"center"})'); await delay(300);
  await main('(async()=>{ const image=await globalThis.__openariseQa.window.webContents.capturePage(); globalThis.__openariseQa.require("node:fs").writeFileSync(' + JSON.stringify(path.join(base, name + '-recovery.png')) + ',image.toPNG());return true;})()');
}
(async () => {
  try {
    socket = new WebSocket(await endpoint); clearTimeout(endpointTimer);
    await new Promise((resolve, reject) => { socket.addEventListener('open', resolve, {once:true}); socket.addEventListener('error', reject, {once:true}); });
    socket.addEventListener('message', event => { const message = JSON.parse(event.data); const item = pending.get(message.id); if (!item) return; pending.delete(message.id); clearTimeout(item.timer); message.error ? item.reject(new Error(message.error.message)) : item.resolve(message.result); });
    await until(() => main('typeof require === "function" || typeof process.mainModule?.require === "function"'), 'packaged main module loaded');
    await main('(()=>{const req=typeof require==="function"?require:process.mainModule?.require.bind(process.mainModule);if(!req)throw Error("Packaged main require unavailable");globalThis.__openariseQa={electron:req("electron"),require:req,responses:[]};return true;})()');
    await until(() => main('globalThis.__openariseQa.electron.BrowserWindow.getAllWindows().length === 1'), 'one actual packaged window');
    evidence.application = await main('(()=>{const q=globalThis.__openariseQa;q.window=q.electron.BrowserWindow.getAllWindows()[0];return {isPackaged:q.electron.app.isPackaged,appPath:q.electron.app.getAppPath(),resources:process.resourcesPath,windowCount:q.electron.BrowserWindow.getAllWindows().length,preferences:q.window.webContents.getLastWebPreferences()};})()');
    assert.equal(evidence.application.isPackaged, true); assert.equal(evidence.application.appPath, path.join(root, 'resources', 'app.asar'));
    const prefs = evidence.application.preferences;
    assert.equal(prefs.contextIsolation,true);assert.equal(prefs.nodeIntegration,false);assert.equal(prefs.sandbox,true);assert.equal(prefs.webSecurity,true);
    await main('(()=>{ const q=globalThis.__openariseQa;const map=q.electron.ipcMain._invokeHandlers;const original=map.get("openarise:request");if(typeof original!=="function")throw Error("Production handler absent");map.set("openarise:request",async(...args)=>{const response=await original(...args);if(response?.kind==="backend")q.responses.push({method:args[1]?.method,response:response.response,source:response.source});return response;});let pick=0;const projects='+JSON.stringify(projects)+';q.electron.dialog.showOpenDialog=async()=>({canceled:false,filePaths:[projects[Math.min(pick++,1)]]});return true;})()');
    await until(() => js('!!document.querySelector(".open-project") && document.visibilityState === "visible"'), 'visible packaged workspace');
    await js('document.querySelector(".open-project").click()');
    await until(() => js('document.querySelector(".ollama-status")?.textContent.includes("Ollama detected")'), 'real bundled model detection');
    await js('if(!document.querySelector(".ai-workspace").classList.contains("ai-expanded"))document.querySelector(".ai-toggle").click()');
    let r = await ask('Use write_file to overwrite math_ops.py with exactly: def multiply(a, b): return a + b. Set overwrite=true. Do not execute anything. This is a disposable acceptance change.');
    r = await decide(r, projects[0], true); assert.equal(r.status, 'denied'); assert.equal(fs.readFileSync(path.join(projects[0], 'math_ops.py'),'utf8'), GOOD);
    await until(() => js('document.querySelector(".ai-permission")?.dataset.state === "denied" && !document.querySelector(".ai-mode button").disabled'), 'settled denial');
    evidence.results.push({case:'denied',result:r}); save();
    r = await finish(await ask('Restore correct multiplication after controlled recovery, preserving original tests. Produce one tool_call action with all THREE ordered calls: (1) execute_tests for a passing baseline; (2) write_file path math_ops.py, overwrite=true, content "def multiply(a, b):\\n    return a + b\\n" to introduce a fault; (3) execute_tests to detect it. The existing recovery engine must repair math_ops.py to return a * b and retest. Never edit test_math_ops.py. The tests require multiply(3,4)==12 and multiply(-2,5)==-10. Do not claim verification without fresh passing proof.'), projects[0]);
    assert.equal(r.status,'success');assert.equal(r.data.recovery.status,'RECOVERED');assert.equal(r.data.verification.overall_status,'VERIFIED');
    assert.equal(new Set(r.data.evidence.map(e=>e.requirement_id)).size,1);
    assert.ok(r.data.evidence.some(e=>e.evidence_type==='TEST_PASS'&&e.stale&&e.superseded));
    assert.ok(r.data.evidence.some(e=>e.evidence_type==='TEST_FAIL'&&e.resolved_by));
    assert.ok(r.data.evidence.some(e=>e.evidence_type==='TEST_PASS'&&e.success&&e.exit_code===0&&!e.stale&&!e.superseded));
    evidence.results.push({case:'success',result:r,ui:await settled(r,'VERIFIED')});save();await screenshots('success','.ai-completion');
    await main('globalThis.__openariseQa.window.setSize(1320,880)');
    await js('document.querySelector(".open-project").click()');
    await until(() => js('document.querySelector(".ai-context")?.textContent.includes("failure") && !document.querySelector(".ai-mode button").disabled'), 'failure project context');
    r = await finish(await ask('Demonstrate a controlled unsuccessful recovery. Produce one tool_call action containing all TWO ordered tool calls: (1) write_file with path math_ops.py, overwrite=true and content "def multiply(a, b):\\n    return a + b\\n", (2) execute_tests on the whole project. Include both calls in this one action. The recovery engine may try to repair math_ops.py to multiply correctly. Preserve every test unchanged, including test_unrecoverable.py which deliberately always fails for acceptance. Do not change test files or fake success. Return the actual failed or unverified CompletionGate outcome.'), projects[1]);
    assert.equal(r.status,'failure');assert.equal(r.current_state,'FAILED');assert.equal(r.data.recovery.status,'ROLLED_BACK');assert.equal(r.data.verification.overall_status,'NOT_VERIFIED');
    assert.ok(r.data.tool_results.some(t=>t.tool_name==='execute_tests'&&t.executed&&!t.success&&t.exit_code===1));
    assert.ok(r.data.recovery.attempts>=1);
    assert.equal(fs.readFileSync(path.join(projects[1],'test_unrecoverable.py'),'utf8'),IMPOSSIBLE);
    const ui=await settled(r,'FAILED');
    evidence.results.push({case:'failure',result:r,ui});save();await screenshots('failure','.ai-completion');
    // innerText reflects the existing CSS uppercase badge; preserve the exact
    // backend enum checks above while comparing the visible heading by case.
    assert.match(ui.recovery,/Recovery rolled back/i);assert.ok(!ui.result.includes('Verified by CompletionGate'));
    evidence.responses=await responses();assert.ok(evidence.responses.every(x=>x.source==='backend'));
    evidence.status='VERIFIED';save();
    fs.writeFileSync(path.resolve(__dirname,'../.packaging/failure-ui-fix/latest-packaged-ui.json'),JSON.stringify({base,root},null,2));
    console.log('REAL PACKAGED UI SUCCESS + FAILURE VERIFIED',base);
    await main('globalThis.__openariseQa.electron.app.quit(); true');socket.close();
    await until(async()=>exited,'normal packaged shutdown',30000).catch(error=>{if(!exited)throw error;});
  } catch(error) {
    clearTimeout(endpointTimer);evidence.error=String(error);
    if(socket?.readyState===WebSocket.OPEN)evidence.responses=await responses().catch(()=>[]);
    save();console.error(error);process.exitCode=1;
    // Request ordinary guarded shutdown of this owned disposable QA app only.
    if(socket?.readyState===WebSocket.OPEN){await main('globalThis.__openariseQa?.electron.app.quit();true').catch(()=>{});socket.close();}
  }
})().finally(()=>{for(const item of pending.values()){clearTimeout(item.timer);item.reject(new Error('QA session closed'));}pending.clear();});
