import '../../styles/outcomes.css';
import { useEffect, useRef } from 'react';
import type { Project } from '../../types/project';
import type { useAI } from '../../workspace/useAI';
import { OrbitMark } from '../Icon';
import { AriseActivityVisualizer } from '../Activity/AriseActivityVisualizer';
import { activityPresentation } from '../../workspace/activity';
import { resultSummary } from '../../workspace/resultSummary';
import { PermissionCard } from './PermissionCard';
import { RecoveryCard } from './RecoveryCard';
import { VerificationCard } from './VerificationCard';
const label: Record<string, string> = {
  success: 'Verified', unverified: 'Unverified', failure: 'Failed', permission_required: 'Waiting for approval',
  approved: 'Approved — ready to resume', denied: 'Denied', cancelled: 'Cancelled', submitting: 'Working…',
};
export function AIPanel({ ai, project, blocked, expanded, onToggle }: {
  ai: ReturnType<typeof useAI>; project?: Project; blocked: boolean; expanded: boolean; onToggle: () => void;
}) {
  const current = ai.current, result = current?.result;
  const simple = current ? resultSummary(current) : undefined;
  const conversation = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const panel = conversation.current;
    if (panel && !result?.pending_action) {
      const activity = panel.querySelector('.arise-activity');
      const finalResult = panel.querySelector('.ai-result');
      if (activity && finalResult) panel.scrollTop = Math.max(0, panel.scrollTop + finalResult.getBoundingClientRect().top - panel.getBoundingClientRect().top - activity.getBoundingClientRect().height - 8);
    }
  }, [current?.state, result?.status]);
  const summary = ai.context?.intelligence_summary;
  const facts = summary && typeof summary === 'object' && !Array.isArray(summary) ? summary : null;
  const provider = ai.context?.ollama;
  const coverage = ai.context?.context_coverage;
  const sampled = coverage && typeof coverage === 'object' && !Array.isArray(coverage) ? coverage : null;
  const ollama = provider && typeof provider === 'object' && !Array.isArray(provider) ? provider : null;
  return <aside className={'ai-workspace' + (expanded ? ' ai-expanded' : '')} aria-label="AI workspace">
    <div className="panel-heading"><button className="ai-toggle" aria-label="Toggle AI workspace" onClick={onToggle}>OpenArise AI <span>✧</span></button></div>
    <div className="ai-content">
      <div className="ai-context"><span className="eyebrow">PROJECT CONTEXT</span><strong>{project?.name ?? 'No project selected'}</strong>
        <p>{facts ? <>{String(facts.total_files ?? 'Unknown')} project files available</> : ai.contextState === 'loading' ? 'Loading project context…' : ai.contextState === 'unavailable' ? 'Project context unavailable' : 'Context not loaded'}</p>
        {ai.contextError && <p role="status">{ai.contextError}</p>}
        <details className="ai-context-details"><summary>Context & connection</summary>
        {facts && <p>{String(facts.total_files ?? 'Unknown')} files · {String(facts.requirements_count ?? 'Unknown')} requirements<br />{String(facts.health_issues ?? 'Unknown')} health findings · {String(facts.traceability_nodes ?? 'Unknown')} traceability nodes</p>}
        {sampled && <p aria-label="Project source context">{String(sampled.sampled_files)} source/config excerpts · {String(sampled.characters)} characters<br /><small>{sampled.truncated ? 'Partial project context · bounded for inference' : 'Source context sampled'}{Number(sampled.unavailable_files) > 0 ? ' · some files unavailable' : ''}. Excerpts stay in the backend. Refresh after saving changes.</small></p>}
        {ollama && <p className="ollama-status" aria-label="Ollama availability"><b>{ollama.status === 'ready' ? 'Ollama detected' : ollama.status === 'model_unavailable' ? 'Configured model unavailable' : 'Ollama unavailable'}</b><br />Model: {String(ollama.model)}<br />{String(ollama.message)}<br /><small>Last availability check · synchronous inference · {String(ollama.timeout_seconds)}s generation timeout</small></p>}
        {ai.environment && <p>Backend Python {String(ai.environment.python_version ?? 'unavailable')} · {ai.environment.python_available ? 'available' : 'unavailable'}<br />{ai.environment.virtualenv_present ? ai.environment.virtualenv_usable ? 'Project environment detected' : 'Project environment unavailable' : 'No project environment'}<br /><small>Observation scope: {String(ai.environment.inspection_scope)}</small></p>}
        <button disabled={!project || ai.busy} onClick={() => void ai.loadContext(true)}>Refresh context</button>
        </details>
      </div>
      {current && current.state !== 'submitting' && <div className={'ai-data-source source-' + (current.source ?? 'unknown')} aria-label="AI data source">
        <b>{current.source === 'test_fixture' ? 'TEST FIXTURE' : current.source === 'backend' ? 'Local AI' : 'SOURCE NOT REPORTED'}</b>
        {current.source !== 'backend' && <span>{current.source === 'test_fixture' ? 'Mocked UI validation · no live AI validation' : 'No live backend claim can be made.'}</span>}
      </div>}
      <div className="ai-conversation" ref={conversation}>
        <AriseActivityVisualizer key={current?.request.requestId ?? 'idle'} activity={activityPresentation(current)} compact />
        {!current ? <div className="ai-empty"><OrbitMark large /><h2>What shall we build?</h2><p>Describe a focused change. OpenArise will use the selected project's factual context.</p><small>Actions that need permission will wait for you.</small></div> : <>
          <article className="ai-request"><span className="eyebrow">YOUR REQUEST</span><p>{current.request.prompt}</p><button className="reuse-prompt" disabled={ai.busy} onClick={() => ai.setPrompt(current.request.prompt)}>Reuse prompt</button></article>
          <PermissionCard item={current} busy={ai.busy} blocked={blocked} command={ai.command} inFlight={ai.commandInFlight} />
          <article className={'ai-result state-' + current.state.replaceAll(' ', '-')} aria-label="AI result">
            <strong>{['success', 'unverified', 'failure'].includes(current.state) ? simple?.title : label[current.state] ?? current.state}</strong>
            {current.state === 'submitting' && <p>Waiting for OpenArise…</p>}
            {simple?.message && <p role={result?.status === 'failure' ? 'alert' : undefined}>{simple.message}</p>}
            {result?.status === 'failure' && result.data.tool_results.length === 0 && current.source !== 'test_fixture' && <p>Check the AI connection under Context & connection, then retry.</p>}
            {current.error && <p role="alert">{current.error}</p>}
            {simple?.answer && <section className="ai-model-response" aria-label="Model response"><pre>{simple.answer}</pre></section>}
            <details className="ai-technical"><summary>Details</summary>
            <small>{current.timestamp} · Request {current.request.requestId}</small>
            {result && <>{simple?.message !== result.message && <p>{result.message}</p>}<small>Backend state: {result.current_state}. Generated text alone does not verify an action.</small></>}
            <VerificationCard item={current} />
          <RecoveryCard item={current} />
          {!!result?.data.tool_results.length && <details className="ai-tools"><summary>Tool results</summary>{result.data.tool_results.map((tool, i) => <div key={i}><b>{tool.tool_name} · {tool.executed ? tool.success ? 'Succeeded' : 'Failed' : 'Not executed'}</b><p>{tool.tool_call_id ?? 'ID withheld'}{tool.exit_code !== null ? ' · exit ' + tool.exit_code : ''}</p><small>{tool.timestamp}</small></div>)}</details>}
          {current.state !== 'submitting' && <button className="ai-refresh" disabled={ai.busy} onClick={() => void ai.command('refresh')}>Refresh request result</button>}
          </details></article>
        </>}
      </div>
      {ai.items.length > 0 && <div className="ai-history"><label htmlFor="ai-history">Session history</label><select id="ai-history" value={ai.selected} onChange={e => ai.setSelected(e.target.value)}>{ai.items.map(i => <option key={i.request.requestId} value={i.request.requestId}>{i.result && !i.result.pending_action ? resultSummary(i).title : label[i.state] ?? i.state} · {i.request.prompt.slice(0, 45)}</option>)}</select></div>}
      <form className="ai-composer" onSubmit={event => { event.preventDefault(); void ai.submit(blocked); }}>
        {ai.error && <p className="ai-error" role="alert">{ai.error}</p>}
        {blocked && <p>Save or discard editor changes before AI execution.</p>}
        <div className="ai-composer-heading"><label htmlFor="ai-prompt">Ask OpenArise</label><div className="ai-mode" role="group" aria-label="Request mode"><button type="button" aria-pressed={ai.mode === 'text_only'} disabled={ai.busy || !!ai.pending} onClick={() => ai.setMode('text_only')} title="Display an answer without tools">Answer only</button><button type="button" aria-pressed={ai.mode === 'agent_actions'} disabled={ai.busy || !!ai.pending} onClick={() => ai.setMode('agent_actions')} title="Edit files and run project commands with approval">Make changes</button></div></div>
        <textarea id="ai-prompt" maxLength={12000} rows={3} value={ai.prompt} onChange={event => ai.setPrompt(event.target.value)} placeholder="Describe a change to this project…"
          onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void ai.submit(blocked); } }} />
        <div><span>{ai.busy ? 'Backend command active' : ai.prompt ? 'Draft · Enter to send' : 'Shift + Enter for a new line'}</span><button type="button" disabled={!ai.prompt || ai.busy} onClick={() => ai.setPrompt('')}>Clear</button><button className="ai-submit" disabled={!project || !ai.prompt.trim() || ai.busy || !!ai.pending || blocked}>{ai.busy ? 'Waiting…' : 'Send ↗'}</button></div>
        {ai.busy && <small>Waiting for the current action. You can cancel at the next permission request.</small>}
      </form>
    </div>
  </aside>;
}
