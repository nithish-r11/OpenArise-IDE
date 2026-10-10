// Real main + preload + Monaco + Python file host. Only the native picker is replaced.
const { app, dialog, BrowserWindow } = require('electron');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'openarise-phase7-'));
const project = path.join(profile, 'orbit-workspace');
fs.mkdirSync(path.join(project, 'app'), { recursive: true });
const source = [
  '"""A small project used only by the desktop smoke test."""',
  '', 'import sys', 'from dataclasses import dataclass', 'from datetime import datetime', '',
  '@dataclass', 'class Workspace:', '    name: str', '    language: str = "python"', '',
  '    def describe(self) -> str:', '        return f"{self.name} · {self.language}"', '',
  'def welcome(workspace: Workspace) -> dict:', '    """Build a local workspace greeting."""',
  '    return {', '        "project": workspace.name,', '        "message": "Welcome to OpenArise",',
  '        "created_at": datetime.now().isoformat(),', '    }', '',
  'def main() -> None:', '    workspace = Workspace(name="orbit-workspace")',
  '    greeting = welcome(workspace)', '    print(greeting["message"])', '    print("stderr captured", file=sys.stderr)', '',
  'if __name__ == "__main__":', '    main()', '',
].join('\n');
fs.writeFileSync(path.join(project, 'app/main.py'), source);
fs.writeFileSync(path.join(project, 'README.md'), '# Smoke project\nRead-only text preview.');
fs.writeFileSync(path.join(project, 'config.json'), '{"label":"ACTUAL_JSON_SOURCE"}');
fs.writeFileSync(path.join(project, '.env'), 'PRIVATE_TEST_VALUE=hidden');
fs.writeFileSync(path.join(project, 'test_sample.py'), 'def test_ready():\n    assert True\n');
fs.writeFileSync(path.join(project, 'long.py'), 'import os,time\nprint("PID="+str(os.getpid()), flush=True)\ntime.sleep(60)\n');
let shutdownPid = null;
app.on('will-quit', () => {
  if (shutdownPid) {
    try { process.kill(shutdownPid, 0); console.error('Shutdown left a process alive'); process.exitCode = 1; }
    catch { console.log('Shutdown process cleanup verified.'); }
  }
});
app.setPath('userData', path.join(profile, 'profile'));
let picks = 0;
dialog.showOpenDialog = async () => (++picks === 1 ? { canceled: true, filePaths: [] } : { canceled: false, filePaths: [project] });
const timeout = setTimeout(() => { console.error('Electron smoke timed out'); app.exit(1); }, 180000);
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
app.once('browser-window-created', (_event, window) => {
  const js = code => window.webContents.executeJavaScript(code);
  async function until(code, label) {
    for (let i = 0; i < 150; i++) { if (await js(code)) return; await delay(100); }
    const snapshot = await js('JSON.stringify({activity:document.querySelector(".arise-activity")?.dataset,final:document.querySelector(".ai-completion>strong")?.textContent,error:document.querySelector(".ai-error")?.textContent,prompt:document.querySelector("#ai-prompt")?.value,result:document.querySelector(".ai-result")?.textContent})');
    fs.writeFileSync(path.join(profile, 'timeout.png'), (await window.webContents.capturePage()).toPNG());
    throw new Error('Timed out: ' + label + '\nRenderer snapshot: ' + snapshot);
  }
  window.webContents.on('preload-error', (_event, _path, error) => console.error('Preload:', error.message));
  window.webContents.on('console-message', (details) => {
    if (details.level === 'error') console.error('Renderer:', details.message);
  });
  window.webContents.once('did-finish-load', async () => {
    try {
      await until('!!document.querySelector("h1")', 'React welcome');
      assert.deepEqual(await js('[typeof require, typeof process]'), ['undefined', 'undefined']);
      const preferences = window.webContents.getLastWebPreferences();
      assert.equal(preferences.sandbox, true);
      assert.equal(preferences.contextIsolation, true);
      assert.equal(preferences.nodeIntegration, false);
      assert.deepEqual(await js('Object.keys(window.openarise.terminal)'), ['request']);
      assert.deepEqual(await js('Object.keys(window.openarise.project).sort()'),
        ['createFile', 'createFolder', 'inspectRename', 'listDirectory', 'observeProject', 'openProject', 'openRecent', 'readFile', 'recentProjects', 'renamePath', 'saveFile', 'searchFiles', 'setDirty']);
      await js('document.querySelector(".open-project").click()');
      await until('!document.querySelector(".open-project").disabled', 'cancel picker');
      assert.equal(await js('document.querySelectorAll("[role=tab]").length'), 0);
      await js('document.querySelector(".open-project").click()');
      await until('!![...document.querySelectorAll(".tree-folder")].find(b=>b.textContent.trim().endsWith("app"))', 'project tree');
      assert.equal(await js('document.querySelector(".explorer-tree").textContent.includes(".env")'), false);
      await js('[...document.querySelectorAll(".tree-folder")].find(b=>b.textContent.trim().endsWith("app")).click()');
      await until('!![...document.querySelectorAll(".tree-file")].find(b=>b.textContent.includes("main.py"))', 'folder expansion');
      await js('[...document.querySelectorAll(".tree-file")].find(b=>b.textContent.includes("main.py")).click()');
      await until('!!document.querySelector(".monaco-editor textarea")', 'Monaco');
      await until('document.querySelector(".view-lines")?.textContent.includes("Workspace")', 'file text');
      assert.equal(await js('!!document.querySelector(".minimap")'), true);
      // Native input goes through Monaco, React state, secure IPC and the existing writer.
      await js('document.querySelector(".monaco-editor textarea").focus()');
      window.webContents.sendInputEvent({ type: 'keyDown', keyCode: 'Home', modifiers: ['control'] });
      window.webContents.sendInputEvent({ type: 'keyUp', keyCode: 'Home', modifiers: ['control'] });
      await window.webContents.insertText('# Saved through the existing backend file tool\n');
      await until('!!document.querySelector(".dirty-dot")', 'dirty state');
      assert.equal(await js('document.querySelector(".run-python").disabled'), true);
      await js('document.querySelector(".save-button").click()');
      await until('document.querySelector(".save-label")?.textContent === "Saved"', 'save confirmation');
      assert.match(fs.readFileSync(path.join(project, 'app/main.py'), 'utf8'), /Saved through the existing backend file tool/);
      await js('[...document.querySelectorAll(".tree-file")].find(b=>b.textContent.includes("README.md")).click()');
      await until('document.querySelectorAll("[role=tab]").length === 2', 'multiple tabs');
      assert.equal(await js('document.querySelector(".save-button").disabled'), true);
      await js('[...document.querySelectorAll(".tree-file")].find(b=>b.textContent.includes("config.json")).click()');
      await until('document.querySelector(".breadcrumb")?.textContent.includes("config.json") && document.querySelector(".view-lines")?.textContent.includes("ACTUAL_JSON_SOURCE")', 'real JSON model and local language feature');
      assert.equal(await js('document.querySelectorAll("[role=tab]").length'), 3);
      await js('document.querySelector(".monaco-editor textarea").focus()');
      window.webContents.sendInputEvent({ type: 'keyDown', keyCode: 'End', modifiers: ['control'] });
      window.webContents.sendInputEvent({ type: 'keyUp', keyCode: 'End', modifiers: ['control'] });
      await window.webContents.insertText('\n');
      await until('document.querySelector(".save-label")?.textContent === "Unsaved changes" && !!document.querySelector(".tab-active .dirty-dot") && !document.querySelector(".save-button").disabled', 'JSON edit reached workspace state and can save');
      await js('document.querySelector(".save-button").click()');
      await until('document.querySelector(".save-label")?.textContent === "Saved"', 'actual JSON safe save');
      assert.equal(JSON.parse(fs.readFileSync(path.join(project, 'config.json'), 'utf8')).label, 'ACTUAL_JSON_SOURCE');
      assert.ok(fs.readFileSync(path.join(project, 'config.json'), 'utf8').endsWith('\n'), 'Native JSON edit was persisted');
      // A first save of a single-line Windows model must preserve editor undo.
      await js('document.querySelector(".monaco-editor textarea").focus()');
      window.webContents.sendInputEvent({ type: 'keyDown', keyCode: 'Z', modifiers: ['control'] });
      window.webContents.sendInputEvent({ type: 'keyUp', keyCode: 'Z', modifiers: ['control'] });
      await until('document.querySelector(".save-label")?.textContent === "Unsaved changes"', 'JSON undo remains available after save');
      window.webContents.sendInputEvent({ type: 'keyDown', keyCode: 'Y', modifiers: ['control'] });
      window.webContents.sendInputEvent({ type: 'keyUp', keyCode: 'Y', modifiers: ['control'] });
      await until('document.querySelector(".save-label")?.textContent === "Saved"', 'JSON redo restores the confirmed buffer');
      await js('[...document.querySelectorAll("[role=tab]")].find(b=>b.textContent.includes("main.py")).click()');
      await until('document.querySelector(".breadcrumb")?.textContent.includes("main.py")', 'active tab');
      await until('!document.querySelector(".run-python").disabled', 'Python environment ready');
      await js('document.querySelector(".run-python").click()');
      await until('document.querySelector(".terminal-tools")?.textContent.includes("exited")', 'Python exited');
      assert.match(await js('document.querySelector(".terminal-output").textContent'), /Welcome to OpenArise/);
      assert.match(await js('document.querySelector(".terminal-output .stderr").textContent'), /stderr captured/);
      await js('document.querySelector(".run-tests").click()');
      await until('document.querySelector(".terminal-tools")?.textContent.includes("pytest passed")', 'pytest passed');
      assert.match(await js('document.querySelector(".terminal-output").textContent'), /1 passed/);
      await js('document.querySelector(".new-terminal").click()');
      await until('document.querySelectorAll(".terminal-sessions [role=tab]").length === 2', 'multiple terminal sessions');
      await js('[...document.querySelectorAll(".terminal-tools button")].find(b=>b.textContent==="Close").click()');
      await until('document.querySelectorAll(".terminal-sessions [role=tab]").length === 1', 'close terminal session');
      await js('document.querySelector("[aria-label=AI]").click()');
      await js('document.querySelector("#ai-prompt").focus()');
      await window.webContents.insertText('Create a small Python helper');
      await until('!document.querySelector(".ai-submit").disabled', 'AI draft');
      await js('document.querySelector(".ai-submit").click()');
      await until('document.querySelector(".arise-activity")?.dataset.state==="submitting"', 'local submission');
      assert.equal(await js('document.querySelector(".arise-activity").dataset.provenance'), 'UNAVAILABLE_ACTIVITY');
      await until('!!document.querySelector(".ai-permission")', 'AI permission card');
      assert.equal(await js('document.querySelector(".arise-activity").dataset.state'), 'waiting_for_permission');
      assert.match(await js('document.querySelector(".ai-permission").textContent'), /OpenArise needs permission/);
      assert.equal(await js('document.querySelector(".ai-submit").disabled'), true);
      fs.writeFileSync(path.join(profile, 'ai-permission.png'), (await window.webContents.capturePage()).toPNG());
      await js('[...document.querySelectorAll(".ai-permission button")].find(b=>b.textContent==="Allow").click()');
      await until('document.querySelector(".ai-result>strong")?.textContent==="Not verified"', 'AI inconclusive outcome remains not verified');
      assert.equal(await js('document.querySelector(".ai-result").textContent.includes("Verified by CompletionGate")'), false);
      assert.equal(await js('document.querySelector(".arise-activity").dataset.state'), 'unverified');
      const activitySubmit = async (prompt, state) => {
        await js('document.querySelector("#ai-prompt").focus(); document.querySelector("#ai-prompt").select()');
        await window.webContents.insertText(prompt);
        await until('document.querySelector("#ai-prompt").value===' + JSON.stringify(prompt), 'exact fixture prompt');
        await until('!document.querySelector(".ai-submit").disabled', 'activity submit ready');
        await js('document.querySelector(".ai-submit").click()');
        await until('document.querySelector(".arise-activity")?.dataset.state==="submitting"', 'activity submission visible');
        await until('document.querySelector(".arise-activity")?.dataset.state===' + JSON.stringify(state), 'activity '+state);
      };
      await activitySubmit('Offline failure fixture', 'failure');
      assert.equal(await js('document.querySelector(".ai-result>strong").textContent'), 'Failed');
      await activitySubmit('Offline verified fixture', 'completed');
      assert.ok(await js('document.querySelector(".ai-result").textContent.includes("Verified by CompletionGate")'));
      await js('document.querySelector(".activity-history li button").click()');
      assert.equal(await js('document.querySelector(".arise-activity").dataset.state'), 'running');
      assert.equal(await js('document.querySelector(".arise-activity").dataset.provenance'), 'RECORDED_ACTIVITY');
      assert.equal(await js('getComputedStyle(document.querySelector(".activity-particle-track")).animationName'), 'arise-orbit');
      window.webContents.debugger.attach('1.3');
      await window.webContents.debugger.sendCommand('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
      await delay(100);
      assert.equal(await js('getComputedStyle(document.querySelector(".activity-particle-track")).animationName'), 'none');
      assert.equal(await js('getComputedStyle(document.querySelector(".orbit-mark")).animationName'), 'none');
      await window.webContents.debugger.sendCommand('Emulation.setEmulatedMedia', { features: [] });
      window.webContents.debugger.detach();
      await js('document.querySelector(".activity-current").click()');
      assert.equal(require('node:crypto').createHash('sha256').update(fs.readFileSync(path.join(__dirname, '../src/assets/openarise-logo.jpeg'))).digest('hex'), '7170a7b5a083b27fa852082e8ae42db47419f52376aefc1a281748eb2b6486e3');
      assert.match(await js('document.querySelector(".ai-activity").textContent'), /Returned observations, not live progress/);
      await js('[...document.querySelectorAll(".ai-context button")].find(b=>b.textContent==="Refresh context").click()');
      // The AI summary below is the explicitly labelled intelligence fixture,
      // independent of the real file-host project edited above.
      await until('document.querySelector(".ai-context").textContent.includes("4 files")', 'fixture AI context summary');
      for (const [width, height] of [[1440, 900], [1050, 740], [760, 540]]) {
        window.setSize(width, height); await delay(500);
        const layout = await js('({overflow:document.documentElement.scrollWidth>innerWidth,editor:document.querySelector(".editor-container").getBoundingClientRect().width})');
        assert.equal(layout.overflow, false); assert.ok(layout.editor >= 280, 'Editor stays usable');
        assert.ok(await js('document.querySelector(".arise-activity").scrollWidth<=document.querySelector(".arise-activity").clientWidth+1'), 'Activity has no horizontal overflow');
        const conversationHeight = await js('document.querySelector(".ai-conversation").clientHeight');
        assert.ok(conversationHeight >= 120, `Current activity stays readable (${conversationHeight}px at ${width}x${height})`);
        const screenshot = path.join(profile, 'editor-' + width + '.png');
        fs.writeFileSync(screenshot, (await window.webContents.capturePage()).toPNG());
        console.log('Screenshot: ' + screenshot);
      }

      // Phase 7: deterministic UI fixtures through the actual main/preload/IPC boundary.
      assert.equal(window.isVisible(), true);
      assert.equal(BrowserWindow.getAllWindows().length, 1);
      assert.equal(preferences.webSecurity, true);
      await activitySubmit('Phase7 permission execution fixture', 'waiting_for_permission');
      assert.match(await js('document.querySelector(".ai-data-source").textContent'), /TEST FIXTURE.*no live AI validation/);
      assert.equal(await js('document.querySelector(".arise-activity").dataset.source'), 'test_fixture');
      assert.match(await js('document.querySelector(".ai-permission").textContent'), /EXECUTE.*execute_tests/s);
      assert.equal(await js('document.querySelector(".ai-completion>strong").textContent'), 'BLOCKED');
      for (const [width,height] of [[1320,880],[1050,740],[760,540]]) {
        window.setSize(width,height); await delay(350);
        await js('document.querySelector(".permission-actions").scrollIntoView({block:"nearest"})'); await delay(180);
        const layout = await js('(()=>{const c=document.querySelector(".ai-conversation"),p=document.querySelector(".ai-permission"),a=document.querySelector(".permission-actions");return {overflow:document.documentElement.scrollWidth>innerWidth,cardOverflow:p.scrollWidth>p.clientWidth+1,height:c.clientHeight,buttons:[...a.children].every(b=>{const r=b.getBoundingClientRect(),v=c.getBoundingClientRect();return r.left>=v.left&&r.right<=v.right+1&&r.top>=v.top-1&&r.bottom<=v.bottom+1})}})()');
        assert.equal(layout.overflow,false); assert.equal(layout.cardOverflow,false); assert.ok(layout.height>=100); assert.equal(layout.buttons,true);
        const file=path.join(profile,'phase7-permission-'+width+'x'+height+'.png');
        fs.writeFileSync(file,(await window.webContents.capturePage()).toPNG()); console.log('Screenshot: '+file);
      }
      const beforeAllow=fixtureBackend.getStats().length;
      await js('(()=>{const b=[...document.querySelectorAll(".ai-permission button")].find(b=>b.textContent==="Allow");b.click();b.click()})()');
      await until('document.querySelector(".ai-permission")?.dataset.state==="pending"','Phase7 approval pending');
      assert.equal(await js('[...document.querySelectorAll(".ai-permission button")].every(b=>b.disabled)'),true);
      await until('document.querySelector(".ai-permission")?.dataset.state==="completed"','Phase7 permission completed');
      assert.deepEqual(fixtureBackend.getStats().slice(beforeAllow),['approve_agent_action','resume_agent_execution']);
      for (const [decision,state] of [['Deny','denied'],['Cancel','cancelled']]) {
        await activitySubmit('Phase7 '+decision.toLowerCase()+' execution fixture','waiting_for_permission');
        const before=fixtureBackend.getStats().length;
        await js('(()=>{const b=[...document.querySelectorAll(".ai-permission button")].find(b=>b.textContent==='+JSON.stringify(decision)+');b.click();b.click()})()');
        await until('document.querySelector(".ai-permission")?.dataset.state==='+JSON.stringify(state),'Phase7 '+state);
        assert.deepEqual(fixtureBackend.getStats().slice(before),[decision==='Deny'?'deny_agent_action':'cancel_agent_execution']);
        assert.equal(await js('document.querySelector(".ai-completion>strong").textContent'),state.toUpperCase());
      }
      for (const [prompt,activity,recovery] of [
        ['Phase7 failure fixture','failure','unavailable'],
        ['Phase7 recovery attempted fixture','failure','attempted'],
        ['Phase7 recovery completed fixture','unverified','completed'],
        ['Phase7 recovery blocked fixture','failure','blocked'],
      ]) {
        await activitySubmit(prompt,activity);
        assert.equal(await js('document.querySelector(".ai-recovery").dataset.state'),recovery);
        assert.notEqual(await js('document.querySelector(".ai-completion>strong").textContent'),'VERIFIED');
      }
      await activitySubmit('Phase7 false done fixture','unverified');
      assert.equal(await js('document.querySelector("#ai-history").selectedOptions[0].textContent.startsWith("Not verified ·")'),true);
      assert.equal(await js('document.querySelector(".ai-completion>strong").textContent'),'INCONCLUSIVE');
      assert.equal(await js('document.querySelector(".activity-symbol").textContent'),' ? '.trim());
      assert.equal(await js('document.querySelector(".ai-result").textContent.includes("Verified by CompletionGate")'),false);
      await activitySubmit('Phase7 stale evidence fixture','unverified');
      assert.match(await js('document.querySelector(".ai-verification").textContent'), /Stale evidence: ev-smoke/);
      assert.match(await js('document.querySelector(".ai-verification").textContent'), /Invalid evidence reference/);
      for (const [width,height] of [[1320,880],[1050,740],[760,540]]) {
        window.setSize(width,height); await delay(350);
        await js('document.querySelector(".ai-verification").scrollIntoView({block:"start"})'); await delay(180);
        assert.equal(await js('document.documentElement.scrollWidth>innerWidth'),false);
        assert.equal(await js('document.querySelector(".ai-verification").scrollWidth>document.querySelector(".ai-verification").clientWidth+1'),false);
        assert.ok(await js('document.querySelector(".ai-conversation").clientHeight>=100'));
        assert.match(await js('document.querySelector(".ai-data-source").textContent'), /TEST FIXTURE/);
        const file=path.join(profile,'phase7-verification-'+width+'x'+height+'.png');
        fs.writeFileSync(file,(await window.webContents.capturePage()).toPNG()); console.log('Screenshot: '+file);
      }
      console.log('Phase 7 fixture-only UI flow passed: permission required/allow/deny/cancel/pending/completed, duplicate prevention, failure/recovery unavailable/attempted/completed/blocked, stale/invalid evidence, CompletionGate false-DONE guard, fixture provenance, all three sizes. Live Ollama is unverified.');
      await js('document.querySelector(".ai-toggle").click()');

      // Phase 5 fixture stays in main; requests cross the real guarded IPC boundary.
      await js('document.querySelector(".terminal-heading button").click()');
      await js('document.querySelector(".intelligence-shortcut").click()');
      await until('document.querySelector(".intelligence-content")?.textContent.includes("C:/orbit-workspace")', 'intelligence overview');
      await until('document.querySelector(".intelligence-header button")?.textContent==="Refresh intelligence"', 'intelligence bundle');
      const openView = async name => {
        await js('[...document.querySelectorAll(".intelligence-nav button")].find(b=>b.textContent===' + JSON.stringify(name) + ').click()');
        await until('document.querySelector(".intelligence-header h1")?.textContent===' + JSON.stringify(name), name);
      };
      for (const [name, expected] of [['Requirements','NOT_VERIFIED'],['Blueprint','Implement greeting'],['Traceability','Evidence-backed'],['Environment','Pytest availability'],['Health','WARNING'],['Snapshot','requirements summary'],['Timeline','Workspace scanned'],['Drift','Capture baseline']]) {
        await openView(name);
        assert.ok((await js('document.querySelector(".intelligence-content").textContent')).toLowerCase().includes(expected.toLowerCase()), name + ' fixture data');
      }
      await js('[...document.querySelectorAll(".intelligence-actions button")].find(b=>b.textContent==="Capture baseline").click()');
      await until('!![...document.querySelectorAll(".intelligence-actions button")].find(b=>b.textContent==="Compare drift"&&!b.disabled)', 'baseline captured');
      await js('[...document.querySelectorAll(".intelligence-actions button")].find(b=>b.textContent==="Compare drift").click()');
      await until('document.querySelector(".intelligence-content").textContent.includes("POTENTIAL_DRIFT")', 'drift comparison');
      for (const [width,height] of [[1440,900],[1050,740],[760,540]]) {
        window.setSize(width,height); await delay(300);
        for (const view of ['Overview','Requirements','Blueprint','Traceability','Environment','Health','Snapshot','Timeline','Drift']) {
          await openView(view);
          const layout = await js('({overflow:document.documentElement.scrollWidth>innerWidth,content:document.querySelector(".intelligence-content").scrollWidth>document.querySelector(".intelligence-content").clientWidth+1,height:document.querySelector(".intelligence-content").clientHeight})');
          assert.equal(layout.overflow,false,view+' page overflow'); assert.equal(layout.content,false,view+' content overflow'); assert.ok(layout.height>100,view+' scrollable area');
          if (view === 'Overview' || view === 'Traceability') {
            await delay(180);
            const screenshot = path.join(profile,'intelligence-'+view+'-'+width+'.png');
            fs.writeFileSync(screenshot,(await window.webContents.capturePage()).toPNG()); console.log('Screenshot: '+screenshot);
          }
        }
      }
      await js('document.querySelector(".terminal-heading button").click()');
      await delay(100);
      assert.ok(await js('document.querySelector(".intelligence-content").clientHeight>100'), 'Intelligence remains readable above expanded terminal');
      await js('document.querySelector(".terminal-heading button").click()');
      for (const section of ['Blueprint','Traceability','Health','Timeline']) {
        await js('document.querySelector(".activity-rail [aria-label='+section+']").click()');
        await until('document.querySelector(".intelligence-header h1")?.textContent===' + JSON.stringify(section), 'rail '+section);
      }
      await js('document.querySelector(".activity-rail [aria-label=Explorer]").click()');
      await until('!document.querySelector(".editor-surface").hidden', 'editor preserved');
      await js('document.querySelector(".terminal-heading button").click()');
      // Conflicting external writes must leave the buffer dirty and disk untouched.
      fs.writeFileSync(path.join(project, 'app/main.py'), 'external_change = True\n');
      await js('document.querySelector(".monaco-editor textarea").focus()');
      await window.webContents.insertText('# unsaved conflict\n');
      await until('!!document.querySelector(".dirty-dot")', 'second edit');
      await js('document.querySelector(".save-button").click()');
      await until('document.querySelector(".error-banner")?.textContent.includes("File changed on disk")', 'save conflict');
      assert.equal(fs.readFileSync(path.join(project, 'app/main.py'), 'utf8'), 'external_change = True\n');
      await js('[...document.querySelectorAll(".close-tab")].find(b=>b.getAttribute("aria-label")==="Close app/main.py").click()');
      await until('!!document.querySelector(".discard-banner")', 'discard guard');
      await js('[...document.querySelectorAll(".discard-banner button")].find(b=>b.textContent==="Discard changes").click()');
      await until('!document.querySelector(".dirty-dot")', 'discard completed');
      await delay(200);
      // Start a real long-running child and verify main's awaited shutdown owns it.
      const context = await js('window.openarise.project.openProject()');
      assert.equal(context.ok, true);
      const projectId = context.data.id;
      const opened = await js('window.openarise.project.readFile(' + JSON.stringify({ projectId, path: 'long.py' }) + ')');
      assert.equal(opened.ok, true);
      const created = await js('window.openarise.terminal.request(' + JSON.stringify({ projectId, operation: 'create' }) + ')');
      assert.equal(created.ok, true);
      const sessionId = created.data.sessions[0].id;
      const run = await js('window.openarise.terminal.request(' + JSON.stringify({ projectId, sessionId, operation: 'execute', command: 'python long.py', revision: opened.data.revision }) + ')');
      assert.equal(run.ok, true);
      for (let i = 0; i < 100; i++) {
        const state = await js('window.openarise.terminal.request(' + JSON.stringify({ projectId, operation: 'snapshot' }) + ')');
        const match = state.data.sessions[0].output.map(o=>o.text).join('').match(/PID=(\d+)/);
        if (match) { shutdownPid = Number(match[1]); break; }
        await delay(100);
      }
      assert.ok(shutdownPid, 'Running process observed before shutdown');
      console.log('Electron Phase 7 smoke passed (AI fixtures only): factual activity states/history, reduced motion, static logo; intelligence nine views, baseline/drift, responsive layout, navigation; AI offline permission/resume/unverified/context plus editor/save/conflict, Python stdout/stderr, pytest, terminal sessions, sandbox, three sizes and running-process shutdown.');
      clearTimeout(timeout); app.quit();
    } catch (error) { console.error(error); clearTimeout(timeout); app.exit(1); }
  });
});
const fixtureBackend = require('./fixtures/smoke-backend.cjs')();
require('../dist-electron/main.cjs').startDesktop(fixtureBackend);
