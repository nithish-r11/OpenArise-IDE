import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within, waitFor } from '@testing-library/react';
import { useEffect } from 'react';
import { useAI } from '../src/workspace/useAI';
import { AIPanel } from '../src/components/AI/AIPanel';
import { validAgentEnvelope } from '../shared/agent-response';
import { agentFixture } from './ai-fixtures';
import intelligence from './fixtures/intelligence.json';
const project = {id:'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',name:'Actual context fixture',rootPath:'C:/Fixture'};
let request: ReturnType<typeof vi.fn>;
function Harness({load=false}: {load?:boolean}) {
 const ai=useAI(project,true);
 useEffect(()=>{if(load) void ai.loadContext();},[load]);
 return <AIPanel ai={ai} project={project} blocked={false} expanded onToggle={()=>{}} />;
}
beforeEach(()=>{
 request=vi.fn(async(r:any)=>({kind:'backend',source:'test_fixture',response:agentFixture(r.request_id)}));
 window.openarise={request} as any;
});
afterEach(()=>{cleanup();delete window.openarise;});
function send(){fireEvent.change(screen.getByLabelText('Ask OpenArise'),{target:{value:'Create multiply code.'}});fireEvent.click(screen.getByRole('button',{name:'Send ↗'}));}
it('defaults desktop to answer-only, sends mode through existing envelope and displays literal model text',async()=>{
 request.mockImplementation(async(r:any)=>{
  const response=agentFixture(r.request_id);
  response.data.data.model_response='def multiply(a, b):\n    return a * b\n<script>unsafe()</script>';
  return {kind:'backend',source:'test_fixture',response};
 });
 render(<Harness/>);send();
 const model=await screen.findByLabelText('Model response');
 expect(model.textContent).toContain('return a * b');
 expect(model.textContent).toContain('<script>');
 expect(model.querySelector('script')).toBeNull();
 expect(request.mock.calls[0][0].params.context_data).toEqual({response_mode:'text_only'});
 expect(screen.getByText('TEST FIXTURE')).toBeTruthy();
 expect(within(screen.getByLabelText('AI result')).getByText('Unverified')).toBeTruthy();
 expect(screen.queryByText('Verified by CompletionGate')).toBeNull();
});
it('requires an explicit mode change to request tools',async()=>{
 render(<Harness/>);
 fireEvent.click(screen.getByRole('button',{name:'Agent actions'}));send();
 await screen.findByText('Recorded backend result.');
 expect(request.mock.calls[0][0].params.context_data).toBeUndefined();
});
it('shows actual safe provider failure reason',async()=>{
 request.mockImplementation(async(r:any)=>{
  const response=agentFixture(r.request_id,'failure');
  response.data.message='Configured Ollama model is not installed. Correct OLLAMA_MODEL.';
  return {kind:'backend',source:'test_fixture',response};
 });
 render(<Harness/>);send();
 await within(screen.getByLabelText('AI result')).findByText(/Configured Ollama model is not installed/);
 expect(screen.queryByText('Verified by CompletionGate')).toBeNull();
});
it('surfaces project context failure and preserves the prompt',async()=>{
 request.mockImplementation(async(r:any)=>({kind:'backend',source:'test_fixture',response:{
  request_id:r.request_id,success:false,data:null,action_state:null,events:[],
  error:{success:false,code:'project_state_unavailable',message:'Project context could not load.',details:{}}
 }}));
 render(<Harness/>);send();
 await waitFor(()=>expect(screen.getAllByText(/Project context could not load/).length).toBeGreaterThan(0));
 expect((screen.getByLabelText('Ask OpenArise') as HTMLTextAreaElement).value).toBe('Create multiply code.');
});
it('loads bounded context and reports configured model availability',async()=>{
 request.mockImplementation(async(r:any)=>({kind:'backend',source:'test_fixture',response:{
  request_id:r.request_id,success:true,error:null,action_state:"completed",events:[],
  data:r.method==='get_environment_status'?intelligence.get_environment_status:{
   ...intelligence.get_intelligence_snapshot,
   ollama:{status:'ready',model:'qwen2.5-coder:7b',message:'Configured model is installed.',timeout_seconds:180}
  }
 }}));
 render(<Harness load/>);
 await screen.findByText('Ollama detected');
 expect(screen.getByLabelText('Ollama availability').textContent).toContain('qwen2.5-coder:7b');
 expect(screen.queryByText('Context not loaded')).toBeNull();
 expect(request.mock.calls.map(([r])=>r.method)).toEqual(['get_intelligence_snapshot','get_environment_status']);
});
it('rejects oversized model text and unknown response properties',()=>{
 const response=agentFixture('x');
 response.data.data.model_response='x'.repeat(8001);
 expect(validAgentEnvelope(response,'x','request_agent_execution')).toBe(false);
 response.data.data.model_response='safe';
 expect(validAgentEnvelope(response,'x','request_agent_execution')).toBe(true);
 (response.data.data as any).raw_response='secret';
 expect(validAgentEnvelope(response,'x','request_agent_execution')).toBe(false);
});
it('disables mode changes and duplicate submission while inference is pending',async()=>{
 request.mockReturnValue(new Promise(()=>{}));
 render(<Harness/>);send();
 expect((screen.getByRole('button',{name:'Answer only'}) as HTMLButtonElement).disabled).toBe(true);
 expect((screen.getByRole('button',{name:'Agent actions'}) as HTMLButtonElement).disabled).toBe(true);
 fireEvent.submit(document.querySelector('.ai-composer')!);
 expect(request).toHaveBeenCalledTimes(1);
});