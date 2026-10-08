// Release QA only: actual bundled stdio host, BackendService and Ollama; no UI/AI fixtures.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process'),{createInterface}=require('node:readline'),{randomUUID}=require('node:crypto');
const root=fs.realpathSync(process.argv[2]||'release/win-unpacked');
const failureCase=process.argv.includes('--failure');
const resources=path.join(root,'resources'),python=path.join(resources,'ai-engine/.venv/Scripts/python.exe');
const base=path.resolve(__dirname,'../.packaging/final-acceptance/packaged-live-'+Date.now());
const project=path.join(base,'project');fs.mkdirSync(project,{recursive:true});
const good='def multiply(a, b):\n    return a * b\n';
const test='from math_ops import multiply\n\ndef test_multiply():\n    assert multiply(3, 4) == 12\n    assert multiply(-2, 5) == -10\n';
fs.writeFileSync(path.join(project,'math_ops.py'),good);fs.writeFileSync(path.join(project,'test_math_ops.py'),test);
const impossible='def test_controlled_failure():\n    assert False, "Intentional acceptance failure: preserve this test"\n';
if(failureCase)fs.writeFileSync(path.join(project,'test_unrecoverable.py'),impossible);
const env={...process.env,PATH:path.join(process.env.SystemRoot||'C:/Windows','System32'),PYTHONIOENCODING:'utf-8'};delete env.PYTHONHOME;delete env.PYTHONPATH;
const child=spawn(python,['-I','-B','-u',path.join(resources,'desktop/python/agent_host.py'),project],{cwd:path.join(resources,'ai-engine'),env,shell:false,windowsHide:true,stdio:['pipe','pipe','pipe']});
const waiting=new Map(),responses=[];let readyResolve,readyReject;
const ready=new Promise((resolve,reject)=>{readyResolve=resolve;readyReject=reject;});
const readyTimer=setTimeout(()=>readyReject(new Error('Bundled host readiness deadline')),30000);
child.stderr.pipe(fs.createWriteStream(path.join(base,'diagnostics.log')));
createInterface({input:child.stdout}).on('line',line=>{const r=JSON.parse(line);if(r.ready){clearTimeout(readyTimer);readyResolve();return;}responses.push(r);const p=waiting.get(r.request_id);if(p){waiting.delete(r.request_id);clearTimeout(p.timer);p.resolve(r);}});
const rejectPending=error=>{clearTimeout(readyTimer);readyReject(error);for(const p of waiting.values()){clearTimeout(p.timer);p.reject(error);}waiting.clear();};
child.on('error',rejectPending);child.on('close',code=>rejectPending(new Error('Bundled host closed: '+code)));
async function command(method,params={}){const id=randomUUID();const reply=new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(new Error('Bundled backend deadline: '+method)),900000);waiting.set(id,{resolve,reject,timer});});child.stdin.write(JSON.stringify({request_id:id,method,params})+'\n');const r=await reply;assert.equal(r.success,true,JSON.stringify(r.error));return r.data;}
(async()=>{try{
 await ready;const context=await command('get_intelligence_snapshot');assert.equal(context.ollama.status,'ready');assert.equal(context.ollama.model,'qwen2.5-coder:7b');
 const prompt=failureCase?'Demonstrate a controlled unsuccessful recovery. Produce one tool_call action containing all TWO ordered tool calls: (1) write_file with path math_ops.py, overwrite=true and content "def multiply(a, b):\\n    return a + b\\n", (2) execute_tests on the whole project. Include both calls in this one action. The recovery engine may try to repair math_ops.py to multiply correctly. Preserve every test unchanged, including test_unrecoverable.py which deliberately always fails for acceptance. Do not change test files or fake success. Return the actual failed or unverified CompletionGate outcome.':'Restore correct multiplication after controlled recovery, preserving original tests. Produce one tool_call action with all THREE ordered calls: (1) execute_tests for a passing baseline; (2) write_file path math_ops.py, overwrite=true, content "def multiply(a, b):\\n    return a + b\\n" to introduce a fault; (3) execute_tests to detect it. The existing recovery engine must repair math_ops.py to return a * b and retest. Never edit test_math_ops.py. The tests require multiply(3,4)==12 and multiply(-2,5)==-10. Do not claim verification without fresh passing proof.';
 let r=await command('request_agent_execution',{prompt});
 let steps=0;while(r.pending_action){if(++steps>10)throw new Error('Unexpected action count');const p=r.pending_action;assert.ok(['write_file','execute_tests'].includes(p.tool_name));if(p.tool_name==='write_file')assert.equal(p.resource,'math_ops.py');const params={request_id:r.request_id,tool_call_id:p.tool_call_id};await command('approve_agent_action',params);r=await command('resume_agent_execution',params);assert.equal(fs.readFileSync(path.join(project,'test_math_ops.py'),'utf8'),test);assert.doesNotMatch(fs.readFileSync(path.join(project,'math_ops.py'),'utf8'),/\b(?:import|open|exec|eval|subprocess|os\.|sys\.)\b/);console.log('Bundled real decision:',r.status,p.tool_name,r.data.recovery?.status);}
 if(failureCase){
 assert.equal(fs.readFileSync(path.join(project,'test_unrecoverable.py'),'utf8'),impossible);
 assert.ok(['failure','unverified'].includes(r.status));assert.notEqual(r.data.verification.overall_status,'VERIFIED');
 assert.ok(r.data.tool_results.some(t=>t.tool_name==='execute_tests'&&t.executed&&!t.success&&t.exit_code!==0));
 assert.ok(r.data.recovery&&r.data.recovery.attempts>=1);assert.notEqual(r.data.recovery.status,'RECOVERED');
 }else{
 assert.equal(r.status,'success');assert.equal(r.data.recovery.status,'RECOVERED');assert.equal(r.data.verification.overall_status,'VERIFIED');
 assert.ok(r.data.evidence.some(e=>e.evidence_type==='TEST_PASS'&&e.stale&&e.superseded));assert.ok(r.data.evidence.some(e=>e.evidence_type==='TEST_FAIL'&&e.resolved_by));assert.ok(r.data.evidence.some(e=>e.evidence_type==='TEST_PASS'&&e.success&&!e.stale&&!e.superseded));
 }
 const evidence={fixture:false,status:'VERIFIED',case:failureCase?'failure':'success',scope:'Actual bundled host/backend; native packaged UI is validated separately',root,python,minimalPATH:env.PATH,project,result:r,responses};fs.writeFileSync(path.join(base,'evidence.json'),JSON.stringify(evidence,null,2));fs.writeFileSync(path.resolve(__dirname,'../.packaging/final-acceptance/latest-packaged-'+(failureCase?'failure':'live')+'.json'),JSON.stringify({base},null,2));
 await command('shutdown');child.stdin.end();console.log('PACKAGED REAL OLLAMA '+(failureCase?'FAILURE REFUSAL':'RECOVERY')+' VERIFIED',base);
 }catch(error){fs.writeFileSync(path.join(base,'evidence.json'),JSON.stringify({fixture:false,error:String(error),root,project,responses},null,2));console.error(error);child.stdin.end();process.exitCode=1;}})();
