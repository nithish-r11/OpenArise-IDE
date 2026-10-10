// Real source Electron acceptance. Disposable projects and native picker choices
// are supplied for unattended QA; all model, tools, evidence and gate results are real.
const { app, BrowserWindow, dialog, ipcMain } = require('electron');
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const base = path.resolve(__dirname, '../.packaging/product-audit/run-' + Date.now());
const GOOD = 'def multiply(a, b):\n    return a * b\n';
const TEST = 'from backend.math_ops import multiply\n\ndef test_multiply():\n    assert multiply(3,4) == 12\n    assert multiply(-2,5) == -10\n';
const projects = ['fullstack', 'failure', 'python-only', 'frontend-only'].map(name => path.join(base, name));
const NODE_GOOD = 'module.exports = (a, b) => a * b;\n';
const NODE_TEST = 'const test=require("node:test"),assert=require("node:assert/strict");const multiply=require("./math.cjs");test("catalog arithmetic",()=>{assert.equal(multiply(3,4),12);assert.equal(multiply(-2,5),-10)});\n';
const INSPECT = 'Inspect this project and tell me:\n1. What is the main entry point?\n2. What does the project do?\n3. What tests are present?\n4. Are there any obvious problems?\nDo not modify any files.';
function file(root, relative, contents) { const target = path.join(root, relative); fs.mkdirSync(path.dirname(target), { recursive: true }); fs.writeFileSync(target, contents); }
for (const root of projects.slice(0, 2)) {
  file(root, 'backend/__init__.py', ''); file(root, 'backend/math_ops.py', GOOD); file(root, 'test_backend.py', TEST);
  file(root, 'backend/main.py', `"""Main API entry point; also serves the actual built React frontend."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json
from math_ops import multiply

class CatalogHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path(__file__).resolve().parents[1] / "frontend" / "dist"), **kwargs)
    def do_GET(self):
        if self.path.split("?")[0] != "/api/catalog":
            return super().do_GET()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps({"total": multiply(3, 4)}).encode())

if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 0), CatalogHandler)
    print("CATALOG_API_PORT=" + str(server.server_port), flush=True)
    server.serve_forever()
`);
  file(root, 'pyproject.toml', '[project]\nname="openarise-catalog-sample"\nversion="0.0.1"\n');
  file(root, 'frontend/package.json', JSON.stringify({ name: 'catalog-frontend', private: true, type: 'module', scripts: { build: 'vite build', test: 'node --test src/math.test.cjs', dev: 'vite' }, dependencies: { react: '19.3.0', 'react-dom': '19.3.0' }, devDependencies: { vite: '8.3.1', typescript: '7.0.2' } }, null, 2));
  file(root, 'frontend/tsconfig.json', '{"compilerOptions":{"jsx":"react-jsx","target":"ES2022","module":"ESNext"}}');
  file(root, 'frontend/index.html', '<!doctype html><html><head><title>Catalog sample</title></head><body><div id="root"></div><script type="module" src="/src/main.tsx"></script></body></html>');
  file(root, 'frontend/src/main.tsx', 'import React, { useState } from "react";\nimport { createRoot } from "react-dom/client";\nimport "./style.css";\nfunction Catalog() { const [total, setTotal] = useState<string>("Not requested"); const port = new URLSearchParams(location.search).get("backendPort"); return <main><h1>Observed Catalog</h1><p>Backend module: backend/math_ops.py</p><button disabled={!port} onClick={async () => { try { const reply = await fetch("http://127.0.0.1:" + port + "/api/catalog"); setTotal(String((await reply.json()).total)); } catch { setTotal("API unavailable"); } }}>Load catalog total</button><p>{total}</p></main>; }\ncreateRoot(document.getElementById("root")!).render(<Catalog />);\n');
  file(root, 'frontend/src/style.css', 'body { background: #091225; color: #eef3ff; font-family: sans-serif; }\n');
  file(root, 'frontend/src/math.cjs', NODE_GOOD);
  file(root, 'frontend/src/math.test.cjs', NODE_TEST);
  // Reuse the already installed, unchanged dependencies. Never install packages.
  fs.symlinkSync(path.resolve(__dirname, '../node_modules'), path.join(root, 'frontend/node_modules'), process.platform === 'win32' ? 'junction' : 'dir');
}
file(projects[1], 'test_unrecoverable.py', 'def test_controlled_failure():\n    assert False, "Acceptance: preserve this always-failing test"\n');
file(projects[2], 'math_ops.py', GOOD); file(projects[2], 'main.py', 'from math_ops import multiply\nprint(multiply(3,4))\n');
file(projects[2], 'test_math_ops.py', 'from math_ops import multiply\ndef test_multiply():\n    assert multiply(3,4) == 12\n');
file(projects[2], 'build.py', 'from pathlib import Path\nimport py_compile\nfor name in ("main.py", "math_ops.py"):\n    py_compile.compile(str(Path(__file__).parent / name), doraise=True)\nprint("PYTHON_COMPILE_BUILD_PASSED")\n');
for (const relative of ['package.json', 'tsconfig.json', 'index.html', 'src/main.tsx', 'src/style.css', 'src/math.cjs', 'src/math.test.cjs'])
  file(projects[3], relative, fs.readFileSync(path.join(projects[0], 'frontend', relative), 'utf8'));
