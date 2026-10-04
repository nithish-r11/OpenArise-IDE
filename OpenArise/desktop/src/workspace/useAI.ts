import { useEffect, useMemo, useRef, useState } from 'react';
import { BackendClient } from '../backend/client';
import type { Project } from '../types/project';
import type { AIHistoryItem, AIRequest, AIResult } from '../types/ai';
import type { ClientResult, JsonObject } from '../types/backend';
import { validAgentEnvelope } from '../../shared/agent-response';
export function useAI(project?: Project) {
  const client = useMemo(() => new BackendClient(window.openarise, project?.id), [project?.id]);
  const [prompt, setPrompt] = useState('');
  const [items, setItems] = useState<AIHistoryItem[]>([]);
  const [selected, setSelected] = useState('');
  const [busy, setBusy] = useState(false);
  const [commandInFlight, setCommandInFlight] = useState<{ requestId: string; kind: 'allow' | 'deny' | 'cancel' | 'refresh'; stage: string }>();
  const [context, setContext] = useState<JsonObject | null>(null);
  const [environment, setEnvironment] = useState<JsonObject | null>(null);
  const [error, setError] = useState('');
  const lock = useRef(false);
  const projectRef = useRef(project?.id); projectRef.current = project?.id;
  const history = useRef(items); history.current = items;
  const current = items.find(i => i.request.requestId === selected && i.request.projectRef?.id === project?.id);
  const pending = items.find(i => i.result?.pending_action);
  const patch = (requestId: string, update: Partial<AIHistoryItem>) => setItems(old => old.map(i => i.request.requestId === requestId ? { ...i, ...update } : i));
  useEffect(() => { setContext(null); setEnvironment(null); setError(''); setSelected(''); }, [project?.id]);
  const loadContext = async () => {
    if (!project || lock.current) return;
    lock.current = true; setBusy(true); setError('');
    const id = project.id;
    try {
      const result = await client.getIntelligence();
      const env = await client.getEnvironment();
      if (projectRef.current !== id) return;
      if (result.kind === 'backend' && result.response.success) setContext(result.response.data as JsonObject);
      else setError('Project context is unavailable. It will be supplied by the backend when a request can run.');
      if (env.kind === 'backend' && env.response.success) setEnvironment(env.response.data as JsonObject);
    } finally { lock.current = false; setBusy(false); }
  };
  const adopt = (requestId: string, result: ClientResult, method: string, commandId: string): AIResult | undefined => {
    if (result.kind !== 'backend' || !validAgentEnvelope(result.response, commandId, method) || !result.response.success) {
      const message = result.kind === 'unavailable' ? result.message : result.kind === 'backend' && !result.response.success
        ? 'Backend rejected this command (' + result.response.error.code + ').' : 'Invalid backend response.';
      patch(requestId, { state: 'backend unavailable', error: message }); setError(message); return;
    }
    const agent = result.response.data as unknown as AIResult;
    if (agent.request_id !== requestId) {
      const message = 'Response request ID did not match.';
      patch(requestId, { state: 'backend unavailable', error: message }); setError(message); return;
    }
    patch(requestId, { result: agent, events: result.response.events, state: agent.status, error: undefined,
      source: result.source === 'backend' || result.source === 'test_fixture' ? result.source : 'unknown',
      ...(agent.pending_action ? { permissionAction: agent.pending_action } : {}) });
    return agent;
  };
  const submit = async (blocked = false) => {
    if (!project || lock.current || pending || !prompt.trim() || blocked) return;
    lock.current = true; setBusy(true); setError('');
    const request: AIRequest = { requestId: crypto.randomUUID(), prompt: prompt.trim(), projectRef: { id: project.id } };
    setItems(old => [...old.slice(-19), { request, timestamp: new Date().toISOString(), state: 'submitting', events: [], source: 'unknown' }]);
    setSelected(request.requestId);
    try {
      const result = await client.submitAIRequest(request);
      if (projectRef.current !== request.projectRef!.id) return;
      const agent = adopt(request.requestId, result, 'request_agent_execution', request.requestId);
      if (agent && agent.status !== 'failure') setPrompt(value => value.trim() === request.prompt ? '' : value);
    } finally { lock.current = false; setBusy(false); }
  };
  const command = async (kind: 'allow' | 'deny' | 'cancel' | 'refresh', blocked = false) => {
    const item = history.current.find(i => i.request.requestId === selected);
    if (!item || item.request.projectRef?.id !== project?.id || lock.current || (kind === 'allow' && (blocked || item.error))) return;
    const action = item.result?.pending_action;
    if (kind !== 'refresh' && !action) return;
    lock.current = true; setBusy(true); setError('');
    const target = item.request.requestId, projectId = project!.id;
    setCommandInFlight({ requestId: target, kind, stage: kind });
    try {
      if (kind === 'refresh') {
        const response = await client.getAgentRequest(target);
        if (projectRef.current !== projectId) return;
        adopt(target, response, 'get_agent_execution', response.kind === 'backend' ? response.response.request_id : '');
        return;
      }
      const method = kind === 'cancel' ? 'cancel_agent_execution' : kind === 'deny' ? 'deny_agent_action' : action!.approved ? 'resume_agent_execution' : 'approve_agent_action';
      const id = crypto.randomUUID();
      const response = kind === 'cancel' ? await client.cancelAgentRequest(target, id) : await client.agentCommand(method as 'approve_agent_action' | 'resume_agent_execution' | 'deny_agent_action', target, action!.tool_call_id, id);
      if (projectRef.current !== projectId) return;
      const agent = adopt(target, response, method, id);
      if (kind === 'allow' && method === 'approve_agent_action' && agent?.status === 'approved' && agent.pending_action?.approved) {
        setCommandInFlight({ requestId: target, kind, stage: 'resume' });
        const resumeId = crypto.randomUUID();
        const resumed = await client.agentCommand('resume_agent_execution', target, action!.tool_call_id, resumeId);
        if (projectRef.current === projectId) adopt(target, resumed, 'resume_agent_execution', resumeId);
      }
    } finally { lock.current = false; setBusy(false); setCommandInFlight(undefined); }
  };
  const visibleItems = items.filter(i => i.request.projectRef?.id === project?.id);
  return { prompt, setPrompt, items: visibleItems, current, selected, setSelected, busy, commandInFlight,
    pending: pending?.request.projectRef?.id === project?.id ? pending : undefined,
    context, environment, error, submit, command, loadContext };
}