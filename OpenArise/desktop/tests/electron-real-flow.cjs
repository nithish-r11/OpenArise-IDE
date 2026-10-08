// This acceptance probe uses the actual Python backend. Only the native
// folder picker is supplied a known temporary path for unattended execution.
const { app, dialog, BrowserWindow } = require('electron');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const base = path.resolve(__dirname, '../.packaging/real-flow');
const project = path.join(base, 'project');
fs.mkdirSync(project, { recursive: true });
fs.writeFileSync(path.join(project, 'main.py'), 'print("REAL_PYTHON_RUN")\n');
fs.writeFileSync(path.join(project, 'test_main.py'), 'def test_real_pytest():\n    assert 2 + 2 == 4\n');
fs.writeFileSync(path.join(project, 'broken.py'), 'def broken(:\n    pass\n');
app.setPath('userData', path.join(base, 'profile'));
dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [project] });
const timer = setTimeout(() => { console.error('Real flow timed out'); app.exit(1); }, 360000);
const delay = ms => new Promise(r => setTimeout(r, ms));
app.once('browser-window-created', (_event, window) => {
  const js = expression => window.webContents.executeJavaScript(expression);
  async function until(expression, name, cycles = 150) {
    for (let i = 0; i < cycles; i++) {
      if (await js(expression)) return;
      await delay(100);
    }
    throw new Error('Timed out: ' + name);
  }
  window.webContents.on('console-message', details => {
    if (details.level === 'error') console.error('Renderer:', details.message);
  });
  window.webContents.once('did-finish-load', async () => {
    try {
      await until('!!document.querySelector(".open-project")', 'Welcome');
      await until('document.visibilityState === "visible"', 'Visible document');
      assert.equal(window.isVisible(), true);
      assert.equal(BrowserWindow.getAllWindows().length, 1);
      assert.equal(app.getName(), 'OpenArise');
      assert.equal(window.getTitle(), 'OpenArise');
      assert.equal(await js('document.querySelectorAll("[role=tab]").length'), 0);
      assert.equal(await js('document.querySelector(".arise-activity").dataset.state'), 'idle');
      assert.equal(await js('!!document.querySelector(".ai-data-source")'), false);
      console.log('Actual Electron window rendered: one window, OpenArise identity, no project or fake activity.');
      for (const [w,h] of [[1320,880],[1050,740],[760,540]]) {
        window.setSize(w,h); await delay(350);
        const welcome = await js('(()=>{const w=document.querySelector(".editor-welcome").getBoundingClientRect(),l=document.querySelector(".editor-welcome .orbit-mark").getBoundingClientRect();return {overflow:document.documentElement.scrollWidth>innerWidth,logoVisible:l.top>=w.top-1&&l.bottom<=w.bottom+1}})()');
        assert.equal(welcome.overflow,false);
        assert.equal(welcome.logoVisible,true,'First-run logo must not be clipped');
        fs.writeFileSync(path.join(base,'welcome-'+w+'x'+h+'.png'),(await window.webContents.capturePage()).toPNG());
      }
      window.setSize(1320,880); await delay(200);
      await js('document.querySelector(".open-project").click()');
      await until('!![...document.querySelectorAll(".tree-file")].find(b=>b.textContent.includes("main.py"))', 'project tree');
      await js('[...document.querySelectorAll(".tree-file")].find(b=>b.textContent.includes("main.py")).click()');
      await until('!!document.querySelector(".monaco-editor textarea")', 'Monaco editor');
      await until('document.querySelector(".view-lines")?.textContent.includes("REAL_PYTHON_RUN")', 'real file read');
      await js('document.querySelector(".monaco-editor textarea").focus()');
      window.webContents.sendInputEvent({ type:'keyDown', keyCode:'Home', modifiers:['control'] });
      window.webContents.sendInputEvent({ type:'keyUp', keyCode:'Home', modifiers:['control'] });
      await window.webContents.insertText('# Real editor save\n');
      await until('!!document.querySelector(".dirty-dot")', 'dirty editor');
      window.webContents.sendInputEvent({ type:'keyDown', keyCode:'R', modifiers:['control'] });
      window.webContents.sendInputEvent({ type:'keyUp', keyCode:'R', modifiers:['control'] });
      await delay(250);
      assert.equal(await js('!!document.querySelector(".dirty-dot")'), true);
      assert.match(await js('document.querySelector(".view-lines").textContent'), /Real\s+editor\s+save/);
      console.log('Unsaved Ctrl+R reload blocked; editor buffer retained.');
      assert.equal(await js('document.querySelector(".run-python").disabled'), true);
      await js('document.querySelector(".save-button").click()');
      await until('document.querySelector(".save-label")?.textContent==="Saved"', 'save');
      assert.match(fs.readFileSync(path.join(project,'main.py'),'utf8'), /Real\s+editor\s+save/);
      await until('!document.querySelector(".run-python").disabled', 'Python ready');
      await js('document.querySelector(".run-python").click()');
      await until('document.querySelector(".terminal-tools")?.textContent.includes("exited")', 'Python execution', 300);
      assert.match(await js('document.querySelector(".terminal-output").textContent'), /REAL_PYTHON_RUN/);
      await js('document.querySelector(".run-tests").click()');
      await until('document.querySelector(".terminal-tools")?.textContent.includes("pytest passed")', 'pytest execution', 300);
      assert.match(await js('document.querySelector(".terminal-output").textContent'), /1 passed/);
      console.log('Real file save, Python execution and pytest passed.');
      await js('[...document.querySelectorAll(".tree-file")].find(b=>b.textContent.includes("broken.py")).click()');
      await until('document.querySelector(".view-lines")?.textContent.includes("broken")','broken source');
      await until('!document.querySelector(".run-python").disabled','broken file ready');
      await js('document.querySelector(".run-python").click()');
      await until('document.querySelector(".terminal-tools")?.textContent.includes("failed")','real Python failure',300);
      assert.match(await js('document.querySelector(".terminal-output").textContent'), /SyntaxError|invalid syntax/);
      await js('[...document.querySelectorAll("[role=tab]")].find(b=>b.textContent.includes("main.py")).click()');
      await until('document.querySelector(".breadcrumb")?.textContent.includes("main.py")','main tab');
      console.log('Real Python syntax failure was shown in the terminal.');
      for (const [w,h] of [[1320,880],[1050,740],[760,540]]) {
        window.setSize(w,h); await delay(350);
        const layout = await js('({overflow:document.documentElement.scrollWidth>innerWidth,editor:document.querySelector(".editor-container").getBoundingClientRect().width})');
        assert.equal(layout.overflow,false);
        assert.ok(layout.editor >= 280);
        const file = path.join(base,'window-'+w+'x'+h+'.png');
        fs.writeFileSync(file,(await window.webContents.capturePage()).toPNG());
        console.log('Screenshot:', file);
      }
      fs.writeFileSync(path.join(project,'main.py'),'print("EXTERNAL_WRITE")\n');
      await js('document.querySelector(".monaco-editor textarea").focus()');
      await window.webContents.insertText('# conflicting change\n');
      await until('!!document.querySelector(".dirty-dot")', 'dirty conflict');
      await js('document.querySelector(".save-button").click()');
      await until('document.querySelector(".error-banner")?.textContent.includes("File changed on disk")', 'conflict banner');
      assert.equal(fs.readFileSync(path.join(project,'main.py'),'utf8'),'print("EXTERNAL_WRITE")\n');
      await js('[...document.querySelectorAll(".close-tab")].find(b=>b.getAttribute("aria-label")==="Close main.py").click()');
      await until('!!document.querySelector(".discard-banner")','discard guard');
      await js('[...document.querySelectorAll(".discard-banner button")].find(b=>b.textContent==="Discard changes").click()');
      await until('!document.querySelector(".dirty-dot")','discarded');
      console.log('Real conflict safeguard and discard guard passed.');
      window.setSize(1320,880); await delay(400);
      await js('if (!document.querySelector(".ai-workspace").classList.contains("ai-expanded")) document.querySelector(".ai-toggle").click()');
      await js('document.querySelector("#ai-prompt").focus()');
      await window.webContents.insertText('Explain this Python project');
      await until('!document.querySelector(".ai-submit").disabled','AI submission ready');
      await js('document.querySelector(".ai-submit").click()');
      await until('document.querySelector(".ai-result")?.textContent.includes("Backend state:") || document.querySelector(".ai-error")','real AI response',2100);
      const aiOutcome = await js('document.querySelector(".ai-result")?.innerText || document.querySelector(".ai-error")?.innerText');
      console.log('Real AI outcome:', aiOutcome);
      if (/Failed|Backend unavailable/.test(aiOutcome)) assert.doesNotMatch(aiOutcome, /Verified by CompletionGate/);
      clearTimeout(timer); app.quit();
    } catch (error) { console.error(error); clearTimeout(timer); app.exit(1); }
  });
});
require('../dist-electron/main.cjs').startDesktop();