file(projects[3], 'src/main.tsx', 'import React from "react";\nimport {createRoot} from "react-dom/client";\nimport multiply from "./math.cjs";\nimport "./style.css";\ncreateRoot(document.getElementById("root")!).render(<main><h1>Catalog arithmetic</h1><p>{multiply(3,4)}</p></main>);\n');
fs.symlinkSync(path.resolve(__dirname, '../node_modules'), path.join(projects[3], 'node_modules'), process.platform === 'win32' ? 'junction' : 'dir');
const records = [], evidence = { fixtureResponses: false, scope: 'Real source renderer/preload/main/Python/Qwen; disposable sample projects, supplied native picker and bounded script approval decisions', base, results: [], records };
const outcomesOnly = process.argv.includes('--outcomes-only');
const failureOnly = process.argv.includes('--failure-only');
const remainingProjects = process.argv.includes('--remaining-projects');
const frontendPermissionsOnly = process.argv.includes('--frontend-permissions-only');
const frontendOnly = process.argv.includes('--frontend-only') || frontendPermissionsOnly;
evidence.validationScope = failureOnly ? 'Targeted real Qwen failed-recovery refusal and actual rollback outcome' : frontendPermissionsOnly ? 'Targeted default-timeout real frontend write/command denial rerun' : frontendOnly ? 'Targeted real Qwen frontend permission/recovery/build rerun' : remainingProjects ? 'Standalone Python and frontend real workflows after the preserved fullstack run' : outcomesOnly ? 'Additional real recovery/refusal and expanded responsive outcome panels' : 'Full real project workflow';
const persist = () => fs.writeFileSync(path.join(base, 'evidence.json'), JSON.stringify(evidence, null, 2));
const original = ipcMain.handle.bind(ipcMain);
ipcMain.handle = (channel, handler) => original(channel, async (...args) => {
  const result = await handler(...args);
  if (result?.kind === 'backend') { assert.equal(result.source, 'backend'); records.push({ method: args[1]?.method, source: result.source, response: result.response }); persist(); }
  return result;
});
app.setPath('userData', path.join(base, 'profile'));
let pick = 0; dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [projects[Math.min(pick++, 3)]] });
let denyScript = true;
dialog.showMessageBox = async (_window, options) => {
  assert.equal(options.title, 'Run project script?'); assert.match(options.message, /^npm run (build|test) · frontend$/);
  evidence.results.push({ case: 'native-script-review', message: options.message, detail: options.detail, denied: denyScript }); persist();
  return { response: denyScript ? 0 : 1 };
};
const delay = ms => new Promise(r => setTimeout(r, ms));
const timeout = setTimeout(() => { persist(); console.error('Product acceptance deadline:', base); app.exit(1); }, 2700000);
app.once('browser-window-created', (_event, window) => {
  const js = async code => { try { return await window.webContents.executeJavaScript(code); } catch (error) { throw Error('Renderer QA step failed: ' + code.slice(0, 1000) + '\n' + String(error)); } };
  window.webContents.on('console-message', details => { if (details.level === 'error') { (evidence.rendererDiagnostics ||= []).push(String(details.message).slice(0, 1200)); persist(); } });
  function stage(name) { evidence.stage = name; persist(); console.log('Acceptance stage:', name); }
  async function until(check, name, budget = 45000) { const end = Date.now() + budget; while (Date.now() < end) { if (await check()) return; await delay(100); } throw Error('Timed out: ' + name); }
  async function click(text, selector = 'button') {
    const target = '[...document.querySelectorAll(' + JSON.stringify(selector) + ')].find(b=>b.textContent.trim()===' + JSON.stringify(text) + '&&!b.disabled)';
    await until(() => js('!!(' + target + ')'), 'enabled button: ' + text);
    await js(target + '.click()');
  }
  async function input(selector, text) {
    await until(() => js('!!document.querySelector(' + JSON.stringify(selector) + ')'), 'input: ' + selector);
    await js('document.querySelector(' + JSON.stringify(selector) + ').focus()'); await window.webContents.insertText(text);
  }
  async function replaceInput(selector, text) {
    await js('(()=>{const input=document.querySelector(' + JSON.stringify(selector) + ');input.focus();input.select()})()');
    assert.equal(await js('(()=>{const input=document.querySelector(' + JSON.stringify(selector) + ');return document.activeElement===input && input.selectionStart===0 && input.selectionEnd===input.value.length})()'), true, 'QA replacement must select the actual input value');
    await window.webContents.insertText(text);
    await until(() => js('document.querySelector(' + JSON.stringify(selector) + ').value===' + JSON.stringify(text)), 'exact replacement input');
  }
  async function clickSelector(selector) {
    const target = 'document.querySelector(' + JSON.stringify(selector) + ')';
    await until(() => js('!!(' + target + ')&&!(' + target + ').disabled'), 'enabled control: ' + selector);
    await js(target + '.click()');
  }
  async function ask(prompt, actions = false) {
    await until(() => js('!document.querySelector(".ai-mode button").disabled'), 'composer idle');
    await click(actions ? 'Make changes' : 'Answer only', '.ai-mode button');
    await input('#ai-prompt', prompt); const before = records.length; await click('Send ↗');
    await until(() => Promise.resolve(records.slice(before).some(r => r.method === 'request_agent_execution')), 'real model reply', 450000);
    const response = records.slice(before).find(r => r.method === 'request_agent_execution').response;
    assert.equal(response.success, true); return response.data;
  }
  async function decide(result, root, deny = false) {
    const pending = result.pending_action; assert.ok(pending);
    assert.ok(['write_file', 'execute_tests'].includes(pending.tool_name), 'Refuse unrelated execution permissions');
    if (pending.tool_name === 'write_file') assert.equal(pending.resource, 'backend/math_ops.py');
    assert.equal(fs.readFileSync(path.join(root, 'test_backend.py'), 'utf8'), TEST);
    await until(() => js('document.querySelector(".ai-permission[data-state=permission_required]")?.textContent.includes(' + JSON.stringify(pending.tool_call_id) + ') && !![...document.querySelectorAll(".permission-actions button")].find(b=>b.textContent==="Allow"&&!b.disabled)'), 'matching permission card');
    const before = records.length; await click(deny ? 'Deny' : 'Allow', '.permission-actions button');
    const method = deny ? 'deny_agent_action' : 'resume_agent_execution';
    await until(() => Promise.resolve(records.slice(before).some(r => r.method === method)), 'real permission result', 700000);
    const next = records.slice(before).find(r => r.method === method).response.data;
    assert.equal(fs.readFileSync(path.join(root, 'test_backend.py'), 'utf8'), TEST);
    assert.doesNotMatch(fs.readFileSync(path.join(root, 'backend/math_ops.py'), 'utf8'), /\b(?:import|exec|eval|open|subprocess|os\.|sys\.)\b/);
    console.log('Actual backend:', next.status, next.current_state, next.pending_action?.tool_name, next.data.recovery?.status); persist(); return next;
  }
  async function finish(result, root) { let steps = 0; while (result.pending_action) { assert.ok(++steps <= 12); result = await decide(result, root); } return result; }
  async function finishNode(result, root, deny = false) {
    let steps = 0;
    while (result.pending_action) {
      assert.ok(++steps <= 12);
      const pending = result.pending_action;
      assert.ok(['write_file', 'execute_project_tests', 'build_project'].includes(pending.tool_name));
      if (pending.tool_name === 'write_file') assert.equal(pending.resource, 'src/math.cjs');
      else { assert.equal(pending.resource, 'package.json'); assert.ok(pending.command); assert.match(pending.command.script, /^(node --test src\/math.test.cjs|vite build)$/); }
      assert.equal(fs.readFileSync(path.join(root, 'src/math.test.cjs'), 'utf8'), NODE_TEST);
      await until(() => js('document.querySelector(".ai-permission")?.textContent.includes(' + JSON.stringify(pending.tool_call_id) + ') && !![...document.querySelectorAll(".permission-actions button")].find(b=>b.textContent===' + JSON.stringify(deny ? 'Deny' : 'Allow') + '&&!b.disabled)'), 'reviewed Node permission');
      const before = records.length; await click(deny ? 'Deny' : 'Allow', '.permission-actions button');
      const method = deny ? 'deny_agent_action' : 'resume_agent_execution';
      await until(() => Promise.resolve(records.slice(before).some(r => r.method === method)), 'actual Node result', 700000);
      result = records.slice(before).find(r => r.method === method).response.data;
      assert.equal(fs.readFileSync(path.join(root, 'src/math.test.cjs'), 'utf8'), NODE_TEST);
      assert.doesNotMatch(fs.readFileSync(path.join(root, 'src/math.cjs'), 'utf8'), /\b(?:require|import|eval|exec|process|fetch)\b/);
      console.log('Actual Node backend:', result.status, result.current_state, result.pending_action?.tool_name, result.data.recovery?.status);
      persist();
    }
    return result;
  }
  async function capture(name) {
    if (name !== 'welcome') {
      await clickSelector('[aria-label="AI"]');
      await until(() => js('document.querySelector(".ai-workspace").classList.contains("ai-expanded")'), 'expanded outcome workspace');
      if (await js('!!document.querySelector(".ai-technical[open]")')) await click('Details', '.ai-technical>summary');
    }
    for (const [width, height] of [[1320, 880], [1050, 740], [760, 540]]) {
      if (window.isMaximized()) window.unmaximize();
      window.setSize(width, height); window.show(); window.focus(); await delay(400);
      await js('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');
      (evidence.layouts ||= []).push({screen:name, requestedWindow:[width,height], actualWindow:window.getSize(), viewport:await js('({width:innerWidth,height:innerHeight,scale:devicePixelRatio})')}); persist();
      assert.equal(await js('document.documentElement.scrollWidth > innerWidth'), false);
      if (await js('!!document.querySelector(".ai-result")')) {
        await js('(()=>{const panel=document.querySelector(".ai-conversation"),card=document.querySelector(".ai-result"),activity=document.querySelector(".arise-activity");panel.scrollTop+=card.getBoundingClientRect().top-panel.getBoundingClientRect().top-activity.getBoundingClientRect().height-8})()');
        await js('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');
        const geometry = await js('(()=>{const rect=e=>{const r=e.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height}};return {heading:rect(document.querySelector(".ai-result>strong")),panel:rect(document.querySelector(".ai-conversation")),activity:rect(document.querySelector(".arise-activity"))}})()');
        (evidence.geometry ||= []).push({ name, width, height, ...geometry }); persist();
        const {heading, panel, activity} = geometry;
        assert.ok(heading.width>0 && heading.height>0 && heading.left>=panel.left-.5 && heading.right<=panel.right+.5 && heading.top>=activity.bottom-.5 && activity.top>=panel.top-.5 && heading.bottom<=panel.bottom+.5, 'Actual simple final outcome and Activity must both be visible without overlap: ' + JSON.stringify(geometry));
        assert.equal(await js('document.querySelector(".ai-technical").open'), false);
      }
      await js('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');
      fs.writeFileSync(path.join(base, `${name}-${width}x${height}.png`), (await window.webContents.capturePage()).toPNG());
    }
    window.setSize(1320, 880);
  }
  window.webContents.once('did-finish-load', async () => {
    try {
      await until(() => js('!!document.querySelector(".open-project") && document.visibilityState==="visible"'), 'visible OpenArise');
      assert.equal(window.isVisible(), true); assert.equal(BrowserWindow.getAllWindows().length, 1);
      assert.deepEqual(Object.fromEntries(['contextIsolation','nodeIntegration','sandbox','webSecurity'].map(k => [k, window.webContents.getLastWebPreferences()[k]])), {contextIsolation:true,nodeIntegration:false,sandbox:true,webSecurity:true});
      await capture('welcome'); await click('Open Project');
      await until(() => js('document.querySelector(".project-capabilities")?.textContent.includes("React") && document.querySelector(".ollama-status")?.textContent.includes("Ollama detected")'), 'real fullstack context');
      assert.match(await js('document.querySelector(".project-capabilities").textContent'), /Vite/);
      assert.match(await js('document.querySelector(".project-capabilities").textContent'), /Python/);
      await js('document.querySelector(".ai-toggle").click()');
      let result;
      if (!outcomesOnly && !remainingProjects && !frontendOnly && !failureOnly) {
      const readonly = await ask(INSPECT);
      assert.equal(readonly.data.tool_results.length, 0); assert.notEqual(readonly.data.verification.overall_status, 'VERIFIED');
      assert.match(readonly.data.model_response, /frontend|main.tsx|React/i); assert.match(readonly.data.model_response, /backend|math_ops|main.py/i);
      assert.doesNotMatch(readonly.data.model_response, /provided context does not include|no file contents or project details/i);
      assert.ok(readonly.data.model_response.split(/\s+/).length <= 220, 'Normal answer should stay concise');
      evidence.results.push({ case: 'fullstack-readonly-context', result: readonly }); persist();
      // Use the actual editor and creation UI, then safe save and reload guard.
      stage('create-edit-save-conflict-reload');
      window.show(); window.focus(); window.webContents.focus();
      await js('new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))');
      await js('if(document.querySelector(".ai-workspace").classList.contains("ai-expanded"))document.querySelector(".ai-toggle").click()');
      await clickSelector('[aria-label="New file"]'); await input('#new-file-path', 'frontend/src/notes.ts'); await click('Create file');
      await until(() => js('!!document.querySelector(".monaco-editor textarea")'), 'new Monaco buffer');
      await input('.monaco-editor textarea', 'export const acceptanceNote = "REAL_SAVED_SOURCE";\n'); await click('Save Ctrl S');
      await until(() => Promise.resolve(fs.readFileSync(path.join(projects[0], 'frontend/src/notes.ts'), 'utf8').includes('REAL_SAVED_SOURCE')), 'actual frontend save');
      fs.writeFileSync(path.join(projects[0], 'frontend/src/notes.ts'), 'export const acceptanceNote = "EXTERNAL_EDIT";\n');
      await input('.monaco-editor textarea', '// unsaved\n'); await click('Save Ctrl S');
      await until(() => js('[...document.querySelectorAll(".error-banner")].some(e=>e.textContent.includes("File changed on disk"))'), 'actual conflict');
      await click('Reload'); await until(() => js('!!document.querySelector(".discard-banner")'), 'reload discard review'); await click('Discard and reload');
      window.show(); window.focus(); window.webContents.focus();
      await until(() => js('document.querySelector(".view-lines")?.textContent.includes("EXTERNAL_EDIT") && !document.querySelector(".dirty-dot")'), 'Monaco synchronized to disk');
      stage('folder-and-file-rename');
      await clickSelector('[aria-label="New folder"]'); await input('#explorer-path', 'frontend/src/scratch'); await click('Create folder');
      await until(() => Promise.resolve(fs.existsSync(path.join(projects[0], 'frontend/src/scratch'))), 'real created folder');
      await clickSelector('[aria-label="Rename selected path"]');
      await until(() => js('!!document.querySelector("#explorer-path")'), 'reviewed folder rename');
      await replaceInput('#explorer-path', 'frontend/src/notes-directory'); await click('Rename');
      await until(() => Promise.resolve(fs.existsSync(path.join(projects[0], 'frontend/src/notes-directory')) && !fs.existsSync(path.join(projects[0], 'frontend/src/scratch'))), 'actual folder renamed');
      await clickSelector('[aria-label="New file"]'); await input('#new-file-path', 'frontend/src/notes-directory/report.ts'); await click('Create file');
      await until(() => js('document.querySelector("[role=tab][aria-selected=true]")?.textContent.includes("report.ts")'), 'new report tab');
      await input('.monaco-editor textarea', 'export const observed = "saved rename";\n');
      await clickSelector('[aria-label="Rename selected path"]');
      await until(() => js('!!document.querySelector("#explorer-path")'), 'rename reviewed before dirty guard');
      await replaceInput('#explorer-path', 'frontend/src/notes-directory/renamed.ts'); await click('Rename');
      await until(() => js('document.querySelector(".error-banner")?.textContent.includes("Save editor changes")'), 'real unsaved rename guard');
      assert.equal(fs.existsSync(path.join(projects[0], 'frontend/src/notes-directory/renamed.ts')), false);
      await click('Cancel', '.new-file-form button'); await click('Save Ctrl S');
      await until(() => js('!document.querySelector(".dirty-dot")'), 'report saved');
      await clickSelector('[aria-label="Rename selected path"]'); await until(() => js('!!document.querySelector("#explorer-path")'), 'fresh file rename');
      await replaceInput('#explorer-path', 'frontend/src/notes-directory/renamed.ts'); await click('Rename');
      await until(() => Promise.resolve(fs.existsSync(path.join(projects[0], 'frontend/src/notes-directory/renamed.ts'))), 'real file rename');
      assert.match(fs.readFileSync(path.join(projects[0], 'frontend/src/notes-directory/renamed.ts'), 'utf8'), /saved rename/);
      evidence.results.push({ case: 'real-folder-file-rename-and-unsaved-guard', result: 'VERIFIED' }); persist();
      await input('[aria-label="Search project filenames"]', 'backend/main.py');
      stage('python-api-run-stop');
      await until(() => js('!![...document.querySelectorAll(".tree-file")].find(b=>b.textContent.includes("backend/main.py"))'), 'actual backend file search');
      await js('[...document.querySelectorAll(".tree-file")].find(b=>b.textContent.includes("backend/main.py")).click()');
      await until(() => js('document.querySelector(".view-lines")?.textContent.includes("ThreadingHTTPServer") && !document.querySelector(".run-python").disabled'), 'actual reviewed backend file');
      await js('document.querySelector(".run-python").click()');
      await until(() => js('/CATALOG_API_PORT=\\d+/.test(document.querySelector(".terminal-output")?.textContent || "")'), 'actual API process');
      const port = Number((await js('document.querySelector(".terminal-output").textContent')).match(/CATALOG_API_PORT=(\d+)/)[1]);
      const api = await (await fetch('http://127.0.0.1:' + port + '/api/catalog')).json(); assert.equal(api.total, 12);
      await click('Stop', '.terminal-tools button'); await until(() => js('document.querySelector(".terminal-tools")?.textContent.includes("stopped")'), 'controlled API process stop');
      evidence.results.push({ case: 'real-python-api-execution-and-stop', port, response: api }); persist();
      await clickSelector('[aria-label="Refresh Explorer"]');
      await until(() => js('!![...document.querySelectorAll(".project-commands button")].find(b=>b.textContent==="npm run test · frontend ↗" && !b.disabled)'), 'project command ready');
      await click('npm run test · frontend ↗', '.project-commands button');
      await until(() => js('document.querySelector(".terminal-error")?.textContent.includes("denied or cancelled")'), 'native script denial');
      assert.equal(await js('document.querySelector(".terminal-tools")?.textContent.includes("exit ")'), false);
      denyScript = false; await click('npm run test · frontend ↗', '.project-commands button');
      await until(() => js('document.querySelector(".terminal-tools")?.textContent.includes("tests passed")'), 'actual frontend test', 90000);
      await click('npm run build · frontend ↗', '.project-commands button');
      await until(() => js('document.querySelector(".terminal-tools")?.textContent.includes("exited") && document.querySelector(".terminal-output")?.textContent.includes("built in")'), 'actual React/Vite build', 90000);
      assert.ok(fs.existsSync(path.join(projects[0], 'frontend/dist/index.html')));
      evidence.results.push({ case: 'frontend-create-save-conflict-reload-native-deny-test-build', result: 'actual commands exited zero', builtIndex: 'frontend/dist/index.html' }); persist();
      stage('browser-fullstack-api-integration');
      await clickSelector('.run-python');
      await until(() => js('/CATALOG_API_PORT=\\d+/.test(document.querySelector(".terminal-output")?.textContent || "")'), 'built frontend/API server');
      const browserPort = Number((await js('document.querySelector(".terminal-output").textContent')).match(/CATALOG_API_PORT=(\d+)/)[1]);
      evidence.browserIntegration = { url: 'http://127.0.0.1:' + browserPort + '/?backendPort=' + browserPort, acknowledgement: path.join(base, 'browser-api-evidence.json') }; persist();
      console.log('BROWSER API CHECK:', JSON.stringify(evidence.browserIntegration));
      await until(() => Promise.resolve(fs.existsSync(evidence.browserIntegration.acknowledgement)), 'independent actual browser API observation', 240000);
      const browserProof = JSON.parse(fs.readFileSync(evidence.browserIntegration.acknowledgement, 'utf8'));
      assert.equal(browserProof.status, 'VERIFIED'); assert.equal(browserProof.observedTotal, '12'); assert.equal(browserProof.url, evidence.browserIntegration.url);
      evidence.results.push({ case: 'actual-built-react-to-python-api', result: browserProof }); persist();
      await click('Stop', '.terminal-tools button'); await until(() => js('document.querySelector(".terminal-tools")?.textContent.includes("stopped")'), 'API server stopped after browser check');
      await js('if(!document.querySelector(".ai-workspace").classList.contains("ai-expanded"))document.querySelector(".ai-toggle").click()');
      result = await ask('Use write_file to overwrite backend/math_ops.py with exactly def multiply(a, b): return a + b. Set overwrite=true. Do not execute anything.', true);
      result = await decide(result, projects[0], true); assert.equal(result.status, 'denied'); assert.equal(fs.readFileSync(path.join(projects[0], 'backend/math_ops.py'), 'utf8'), GOOD);
      evidence.results.push({ case: 'real-ai-denial', result }); persist();
      }
      if (!remainingProjects && !frontendOnly && !failureOnly) {
      result = await finish(await ask('Perform controlled recovery in this disposable project. Return action_type "tool_call" with exactly these THREE ordered entries in tool_calls, all associated with the supplied requirement ID:\n1. execute_tests with default arguments, to record the passing baseline.\n2. write_file with path "backend/math_ops.py", overwrite true, and content "def multiply(a, b):\\n    return a + b\\n". This deliberate addition fault is required.\n3. execute_tests with default arguments, to expose the fault.\nThen let the existing recovery engine repair multiplication and retest. Preserve test_backend.py and frontend tests. The original tests require multiply(3,4)==12 and multiply(-2,5)==-10. Repeating baseline tests without the middle file change does not satisfy this request.', true), projects[0]);
      assert.equal(result.status, 'success'); assert.equal(result.data.recovery?.status, 'RECOVERED'); assert.equal(result.data.verification.overall_status, 'VERIFIED');
      assert.equal(new Set(result.data.evidence.map(e => e.requirement_id)).size, 1);
      assert.ok(result.data.evidence.some(e => e.evidence_type === 'TEST_PASS' && e.stale && e.superseded));
      assert.ok(result.data.evidence.some(e => e.evidence_type === 'TEST_FAIL' && e.resolved_by));
      assert.ok(result.data.evidence.some(e => e.evidence_type === 'TEST_PASS' && !e.stale && !e.superseded && e.exit_code === 0));
      await until(() => js('document.querySelector(".ai-completion>strong")?.textContent==="VERIFIED"'), 'actual gate UI');
      evidence.results.push({ case: 'fullstack-live-recovery-verified', result }); persist(); await capture('verified');
      fs.appendFileSync(path.join(projects[0], 'frontend/src/main.tsx'), '\n// Controlled frontend change invalidates old project proof\n');
      const before = records.length; await click('Details', '.ai-technical>summary'); await click('Refresh request result');
      await until(() => Promise.resolve(records.slice(before).some(r => r.method === 'get_agent_execution')), 'freshness re-evaluation');
      const stale = records.slice(before).find(r => r.method === 'get_agent_execution').response.data;
      assert.notEqual(stale.data.verification.overall_status, 'VERIFIED'); evidence.results.push({ case: 'frontend-change-stale-proof-refused', result: stale }); persist();
      }
      if (!remainingProjects && !frontendOnly) {
      if (failureOnly) pick = 1;
      await click('Open Project'); await until(() => js('document.querySelector(".ai-context")?.textContent.includes("failure") && !document.querySelector(".ai-mode button").disabled'), 'failure project');
      result = await finish(await ask('Demonstrate unsuccessful recovery. Produce ONE tool_call action with BOTH ordered calls: write_file path backend/math_ops.py overwrite=true content "def multiply(a, b):\\n    return a + b\\n"; execute_tests on the whole project. Recovery may repair only backend/math_ops.py to multiplication. Preserve every test unchanged including the deliberately always-failing test_unrecoverable.py. Return actual failed or unverified CompletionGate outcome.', true), projects[1]);
      assert.equal(result.status, 'failure'); assert.equal(result.data.verification.overall_status, 'NOT_VERIFIED');
      const recoveryWrites = result.data.tool_results.filter(t => t.tool_name === 'write_file' && t.executed && t.tool_call_id?.startsWith('rec_'));
      if (recoveryWrites.length) assert.equal(result.data.recovery?.status, 'ROLLED_BACK');
      else assert.ok(['FAILED', 'BLOCKED'].includes(result.data.recovery?.status), 'A non-mutating failed/invalid plan must refuse recovery success');
      if (result.data.recovery?.status === 'BLOCKED') {
        assert.ok(result.data.recovery.final_result, 'Blocked recovery must explain its actual reason');
        assert.ok(result.data.tool_results.every(t => !t.tool_call_id?.startsWith('rec_')), 'Invalid recovery plans must not execute');
      }
      assert.equal(fs.readFileSync(path.join(projects[1], 'backend/math_ops.py'), 'utf8'), 'def multiply(a, b):\n    return a + b\n', 'Failed recovery must preserve or restore its actual pre-recovery checkpoint');
      assert.equal(fs.readFileSync(path.join(projects[1], 'test_unrecoverable.py'), 'utf8'), 'def test_controlled_failure():\n    assert False, "Acceptance: preserve this always-failing test"\n');
      assert.ok(result.data.tool_results.some(t => t.tool_name === 'execute_tests' && t.executed && !t.success && t.exit_code !== 0));
      const recoveryLabel = recoveryWrites.length ? 'Recovery rolled back' : result.data.recovery?.status === 'BLOCKED' ? 'Recovery blocked' : 'Recovery failed';
      await until(() => js('document.querySelector(".ai-completion>strong")?.textContent==="FAILED" && document.querySelector(".ai-recovery")?.textContent.includes(' + JSON.stringify(recoveryLabel) + ')'), 'actual failed recovery UI');
      evidence.results.push({ case: 'fullstack-live-failed-recovery-refusal', recoveryWrites: recoveryWrites.length, result }); persist(); await capture('failure');
      }
      if (!outcomesOnly && !failureOnly) {
      if (remainingProjects) pick = 2;
      if (!frontendOnly) {
      await click('Open Project'); await until(() => js('document.querySelector(".ai-context")?.textContent.includes("python-only") && !document.querySelector(".ai-mode button").disabled'), 'Python-only project');
      const python = await ask(INSPECT);
      assert.equal(python.data.tool_results.length, 0); assert.match(python.data.model_response, /main.py/); assert.match(python.data.model_response, /math_ops/);
      assert.doesNotMatch(python.data.model_response, /provided context does not include|no file contents or project details/i);
      evidence.results.push({ case: 'exact-python-readonly-request', result: python }); persist();
      stage('python-only-edit-run-test-build');
      await js('if(document.querySelector(".ai-workspace").classList.contains("ai-expanded"))document.querySelector(".ai-toggle").click()');
      await input('[aria-label="Search project filenames"]', 'main.py');
      await until(() => js('!![...document.querySelectorAll(".tree-file")].find(b=>b.textContent.includes("main.py"))'), 'standalone Python main file');
      await js('[...document.querySelectorAll(".tree-file")].find(b=>b.textContent.includes("main.py")).click()');
      await until(() => js('document.querySelector(".view-lines")?.textContent.includes("multiply")'), 'standalone Python source');
      await input('.monaco-editor textarea', '# REAL_PYTHON_EDITOR_SAVE\n'); await click('Save Ctrl S');
      await until(() => Promise.resolve(fs.readFileSync(path.join(projects[2], 'main.py'), 'utf8').includes('REAL_PYTHON_EDITOR_SAVE')), 'standalone Python safe save');
      await clickSelector('.run-python'); await until(() => js('document.querySelector(".terminal-tools")?.textContent.includes("exited")'), 'standalone Python run');
      assert.match(await js('document.querySelector(".terminal-output").textContent'), /12/);
      await clickSelector('.run-tests'); await until(() => js('document.querySelector(".terminal-tools")?.textContent.includes("pytest passed")'), 'standalone real pytest', 90000);
      assert.match(await js('document.querySelector(".terminal-output").textContent'), /1 passed/);
      await replaceInput('[aria-label="Search project filenames"]', 'build.py');
      await until(() => js('!![...document.querySelectorAll(".tree-file")].find(b=>b.textContent.includes("build.py"))'), 'standalone Python build file');
      await js('[...document.querySelectorAll(".tree-file")].find(b=>b.textContent.includes("build.py")).click()');
      await until(() => js('document.querySelector(".view-lines")?.textContent.includes("py_compile")'), 'actual Python build source');
      await clickSelector('.run-python'); await until(() => js('document.querySelector(".terminal-tools")?.textContent.includes("exited") && document.querySelector(".terminal-output")?.textContent.includes("PYTHON_COMPILE_BUILD_PASSED")'), 'actual Python compilation build');
      evidence.results.push({ case: 'standalone-python-edit-safe-save-run-pytest-compile', result: 'VERIFIED', tests: '1 passed', build: 'py_compile of main.py and math_ops.py' }); persist();
      await js('if(!document.querySelector(".ai-workspace").classList.contains("ai-expanded"))document.querySelector(".ai-toggle").click()');
      } else pick = 3;
      stage('frontend-only-real-ai');
      await click('Open Project'); await until(() => js('document.querySelector(".ai-context")?.textContent.includes("frontend-only") && !document.querySelector(".ai-mode button").disabled'), 'frontend-only project');
      if (!frontendPermissionsOnly) {
      const front = await ask(INSPECT);
      assert.equal(front.data.tool_results.length, 0); assert.notEqual(front.data.verification.overall_status, 'VERIFIED');
      assert.match(front.data.model_response, /src\/main.tsx/); assert.match(front.data.model_response, /math.test.cjs/);
      assert.ok(front.data.model_response.split(/\s+/).length <= 220);
      evidence.results.push({ case: 'frontend-only-real-readonly', result: front }); persist();
      }
      result = await finishNode(await ask('Use write_file to overwrite src/math.cjs with "module.exports = (a, b) => a + b;\\n", overwrite=true. Do not run any commands.', true), projects[3], true);
      assert.equal(result.status, 'denied'); assert.equal(fs.readFileSync(path.join(projects[3], 'src/math.cjs'), 'utf8'), NODE_GOOD);
      evidence.results.push({ case: 'frontend-real-ai-deny', result }); persist();
      result = await finishNode(await ask('Run the detected npm tests. Use execute_project_tests and copy command_id and revision exactly from its observed_commands schema. No file edits, pytest or Python execution.', true), projects[3], true);
      assert.equal(result.status, 'denied'); assert.ok(result.data.tool_results.every(t => !t.executed));
      evidence.results.push({ case: 'frontend-real-execute-deny', result }); persist();
      if (!frontendPermissionsOnly) {
      result = await finishNode(await ask('Demonstrate controlled frontend recovery and restore multiplication with original Node tests passing. Return ONE tool_call action with THREE ordered calls: execute_project_tests for baseline; write_file src/math.cjs overwrite=true content "module.exports = (a, b) => a + b;\\n"; execute_project_tests to detect the fault. Copy command_id and revision exactly from the observed_commands schema. Recovery may only repair src/math.cjs to multiply. Preserve src/math.test.cjs and package.json. Never call execute_tests or execute_python for this frontend. Let the real recovery engine plan a repair and rerun the original npm test command.', true), projects[3]);
      assert.equal(result.status, 'success'); assert.equal(result.data.recovery?.status, 'RECOVERED'); assert.equal(result.data.verification.overall_status, 'VERIFIED');
      assert.ok(result.data.evidence.some(e => e.evidence_type === 'TEST_FAIL' && e.resolved_by));
      assert.ok(result.data.evidence.some(e => e.evidence_type === 'TEST_PASS' && !e.stale && !e.superseded));
      evidence.results.push({ case: 'frontend-real-node-recovery-and-fresh-gate', result }); persist(); await capture('frontend-verified');
      result = await finishNode(await ask('Build this React/Vite frontend using build_project only. Copy command_id and revision exactly from its observed_commands schema. No file edits and no tests; report the actual build result.', true), projects[3]);
      assert.equal(result.status, 'success'); assert.equal(result.data.verification.overall_status, 'VERIFIED');
      assert.equal(result.data.verification.report.tests_executed, 0);
      assert.ok(result.data.evidence.some(e => e.evidence_type === 'BUILD_PASS'));
      assert.ok(fs.existsSync(path.join(projects[3], 'dist/index.html')));
      evidence.results.push({ case: 'frontend-real-ai-vite-build-distinct-from-tests', result }); persist();
      }
      }
      assert.ok(records.every(r => r.source === 'backend'));
      console.log('REAL PRODUCT FLOW VERIFIED:', base); evidence.status = 'VERIFIED'; persist(); clearTimeout(timeout); app.quit();
    } catch (error) {
      evidence.status = 'NOT VERIFIED'; evidence.error = String(error);
      try { evidence.visibleErrorState = await js('document.body.innerText'); fs.writeFileSync(path.join(base, 'failure-at-stop.png'), (await window.webContents.capturePage()).toPNG()); } catch { /* Preserve the original failure if renderer capture is unavailable. */ }
      persist(); console.error(error, base); clearTimeout(timeout); app.exit(1);
    }
  });
});
require('../dist-electron/main.cjs').startDesktop();
