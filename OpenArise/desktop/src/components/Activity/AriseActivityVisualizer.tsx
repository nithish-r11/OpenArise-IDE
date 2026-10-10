import { useState } from 'react';
import type { ActivityPresentation } from '../../types/activity';
import '../../styles/activity.css';
/** Pure presentation: accepts returned state/history; never polls or synthesizes activity. */
export function AriseActivityVisualizer({ activity, compact = false }: { activity: ActivityPresentation; compact?: boolean }) {
  const [selected, setSelected] = useState<string | null>(null);
  const event = activity.events.find(e => e.eventId === selected);
  const state = event?.state ?? activity.state;
  const provenance = event?.provenance ?? activity.provenance;
  const label = event ? event.title + ' · ' + event.state.replaceAll('_', ' ') : activity.label;
  return <section className={'arise-activity activity-' + state + (event ? ' is-recorded' : '') + (compact ? ' activity-compact' : '')}
    aria-label="Arise Activity Visualizer" data-state={state} data-provenance={provenance} data-source={activity.dataSource}>
    <div className="activity-heading"><span className="eyebrow">ARISE ACTIVITY</span>{!compact && <span className="activity-source">{provenance}</span>}</div>
    {activity.dataSource === 'test_fixture' && <p className="activity-scope">TEST FIXTURE · mocked recorded states; no live AI validation.</p>}
    <div className="activity-summary">
      <div className="activity-orbit" aria-hidden="true"><span className="activity-ring" /><span className="activity-particle-track"><i /></span><span className="activity-symbol">{state === 'completed' ? !event && activity.verified ? '✓' : '■' : state === 'unverified' ? '?' : state === 'failure' ? '!' : state === 'waiting_for_permission' ? 'Ⅱ' : '·'}</span></div>
      <div className="activity-state" role="status" aria-live="polite" aria-atomic="true"><strong>{label}</strong><p>{event?.detail ?? activity.detail}</p>{event && <p>{event.outcome}</p>}</div>
    </div>
    {!compact && <small className="activity-scope">{event ? 'Recorded observation selected. Motion illustrates this historical state only; recorded completion does not establish verification.' : provenance === 'ACTUAL_STATE' ? 'ACTUAL_STATE = last returned result, not live telemetry.' : 'No backend activity is inferred from elapsed time.'}</small>}
    {!compact && activity.requestId && <code className="activity-request-id">Request {activity.requestId}</code>}
    {event && <button className="activity-current" onClick={() => setSelected(null)}>Return to current result</button>}
    {activity.events.length > 0 ? <details className="ai-activity activity-history" open={compact ? undefined : true}><summary>Recorded activity · {activity.events.length} events</summary><p>Returned observations, not live progress.</p>
      {activity.events.length ? <ol aria-label="Recorded activity history">{activity.events.map(e => <li key={e.eventId}>
        <button aria-pressed={e.eventId === selected} onClick={() => setSelected(e.eventId)}>{e.title}</button><span>{e.detail}</span><time dateTime={e.timestamp === 'Timestamp unavailable' ? undefined : e.timestamp}>{e.timestamp}</time>
        {e.toolName && <span>{e.toolName}</span>}{e.toolId && <code>Tool {e.toolId}</code>}<small>{e.outcome}</small>
      </li>)}</ol> : <p>No recorded activity returned.</p>}
    </details> : !compact && <p className="activity-scope">No recorded activity returned.</p>}
  </section>;
}
