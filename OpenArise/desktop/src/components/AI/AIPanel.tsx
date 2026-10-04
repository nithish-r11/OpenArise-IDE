import '../../styles/outcomes.css';
import { useEffect, useRef } from 'react';
import type { Project } from '../../types/project';
import type { useAI } from '../../workspace/useAI';
import { OrbitMark } from '../Icon';
import { AriseActivityVisualizer } from '../Activity/AriseActivityVisualizer';
import { activityPresentation } from '../../workspace/activity';
import { completionPresentation } from '../../workspace/completion';
import { PermissionCard } from './PermissionCard';
import { RecoveryCard } from './RecoveryCard';
import { VerificationCard } from './VerificationCard';
const label: Record<string, string> = {
  success: 'Verified', unverified: 'Unverified', failure: 'Failed', permission_required: 'Waiting for approval',
  approved: 'Approved — ready to resume', denied: 'Denied', cancelled: 'Cancelled', submitting: 'Submitting',
};
export function AIPanel({ ai, project, blocked, expanded, onToggle }: {
  ai: ReturnType<typeof useAI>; project?: Project; blocked: boolean; expanded: boolean; onToggle: () => void;
}) {
  const current = ai.current, result = current?.result;
  const completion = completionPresentation(current);
  const conversation = useRef<HTMLDivElement>(null);
  useEffect(() => { if (!result?.pending_action && conversation.current) conversation.current.scrollTop = 0; }, [current?.state, result?.status]);
  const summary = ai.context?.intelligence_summary;
  const facts = summary && typeof summary === 'object' && !Array.isArray(summary) ? summary : null;
  return <aside className={'ai-workspace' + (expanded ? ' ai-expanded' : '')} aria-label="AI workspace">
    <div className="panel-heading"><button className="ai-toggle" aria-label="Toggle AI workspace" onClick={onToggle}>OpenArise AI <span>✧</span></button></div>
    <div className="ai-content">
      <div className="ai-context"><span className="eyebrow">PROJECT CONTEXT</span><strong>{project?.name ?? 'No project selected'}</strong>
        <p>{facts ? <>{String(facts.total_files ?? 'Unknown')} files · {String(facts.requirements_count ?? 'Unknown')} requirements<br />{String(facts.health_issues ?? 'Unknown')} health findings · {String(facts.traceability_nodes ?? 'Unknown')} traceability nodes</> : 'Context not loaded'}</p>
        {ai.environment && <p>Backend Python {String(ai.environment.python_version ?? 'unavailable')} · {ai.environment.python_available ? 'available' : 'unavailable'}<br />{ai.environment.virtualenv_present ? ai.environment.virtualenv_usable ? 'Project environment detected' : 'Project environment unavailable' : 'No project environment'}<br /><small>Observation scope: {String(ai.environment.inspection_scope)}</small></p>}
        <button disabled={!project || ai.busy} onClick={() => void ai.loadContext()}>Refresh context</button>
      </div>
      {current && <div className={'ai-data-source source-' + (current.source ?? 'unknown')} aria-label="AI data source">
        <b>{current.source === 'test_fixture' ? 'TEST FIXTURE' : current.source === 'backend' ? 'BACKEND RESPONSE' : 'SOURCE NOT REPORTED'}</b>
        <span>{current.source === 'test_fixture' ? 'Mocked UI validation · no live AI validation' : current.source === 'backend' ? 'Last returned data · no live streaming' : 'No live backend claim can be made.'}</span>
      </div>}
      <div className="ai-conversation" ref={conversation}>
        <AriseActivityVisualizer key={current?.request.requestId ?? 'idle'} activity={activityPresentation(current)} />
        {!current ? <div className="ai-empty"><OrbitMark large /><h2>What shall we build?</h2><p>Describe a focused change. OpenArise will use the selected project's factual context.</p><small>Actions that need permission will wait for you.</small></div> : <>
          <article className="ai-request"><span className="eyebrow">YOUR REQUEST</span><p>{current.request.prompt}</p><button className="reuse-prompt" disabled={ai.busy} onClick={() => ai.setPrompt(current.request.prompt)}>Reuse prompt</button><small title={current.request.requestId}>{current.timestamp} · {current.request.requestId}</small></article>
          <PermissionCard item={current} busy={ai.busy} blocked={blocked} command={ai.command} inFlight={ai.commandInFlight} />
          <article className={'ai-result state-' + current.state.replaceAll(' ', '-')} aria-label="AI result">
            <strong>{['success', 'unverified'].includes(current.state) ? completion.final === 'VERIFIED' ? 'Verified' : completion.final === 'FAILED' ? 'Failed' : completion.final === 'UNAVAILABLE' ? 'Unavailable' : 'Unverified' : label[current.state] ?? current.state}</strong>
            {current.state === 'submitting' && <p>Waiting for the synchronous backend response. Activity will appear when returned; this is not live streaming.</p>}
            {result && <><p>{result.message}</p>{result.status === 'failure' && result.data.tool_results.length === 0 && current.source !== 'test_fixture' && <p>Check that your configured Ollama service and model are available. No AI change was confirmed.</p>}<small>Backend state: {result.current_state}</small></>}
            {current.error && <p role="alert">{current.error}</p>}
            <VerificationCard item={current} />
          </article>
          <RecoveryCard item={current} />
          {!!result?.data.tool_results.length && <details className="ai-tools" open><summary>Tool results</summary>{result.data.tool_results.map((tool, i) => <div key={i}><b>{tool.tool_name} · {tool.executed ? tool.success ? 'Succeeded' : 'Failed' : 'Not executed'}</b><p>{tool.tool_call_id ?? 'ID withheld'}{tool.exit_code !== null ? ' · exit ' + tool.exit_code : ''}</p><small>{tool.timestamp}</small></div>)}</details>}
          {current.state !== 'submitting' && <button className="ai-refresh" disabled={ai.busy} onClick={() => void ai.command('refresh')}>Refresh request result</button>}
        </>}
      </div>
      {ai.items.length > 0 && <div className="ai-history"><label htmlFor="ai-history">Session history</label><select id="ai-history" value={ai.selected} onChange={e => ai.setSelected(e.target.value)}>{ai.items.map(i => <option key={i.request.requestId} value={i.request.requestId}>{i.result && !i.result.pending_action ? completionPresentation(i).final : label[i.state] ?? i.state} · {i.request.prompt.slice(0, 45)}</option>)}</select></div>}
      <form className="ai-composer" onSubmit={event => { event.preventDefault(); void ai.submit(blocked); }}>
        {ai.error && <p className="ai-error" role="alert">{ai.error}</p>}
        {blocked && <p>Save or discard editor changes before AI execution.</p>}
        <label htmlFor="ai-prompt">Ask OpenArise</label>
        <textarea id="ai-prompt" maxLength={12000} rows={3} value={ai.prompt} onChange={event => ai.setPrompt(event.target.value)} placeholder="Describe a change to this project…"
          onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void ai.submit(blocked); } }} />
        <div><span>{ai.busy ? 'Backend command active' : ai.prompt ? 'Draft · Enter to send' : 'Shift + Enter for a new line'}</span><button type="button" disabled={!ai.prompt || ai.busy} onClick={() => ai.setPrompt('')}>Clear</button><button className="ai-submit" disabled={!project || !ai.prompt.trim() || ai.busy || !!ai.pending || blocked}>{ai.busy ? 'Waiting…' : 'Send ↗'}</button></div>
        {ai.busy && <small>Synchronous execution cannot be interrupted here. Pending approval can be cancelled when returned.</small>}
      </form>
    </div>
  </aside>;
}