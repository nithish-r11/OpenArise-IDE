// Source-only acceptance observer. Actual IPC handlers/results are not replaced.
// All AI generation uses real Qwen. Allow is clicked only for disposable scope.
const {app,dialog,BrowserWindow,ipcMain}=require('electron');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const base=path.resolve(__dirname,'../.packaging/final-acceptance/live-'+Date.now());
const GOOD='def multiply(a, b):\n    return a * b\n';
const TEST='from math_ops import multiply\n\ndef test_multiply():\n    assert multiply(3, 4) == 12\n    assert multiply(-2, 5) == -10\n';
const projects=['success','failure'].map(name=>path.join(base,name));
for(const project of projects){
 fs.mkdirSync(project,{recursive:true});
 fs.writeFileSync(path.join(project,'math_ops.py'),GOOD);
 fs.writeFileSync(path.join(project,'test_math_ops.py'),TEST);
}
fs.writeFileSync(path.join(projects[1],'test_unrecoverable.py'),'def test_controlled_failure():\n    assert False, "Intentional acceptance failure: preserve this test"\n');
const collected=[],evidence={fixture:false,provider:'real local Ollama',base,results:[],responses:collected};
const handle=ipcMain.handle.bind(ipcMain);
ipcMain.handle=(channel,listener)=>handle(channel,async(...args)=>{
 const result=await listener(...args);
 if(result?.kind==='backend')collected.push({method:args[1]?.method,response:result.response,source:result.source});
 return result;
});
app.setPath('userData',path.join(base,'profile'));
let pick=0;dialog.showOpenDialog=async()=>({canceled:false,filePaths:[projects[Math.min(pick++,1)]]});
const delay=ms=>new Promise(r=>setTimeout(r,ms));
const timer=setTimeout(()=>{fs.writeFileSync(path.join(base,'evidence.json'),JSON.stringify(evidence,null,2));console.error('Live recovery deadline');app.exit(1);},2400000);
app.once('browser-window-created',(_e,window)=>{
 const js=code=>window.webContents.executeJavaScript(code);
 async function until(code,name,budget=45000){
  const end=Date.now()+budget;
  while(Date.now()<end){if(await code())return;await delay(100);}
  throw new Error('Timed out: '+name);
 }
 async function ask(prompt){
  const before=collected.length;
  await js('document.querySelector(".ai-mode button:nth-child(2)").click();document.querySelector("#ai-prompt").focus()');
  await window.webContents.insertText(prompt);
  await until(()=>js('!document.querySelector(".ai-submit").disabled'),'send ready');
  await js('document.querySelector(".ai-submit").click()');
  await until(()=>Promise.resolve(collected.slice(before).some(x=>x.method==='request_agent_execution')),'actual model action response',300000);
  return collected.slice(before).find(x=>x.method==='request_agent_execution').response.data;
 }
 async function decide(r,project,deny=false){
  const pending=r.pending_action;
  assert.ok(pending,'Actual permission required');
  assert.ok(['write_file','execute_tests'].includes(pending.tool_name),'Only controlled mutation/pytest may be approved');
  if(pending.tool_name==='write_file')assert.equal(pending.resource,'math_ops.py','Refuse unrelated writes or test edits');
  assert.equal(fs.readFileSync(path.join(project,'test_math_ops.py'),'utf8'),TEST);
  await until(()=>js('document.querySelector("#ai-history")?.value==='+JSON.stringify(r.request_id)+' && document.querySelector(".ai-permission[data-state=permission_required]")?.textContent.includes('+JSON.stringify(pending.tool_call_id)+') && !![...document.querySelectorAll(".permission-actions button")].find(b=>b.textContent==="Allow"&&!b.disabled)'),'matching actual permission card ready',30000);
  const before=collected.length;
  await js('[...document.querySelectorAll(".permission-actions button")].find(b=>b.textContent==="'+(deny?'Deny':'Allow')+'").click()');
  const method=deny?'deny_agent_action':'resume_agent_execution';
  await until(()=>Promise.resolve(collected.slice(before).some(x=>x.method===method)),'actual approved/denied backend execution',650000);
  const next=collected.slice(before).find(x=>x.method===method).response.data;
  assert.equal(fs.readFileSync(path.join(project,'test_math_ops.py'),'utf8'),TEST,'Original assertions must remain intact');
  console.log('Actual decision result:',next.status,next.current_state,next.pending_action?.tool_name,next.data.recovery?.status);
  return next;
 }
 async function finish(r,project){
  let steps=0;
  while(r.pending_action){
   if(++steps>10)throw new Error('Unexpected action count');
   r=await decide(r,project);
   // Before any subsequent execution, inspect the written implementation.
   const content=fs.readFileSync(path.join(project,'math_ops.py'),'utf8');
   assert.doesNotMatch(content,/\b(?:import|open|exec|eval|subprocess|os\.|sys\.)\b/,'Disposable program must remain arithmetic only');
  }
  return r;
 }
 window.webContents.once('did-finish-load',async()=>{
  try{
   await until(()=>js('!!document.querySelector(".open-project") && document.visibilityState==="visible"'),'visible app');
   assert.equal(window.isVisible(),true);assert.equal(BrowserWindow.getAllWindows().length,1);
   await js('document.querySelector(".open-project").click()');
   await until(()=>js('document.querySelector(".ollama-status")?.textContent.includes("Ollama detected")'),'real model detected');
   await js('if(!document.querySelector(".ai-workspace").classList.contains("ai-expanded"))document.querySelector(".ai-toggle").click()');
   let r=await ask('Use write_file to overwrite math_ops.py with exactly: def multiply(a, b): return a + b. Set overwrite=true. Do not execute anything. This is a disposable acceptance change.');
   r=await decide(r,projects[0],true);
   assert.equal(r.status,'denied');assert.equal(fs.readFileSync(path.join(projects[0],'math_ops.py'),'utf8'),GOOD);
   await until(()=>js('document.querySelector("#ai-history")?.value==='+JSON.stringify(r.request_id)+' && document.querySelector(".ai-permission")?.dataset.state==="denied" && !document.querySelector(".ai-mode button").disabled'),'settled denial UI');
   evidence.results.push({case:'denied',result:r});
   const prompt='Demonstrate controlled recovery and finish with correct multiplication and the original tests passing. Produce one tool_call action containing all THREE ordered tool calls: (1) execute_tests to record a passing baseline; (2) write_file path math_ops.py, overwrite=true, content "def multiply(a, b):\\n    return a + b\\n" to introduce an intentional fault; (3) execute_tests to expose that fault. Then let the existing recovery engine repair math_ops.py to return a * b and retest. Never modify test_math_ops.py or weaken assertions. The original function returns a * b; the tests require multiply(3,4)==12 and multiply(-2,5)==-10. Preserve requirement identity and do not claim completion without fresh passing test proof.';
   r=await finish(await ask(prompt),projects[0]);
   assert.equal(r.status,'success','Real recovery must finish verified');
   assert.equal(r.data.recovery?.status,'RECOVERED');
   assert.equal(r.data.verification.overall_status,'VERIFIED');
   const proof=r.data.evidence;
   assert.equal(new Set(proof.map(e=>e.requirement_id)).size,1);
   assert.ok(proof.some(e=>e.evidence_type==='TEST_PASS'&&e.stale&&e.superseded),'Baseline must become stale after mutation');
   assert.ok(proof.some(e=>e.evidence_type==='TEST_FAIL'&&e.success===false&&e.resolved_by),'Failed evidence must remain linked to real retest');
   assert.ok(proof.some(e=>e.evidence_type==='TEST_PASS'&&e.success&&e.exit_code===0&&!e.stale&&!e.superseded),'Fresh passing proof required');
   assert.ok(r.data.recovery.tests_run.length>0);
   await until(()=>js('document.querySelector(".ai-completion>strong")?.textContent==="VERIFIED" && document.querySelector(".arise-activity")?.dataset.state==="completed" && !document.querySelector(".ai-mode button").disabled'),'settled CompletionGate VERIFIED');
   for(const [width,height] of [[1320,880],[1050,740],[760,540]]){
    window.setSize(width,height);await delay(500);
    await js('document.querySelector(".ai-completion").scrollIntoView({block:"center"})');await delay(350);
    assert.equal(await js('(()=>{const h=document.querySelector(".ai-completion>strong").getBoundingClientRect(),p=document.querySelector(".ai-conversation").getBoundingClientRect();return h.top>=p.top && h.bottom<=p.bottom && h.right<=innerWidth})()'),true,'Real VERIFIED heading must be visible');
    fs.writeFileSync(path.join(base,`verified-${width}x${height}.png`),(await window.webContents.capturePage()).toPNG());
   }
   window.setSize(1320,880);await delay(300);
   evidence.results.push({case:'recovery-success',result:r});
   fs.writeFileSync(path.join(projects[0],'math_ops.py'),'def multiply(a, b):\n    return a - b\n');
   const before=collected.length;
   await js('[...document.querySelectorAll("button")].find(b=>b.textContent==="Refresh request result").click()');
   await until(()=>Promise.resolve(collected.slice(before).some(x=>x.method==='get_agent_execution')),'fresh gate retrieval after external mutation');
   const stale=collected.slice(before).find(x=>x.method==='get_agent_execution').response.data;
   assert.notEqual(stale.data.verification.overall_status,'VERIFIED');
   await until(()=>js('document.querySelector("#ai-history")?.value==='+JSON.stringify(stale.request_id)+' && document.querySelector(".ai-completion>strong")?.textContent==="FAILED" && document.querySelector(".ai-result")?.textContent.includes('+JSON.stringify(stale.message)+') && !document.querySelector(".ai-mode button").disabled'),'settled stale proof refused by UI');
   evidence.results.push({case:'stale-proof-blocked',result:stale});
   await js('document.querySelector(".open-project").click()');
   await until(()=>js('document.querySelector(".ai-context")?.textContent.includes("failure") && !document.querySelector(".ai-submit").textContent.includes("Waiting")'),'failure project loaded');
   r=await finish(await ask('Demonstrate a controlled unsuccessful recovery. Produce one tool_call action containing all TWO ordered tool calls: (1) write_file with path math_ops.py, overwrite=true and content "def multiply(a, b):\\n    return a + b\\n", (2) execute_tests on the whole project. Include both calls in this one action. The recovery engine may try to repair math_ops.py to multiply correctly. Preserve every test unchanged, including test_unrecoverable.py which deliberately always fails for acceptance. Do not change test files or fake success. Return the actual failed or unverified CompletionGate outcome.'),projects[1]);
   assert.ok(['failure','unverified'].includes(r.status));
   assert.notEqual(r.data.verification?.overall_status,'VERIFIED');
   assert.ok(r.data.tool_results.some(t=>t.tool_name==='execute_tests' && t.executed && !t.success && t.exit_code!==0),'Actual failed pytest must be detected');
   assert.ok(r.data.recovery && r.data.recovery.attempts>=1,'Actual recovery planning/result must be returned');
   assert.notEqual(r.data.recovery.status,'RECOVERED');
   await until(()=>js('document.querySelector("#ai-history")?.value==='+JSON.stringify(r.request_id)+' && document.querySelector(".ai-result")?.classList.contains('+JSON.stringify('state-'+r.status)+') && document.querySelector(".ai-completion>strong")?.textContent==="FAILED" && document.querySelector(".ai-result")?.textContent.includes('+JSON.stringify(r.message)+') && !document.querySelector(".ai-mode button").disabled && !document.querySelector(".permission-actions")'),'matching final failure UI settled');
   await js('document.querySelector(".ai-completion").scrollIntoView({block:"center"})');await delay(500);
   fs.writeFileSync(path.join(base,'failure.png'),(await window.webContents.capturePage()).toPNG());
   evidence.results.push({case:'recovery-failure',result:r});
   assert.ok(collected.every(x=>x.source==='backend'),'All acceptance data must come from actual backend');
   fs.writeFileSync(path.join(base,'evidence.json'),JSON.stringify(evidence,null,2));
   fs.writeFileSync(path.resolve(__dirname,'../.packaging/final-acceptance/latest-live.json'),JSON.stringify({base},null,2));
   console.log('LIVE RECOVERY / VERIFICATION ACCEPTANCE PASSED',base);
   clearTimeout(timer);app.quit();
  }catch(error){evidence.error=String(error);fs.writeFileSync(path.join(base,'evidence.json'),JSON.stringify(evidence,null,2));console.error(error);clearTimeout(timer);app.exit(1);}
 });
});
require('../dist-electron/main.cjs').startDesktop();
