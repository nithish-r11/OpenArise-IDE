// @vitest-environment node
import { EventEmitter } from 'node:events';
import { spawn } from 'node:child_process';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { AgentProcess } from '../electron/agent-process';
import { agentFixture } from './ai-fixtures';
vi.mock('node:child_process',()=>({spawn:vi.fn()}));
let child:any;
beforeEach(()=>{
 vi.useFakeTimers();
 child=new EventEmitter();
 child.stdout=Object.assign(new EventEmitter(),{setEncoding:vi.fn()});
 child.stderr=new EventEmitter();
 child.stdin=Object.assign(new EventEmitter(),{write:vi.fn(),end:vi.fn()});
 child.kill=vi.fn(); child.pid=undefined;
 vi.mocked(spawn).mockReturnValue(child);
});
afterEach(()=>{vi.useRealTimers();vi.restoreAllMocks();});
function ready(){const host=new AgentProcess('C:/Test');child.stdout.emit('data','{"ready":true}\n');return host;}
it('reports startup failure distinctly after 30 seconds',async()=>{
 const host=new AgentProcess('C:/Test');
 await vi.advanceTimersByTimeAsync(30000);
 expect(await host.ready).toBe(false);
 expect(await host.request({request_id:'x',method:'get_intelligence_snapshot',params:{}})).toMatchObject({code:'backend_startup_failed'});
});
it('read requests time out visibly and release pending work',async()=>{
 const host=ready();
 const result=host.request({request_id:'x',method:'get_intelligence_snapshot',params:{}});
 await vi.advanceTimersByTimeAsync(30000);
 expect(await result).toMatchObject({code:'backend_timeout'});
 expect(host.alive).toBe(false);
});
it('permits synchronous inference longer than the old budget and clears response timer',async()=>{
 const host=ready();
 const result=host.request({request_id:'x',method:'request_agent_execution',params:{prompt:'Explain'}});
 await vi.advanceTimersByTimeAsync(70000);
 expect(host.alive).toBe(true);
 child.stdout.emit('data',JSON.stringify(agentFixture('x'))+'\n');
 expect(await result).toMatchObject({kind:'backend',response:{request_id:'x'}});
 await vi.advanceTimersByTimeAsync(900000);
 expect(host.alive).toBe(true);
});