// Live acceptance: real Ollama through renderer/preload/main/Python/orchestrator.
// Only the native folder picker gets a known temporary project. No AI fixture.
const { app, dialog, BrowserWindow } = require('electron');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const base = path.resolve(__dirname, '../.packaging/ollama-integration/live-ui');
const project = path.join(base, 'project');
fs.mkdirSync(project, {recursive:true});
fs.writeFileSync(path.join(project,'main.py'),'def add(a, b):\n    return a + b\n');
app.setPath('userData', path.join(base,'profile'));
dialog.showOpenDialog = async () => ({canceled:false,filePaths:[project]});
const delay = ms => new Promise(resolve => setTimeout(resolve,ms));
const timer = setTimeout(()=>{ console.error('Live acceptance timed out'); app.exit(1); },900000);
const evidence = { provider:'real Ollama', fixture:false, prompts:[], viewport:[], toolPermission:null };
app.once('browser-window-created', (_event, window) => {
 const js = async code => {try{return await window.webContents.executeJavaScript(code);}catch(error){console.error("Renderer expression failed:",code);throw error;}};
 async function until(code, name, limit=30000) {
  const end=Date.now()+limit;
  while(Date.now()<end) { if(await js(code)) return; await delay(100); }
  throw new Error('Timed out: '+name);
 }
 async function ask(prompt) {
  await js('document.querySelector("#ai-prompt").focus()');
  await window.webContents.insertText(prompt);
  await until('!document.querySelector(".ai-submit").disabled','submit enabled');
  await js('document.querySelector(".ai-submit").click()');
  await until('document.querySelector(".ai-result")?.textContent.includes("Backend state:") && document.querySelector(".ai-submit")?.textContent === "Send ↗"','actual backend result',240000);
  await delay(350); // Observe the settled, painted React response and scroll effect.
  const result=await js('({text:document.querySelector(".ai-result").innerText,answer:document.querySelector(".ai-model-response pre")?.textContent,source:document.querySelector(".ai-data-source")?.innerText,activity:document.querySelector(".arise-activity").dataset.state,answerTop:document.querySelector(".ai-model-response")?.getBoundingClientRect().top,panelTop:document.querySelector(".ai-conversation").getBoundingClientRect().top,panelBottom:document.querySelector(".ai-conversation").getBoundingClientRect().bottom})');
  assert.ok(result.answerTop>=result.panelTop && result.answerTop<result.panelBottom,'Model answer heading must be in the actual visible conversation');
  console.log('Real UI response:',JSON.stringify(result));
  return result;
 }
 window.webContents.once('did-finish-load',async()=>{
  try {
   await until('!!document.querySelector(".open-project") && document.visibilityState==="visible"','visible welcome');
   assert.equal(window.isVisible(),true);
   assert.equal(BrowserWindow.getAllWindows().length,1);
   assert.equal(window.getTitle(),'OpenArise');
   await js('document.querySelector(".open-project").click()');
   await until('document.querySelector(".ollama-status")?.textContent.includes("Ollama detected") && document.querySelector(".ai-context")?.textContent.includes("1 files")','automatic real context and availability');
   evidence.context=await js('document.querySelector(".ai-context").innerText');
   await js('if(!document.querySelector(".ai-workspace").classList.contains("ai-expanded")) document.querySelector(".ai-toggle").click()');
   assert.equal(await js('document.querySelector(".ai-mode button").getAttribute("aria-pressed")'),'true');
   const prompts=['Create a Python function named multiply(a, b) that returns a * b.','Explain this project in 3 short points.'];
   for(let i=0;i<prompts.length;i++) {
    const started=Date.now(), result=await ask(prompts[i]);
    assert.match(result.source,/BACKEND RESPONSE/); assert.doesNotMatch(result.source,/TEST FIXTURE/);
    assert.ok(result.answer?.trim(),'Actual model text must display');
    assert.match(result.text,/Unverified/); assert.doesNotMatch(result.text,/Verified by CompletionGate/);
    assert.equal(result.activity,'unverified');
    if(i===0) { assert.match(result.answer,/def\s+multiply\s*\(\s*a\s*,\s*b\s*\)/); assert.match(result.answer,/return\s+a\s*\*\s*b/); }
    evidence.prompts.push({prompt:prompts[i],elapsedSeconds:(Date.now()-started)/1000,...result});
    assert.equal(fs.existsSync(path.join(project,'multiply.py')),false);
    fs.writeFileSync(path.join(base,'answer-'+i+'.png'),(await window.webContents.capturePage()).toPNG());
   }
   for(const [w,h] of [[1320,880],[1050,740],[760,540]]) {
    window.setSize(w,h); await delay(350);
    const layout=await js('({overflow:document.documentElement.scrollWidth>innerWidth,composerVisible:document.querySelector(".ai-composer").getBoundingClientRect().bottom<=innerHeight,conversationHeight:document.querySelector(".ai-conversation").getBoundingClientRect().height})');
    assert.equal(layout.overflow,false); assert.equal(layout.composerVisible,true); assert.ok(layout.conversationHeight>=120);
    evidence.viewport.push({w,h,...layout});
    fs.writeFileSync(path.join(base,'live-'+w+'x'+h+'.png'),(await window.webContents.capturePage()).toPNG());
   }
   window.setSize(1320,880);
   await js('document.querySelector(".ai-mode button:nth-child(2)").click()');
   await js('document.querySelector("#ai-prompt").focus()');
   await window.webContents.insertText('Use write_file to create multiply.py in this project with content: def multiply(a, b): return a * b. Do not execute code.');
   await until('!document.querySelector(".ai-submit").disabled','tool submit enabled');
   await js('document.querySelector(".ai-submit").click()');
   await until('!!document.querySelector(".ai-permission") || document.querySelector(".ai-result")?.textContent.includes("Backend state:")','tool response',240000);
   const tool=await js('document.querySelector(".ai-conversation").innerText');
   assert.match(tool,/OpenArise needs permission/,'Real model write must stop for approval');
   assert.equal(fs.existsSync(path.join(project,'multiply.py')),false);
   fs.writeFileSync(path.join(base,'permission.png'),(await window.webContents.capturePage()).toPNG());
   await js('[...document.querySelectorAll("button")].find(b=>b.textContent==="Deny").click()');
   await until('document.querySelector(".ai-result")?.textContent.includes("Denied")','denied backend response');
   assert.equal(fs.existsSync(path.join(project,'multiply.py')),false);
   evidence.toolPermission={required:true,denied:true,fileCreated:false,text:await js('document.querySelector(".ai-conversation").innerText')};
   fs.writeFileSync(path.join(base,'evidence.json'),JSON.stringify(evidence,null,2));
   console.log('LIVE OLLAMA UI VERIFIED:',path.join(base,'evidence.json'));
   clearTimeout(timer); app.quit();
  } catch(error) {
   evidence.error=String(error);fs.writeFileSync(path.join(base,'evidence.json'),JSON.stringify(evidence,null,2));
   console.error(error); clearTimeout(timer);app.exit(1);
  }
 });
});
require('../dist-electron/main.cjs').startDesktop();