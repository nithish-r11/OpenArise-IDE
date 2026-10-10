// Visible real Electron renderer/main/preload + production Python backend/file writes.
// Inference and native folder choice are deterministic test fixtures, never live AI.
const { app, dialog, BrowserWindow } = require('electron');
const { spawn } = require('node:child_process');
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const base = path.resolve(__dirname, '../.packaging/permission-safety-' + Date.now());
const project = path.join(base, 'project');
fs.mkdirSync(project, { recursive: true }); fs.writeFileSync(path.join(project, 'original.py'), 'value = "KEEP"\n');
app.setPath('userData', path.join(base, 'profile'));
dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [project] });
const methods = [], results = [];
class RealBackend {
  constructor() {
    this.child = spawn(path.resolve(__dirname, '../../ai-engine/.venv/Scripts/python.exe'), [path.join(__dirname, 'fixtures/permission-backend.py'), project], { windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'] });
    this.buffer = ''; this.ready = new Promise(resolve => this.resolveReady = resolve);
    this.child.stdout.setEncoding('utf8');
    this.child.stdout.on('data', chunk => {
      this.buffer += chunk;
      while (this.buffer.includes('\n')) {
        const end = this.buffer.indexOf('\n'); const value = JSON.parse(this.buffer.slice(0, end)); this.buffer = this.buffer.slice(end + 1);
        if (value.ready) this.resolveReady();
        else { const resolve = this.pending; this.pending = null; results.push(value); resolve({ kind: 'backend', response: value }); }
      }
    });
    this.child.stderr.on('data', chunk => console.error(String(chunk).slice(0, 1000)));
    this.child.on('error', error => { console.error(error); app.exit(1); });
  }
  async connect() { await this.ready; return { status: 'connected', reason: 'ready' }; }
  async request(request) { await this.ready; assert.ok(!this.pending, 'One backend command at a time'); methods.push(request.method); return new Promise(resolve => { this.pending = resolve; this.child.stdin.write(JSON.stringify(request) + '\n'); }); }
  async disconnect() { await this.request({ request_id: 'test-shutdown', method: 'shutdown', params: {} }); this.child.stdin.end(); return { status: 'disconnected', reason: 'closed' }; }
}
const adapter = new RealBackend(), delay = ms => new Promise(r => setTimeout(r, ms));
const timer = setTimeout(() => { console.error('Permission integration timed out', base); adapter.child.kill(); app.exit(1); }, 120000);
app.once('browser-window-created', (_event, window) => {
  const js = code => window.webContents.executeJavaScript(code);
  const until = async (code, label) => { for (let i = 0; i < 200; i++) { if (await js(code)) return; await delay(50); } throw Error('Timed out: ' + label); };
  const button = text => js('[...document.querySelectorAll("button")].find(b=>b.textContent.trim()===' + JSON.stringify(text) + '&&!b.disabled).click()');
  const command = async (method, target, tool = 'same-write-id') => js('window.openarise.request(' + JSON.stringify({request_id: 'qa-' + Math.random().toString(36).slice(2), method, params:{request_id:target,tool_call_id:tool}}) + ',' + JSON.stringify(projectId) + ')');
  let projectId;
  const ask = async file => {
    await button('Make changes'); await js('document.querySelector("#ai-prompt").focus()');
    await window.webContents.insertText('Create ' + file); await button('Send ↗');
    await until('!!document.querySelector(".ai-permission[data-state=permission_required]")', 'real permission card');
    const latest = results.filter(r => r.data?.status === 'permission_required').at(-1);
    assert.equal(latest.data.pending_action.resource, file); assert.equal(latest.data.pending_action.tool_call_id, 'same-write-id');
    assert.equal(fs.existsSync(path.join(project, file)), false); return latest.data.request_id;
  };
  window.webContents.once('did-finish-load', async () => {
    try {
      await until('!!document.querySelector(".open-project")', 'visible app');
      assert.equal(window.isVisible(), true); assert.equal(BrowserWindow.getAllWindows().length, 1);
      assert.deepEqual(Object.fromEntries(['contextIsolation','nodeIntegration','sandbox','webSecurity'].map(k=>[k,window.webContents.getLastWebPreferences()[k]])), {contextIsolation:true,nodeIntegration:false,sandbox:true,webSecurity:true});
      await js('document.querySelector(".open-project").click()');
      await until('document.querySelector(".ai-context")?.textContent.includes("1 project files")', 'real project');
      const recent = await js('window.openarise.project.recentProjects()');
      assert.equal(recent.ok, true); assert.equal(recent.data.length, 1); assert.equal(recent.data[0].rootPath, project);
      projectId = recent.data[0].id;
      const missing = await ask('unapproved.py');
      const noApproval = await command('resume_agent_execution', missing);
      assert.equal(noApproval.response.data.status, 'permission_required'); assert.equal(fs.existsSync(path.join(project, 'unapproved.py')), false);
      const invalid = await command('approve_agent_action', missing, 'wrong-call');
      assert.equal(invalid.response.success, false); assert.equal(fs.existsSync(path.join(project, 'unapproved.py')), false);
      await button('Deny'); await until('document.querySelector(".ai-result>strong")?.textContent==="Denied"', 'denial result');
      assert.equal(fs.existsSync(path.join(project, 'unapproved.py')), false);
      const afterDeny = await command('resume_agent_execution', missing);
      assert.equal(afterDeny.response.success, false); assert.equal(fs.existsSync(path.join(project, 'unapproved.py')), false);
      await ask('denied.py'); const beforeDeny = methods.length; await button('Deny');
      await until('document.querySelector(".ai-result>strong")?.textContent==="Denied"', 'second exact denial');
      assert.deepEqual(methods.slice(beforeDeny), ['deny_agent_action']); assert.equal(fs.existsSync(path.join(project, 'denied.py')), false);
      const allowed = await ask('allowed.py'); const beforeAllow = methods.length; await button('Allow');
      await until('document.querySelector(".ai-result>strong")?.textContent==="Not verified"', 'actual write result');
      assert.deepEqual(methods.slice(beforeAllow), ['approve_agent_action','resume_agent_execution']);
      assert.equal(fs.readFileSync(path.join(project, 'allowed.py'), 'utf8'), 'answer = 42\n');
      const replay = await command('resume_agent_execution', allowed);
      assert.equal(replay.response.success, false);
      assert.equal(fs.readFileSync(path.join(project, 'original.py'), 'utf8'), 'value = "KEEP"\n');
      fs.writeFileSync(path.join(base, 'evidence.json'), JSON.stringify({fixtureInference:true,states:'Production backend',methods,results,status:'VERIFIED'},null,2));
      console.log('PERMISSION UI/BACKEND VERIFIED:', base); clearTimeout(timer); app.quit();
    } catch(error) { console.error(error); fs.writeFileSync(path.join(base,'failure.json'),JSON.stringify({error:String(error),methods,results},null,2)); clearTimeout(timer); adapter.child.kill(); app.exit(1); }
  });
});
require('../dist-electron/main.cjs').startDesktop(adapter);
