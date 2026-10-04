import { useLayoutEffect, useRef, useState } from 'react';
import { BackendClient } from '../backend/client';
import { intelligenceChecks } from '../../shared/intelligence-response';
import type { Project } from '../types/project';
import type { ClientResult } from '../types/backend';
import type { DriftFinding, IntelligenceBundle } from '../types/intelligence';
export type SourceState = 'loading' | 'ready' | 'error' | 'unavailable';
export type IntelligenceState = { data: Partial<IntelligenceBundle>; states: Partial<Record<keyof IntelligenceBundle, SourceState>>; message: string };
export function useIntelligence(project: Project | null | undefined) {
  const [state, setState] = useState<IntelligenceState>({ data: {}, states: {}, message: '' });
  const [busy, setBusy] = useState(false);
  const [baselines, setBaselines] = useState<string[]>([]);
  const [findings, setFindings] = useState<Record<string, DriftFinding>>({});
  const [actionMessage, setActionMessage] = useState('');
  const generation = useRef(0), locked = useRef(false);
  const current = useRef(project?.id); current.current = project?.id;
  useLayoutEffect(() => { generation.current++; locked.current = false; setBusy(false); setState({ data: {}, states: {}, message: '' }); setBaselines([]); setFindings({}); setActionMessage(''); }, [project?.id]);
  const refresh = async () => {
    if (!project || locked.current) return;
    const id = project.id, token = generation.current; locked.current = true; setBusy(true);
    const valid = () => current.current === id && generation.current === token;
    const client = new BackendClient(window.openarise, id);
    const reads = { info: () => client.getProjectInfo(), state: () => client.getProjectState(), requirements: () => client.getRequirements(), blueprint: () => client.getBlueprint(), graph: () => client.getTraceability(), environment: () => client.getEnvironment(), health: () => client.getHealth(), snapshot: () => client.getIntelligence(), timeline: () => client.getTimeline() };
    const methods = { info: 'get_project_information', state: 'get_project_state', requirements: 'get_requirements', blueprint: 'get_blueprint', graph: 'get_traceability_graph', environment: 'get_environment_status', health: 'get_health_report', snapshot: 'get_intelligence_snapshot', timeline: 'get_timeline' };
    setState({ data: {}, states: Object.fromEntries(Object.keys(reads).map(k => [k, 'loading'])), message: '' });
    try {
      const fresh = await client.refreshWorkspace();
      if (!valid()) return;
      if (fresh.kind !== 'backend' || !fresh.response.success) {
        setState({ data: {}, states: Object.fromEntries(Object.keys(reads).map(k => [k, fresh.kind === 'unavailable' ? 'unavailable' : 'error'])), message: 'Project intelligence could not be refreshed. Retry when the backend is available.' }); return;
      }
      for (const key of Object.keys(reads) as (keyof IntelligenceBundle)[]) {
        const result = await reads[key]();
        if (!valid()) return;
        const ready = result.kind === 'backend' && result.response.success && intelligenceChecks[methods[key]](result.response.data);
        setState(s => ({ ...s, states: { ...s.states, [key]: ready ? 'ready' : result.kind === 'unavailable' ? 'unavailable' : 'error' }, data: ready && result.kind === 'backend' ? { ...s.data, [key]: result.response.data } : s.data }));
      }
    } finally { if (valid()) { locked.current = false; setBusy(false); } }
  };
  const baselineAction = async (requirementId: string, compare = false) => {
    if (!project || locked.current) return;
    const id = project.id, token = generation.current; locked.current = true; setBusy(true); setActionMessage('');
    const client = new BackendClient(window.openarise, id);
    try {
      const result: ClientResult = compare ? await client.getDrift({ requirement_id: requirementId }) : await client.captureBaseline(requirementId);
      if (current.current !== id || generation.current !== token) return;
      const method = compare ? 'get_drift_report' : 'create_requirement_baseline';
      if (result.kind !== 'backend' || !result.response.success || !intelligenceChecks[method](result.response.data)) { setActionMessage('Baseline action unavailable or failed. Capture a new baseline if the backend session restarted.'); return; }
      if (compare) {
        setFindings(f => ({ ...f, [requirementId]: result.response.data as unknown as DriftFinding }));
        // Read the backend's recorded comparison/event without refreshing away its drift cache.
        for (const key of ['snapshot', 'timeline'] as const) {
          const method = key === 'snapshot' ? 'get_intelligence_snapshot' : 'get_timeline';
          const updated = await (key === 'snapshot' ? client.getIntelligence() : client.getTimeline());
          if (current.current !== id || generation.current !== token) return;
          const ready = updated.kind === 'backend' && updated.response.success && intelligenceChecks[method](updated.response.data);
          setState(s => ({ ...s, states: { ...s.states, [key]: ready ? 'ready' : updated.kind === 'unavailable' ? 'unavailable' : 'error' }, data: ready && updated.kind === 'backend' ? { ...s.data, [key]: updated.response.data } : s.data }));
        }
      }
      else { setBaselines(b => [...new Set([...b, requirementId])]); setFindings(f => { const next = { ...f }; delete next[requirementId]; return next; }); setActionMessage('Baseline captured for ' + requirementId + '. Compare after saved changes.'); }
    } finally { if (current.current === id && generation.current === token) { locked.current = false; setBusy(false); } }
  };
  return { ...state, busy, refresh, baselines, findings, actionMessage, baselineAction };
}
export type IntelligenceController = ReturnType<typeof useIntelligence>;
