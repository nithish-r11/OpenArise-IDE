import type { AIHistoryItem } from '../../types/ai';
export function RecoveryCard({ item }: { item: AIHistoryItem }) {
  const r = item.result;
  if (!r) return null;
  const failure = r.data.failure, recovery = r.data.recovery;
  const attempts = r.data.verification?.report.recovery_attempts;
  const recorded = item.events.some(e => e.event_type === 'recovery_finished' || e.current_state === 'RECOVERING');
  const failedTools = r.data.tool_results.filter(t => t.executed && !t.success);
  if (r.status !== 'failure' && !failure && !recovery && !attempts && !recorded && !failedTools.length) return null;
  const state = item.error ? 'unavailable' : recovery?.status === 'RECOVERED' ? 'completed'
    : recovery && ['BLOCKED', 'PERMISSION_REQUIRED'].includes(recovery.status) ? 'blocked'
    : recovery && ['FAILED', 'ROLLED_BACK'].includes(recovery.status) ? 'failed' : recovery ? ['PLANNING', 'CHECKPOINTING', 'APPLYING', 'RETESTING', 'RETRYING', 'ROLLING_BACK'].includes(recovery.status) ? 'pending' : 'attempted'
    : attempts || recorded ? 'attempted' : 'unavailable';
  return <section className="ai-recovery outcome-card" aria-label="Failure and recovery" data-state={state} data-recovery-status={item.error ? undefined : recovery?.status}>
    <header><span className="eyebrow">FAILURE & RECOVERY</span><span className="outcome-badge">{state === 'completed' ? 'Recovery completed' : !item.error && recovery?.status === 'ROLLED_BACK' ? 'Recovery rolled back' : 'Recovery ' + state}</span></header>
    {item.error && <p>These are earlier returned details; the current recovery state is unavailable.</p>}
    <p>{failure?.summary ?? (r.status === 'failure' ? r.message : 'A recovery observation was returned.')}</p>
    <dl className="outcome-facts"><div><dt>Category</dt><dd>{failure?.category ?? 'Not reported'}</dd></div><div><dt>Severity</dt><dd>{failure?.severity ?? 'Not reported'}</dd></div><div><dt>Diagnosis / root cause</dt><dd>{failure?.root_cause ?? 'No diagnosis was returned.'}</dd></div></dl>
    {failedTools.map((t, i) => <p key={i}>{t.resolved_by ? 'Historical failure resolved by the returned recovery retest: ' : ''}{t.tool_name} failed{t.exit_code !== null ? ' · exit ' + t.exit_code : ''}. Tool {t.tool_call_id ?? 'ID withheld'}.</p>)}
    {recovery ? <><p>Backend recovery state: <b>{recovery.status}</b></p><p>{recovery.final_result}</p><p>{recovery.attempts} attempt(s) reported.</p>
      {recovery.tests_run.length > 0 ? <><h4>Retry / retest evidence returned</h4><ul>{recovery.tests_run.map((test, i) => <li key={i}>{test}</li>)}</ul></> : <p>Retry / retest details were not returned.</p>}
      <small>Recovery completion does not establish verified completion.</small></>
      : <><p>{state === 'attempted' ? (attempts !== undefined ? attempts + ' recovery attempt(s) reported. ' : '') + 'A recorded recovery attempt has no separately returned outcome.' : 'Recovery details are unavailable in this response.'}</p><p>Retry / retest state was not returned. No recovery success is assumed.</p></>}
  </section>;
}
