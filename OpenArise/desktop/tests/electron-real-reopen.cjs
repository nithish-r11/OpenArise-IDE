const { app, dialog, BrowserWindow } = require('electron');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const base = path.resolve(__dirname, '../.packaging/real-flow');
const project = path.join(base, 'project');
if (!fs.existsSync(path.join(project, 'main.py'))) throw new Error('Run electron-real-flow.cjs first.');
app.setPath('userData', path.join(base, 'profile'));
dialog.showOpenDialog = async () => ({ canceled:false, filePaths:[project] });
const timer = setTimeout(() => { console.error('Reopen timed out'); app.exit(1); }, 30000);
const delay = ms => new Promise(r=>setTimeout(r,ms));
app.once('browser-window-created', (_e,window) => {
  const js = x => window.webContents.executeJavaScript(x);
  const until = async (x,label) => {
    for (let i=0;i<100;i++) { if (await js(x)) return; await delay(100); }
    throw new Error('Timed out: '+label);
  };
  window.webContents.once('did-finish-load', async () => {
    try {
      await until('!!document.querySelector(".open-project")','welcome');
      assert.equal(BrowserWindow.getAllWindows().length,1);
      assert.equal(window.isVisible(),true);
      await js('document.querySelector(".open-project").click()');
      await until('!![...document.querySelectorAll(".tree-file")].find(b=>b.textContent.includes("main.py"))','explorer');
      await js('[...document.querySelectorAll(".tree-file")].find(b=>b.textContent.includes("main.py")).click()');
      await until('document.querySelector(".view-lines")?.textContent.includes("EXTERNAL_WRITE")','persisted file');
      assert.equal(fs.readFileSync(path.join(project,'main.py'),'utf8'),'print("EXTERNAL_WRITE")\n');
      console.log('Close/reopen passed: one Electron window, persisted project file visible.');
      clearTimeout(timer); app.quit();
    } catch (error) { console.error(error); clearTimeout(timer); app.exit(1); }
  });
});
require('../dist-electron/main.cjs').startDesktop();
