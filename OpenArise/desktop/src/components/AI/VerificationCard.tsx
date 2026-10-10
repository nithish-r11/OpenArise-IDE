import type { AIHistoryItem } from '../../types/ai';
import { completionPresentation, verificationState } from '../../workspace/completion';
export function VerificationCard({ item }: { item: AIHistoryItem }) {
  const result = item.result, v = result?.data.verification, completion = completionPresentation(item);
  const state = item.error ? 'unavailable' : v ? v.overall_status === 'VERIFIED' && completion.state !== 'verified' ? completion.state : verificationState(v.overall_status)
    : item.state === 'submitting' || result?.pending_action ? 'pending' : 'unavailable';
  const tests = result?.data.tool_results.filter(t => ['execute_tests', 'execute_project_tests'].includes(t.tool_name)) ?? [];
  const builds = result?.data.tool_results.filter(t => t.tool_name === 'build_project') ?? [];
  return <section className="ai-verification outcome-card" aria-label="Verification and evidence" data-state={state} data-verification-status={item.error ? undefined : v?.overall_status}>
    <header><span className="eyebrow">VERIFICATION</span><span className="outcome-badge">{item.error ? 'UNAVAILABLE' : v?.overall_status ?? state}</span></header>
    <div className={'ai-completion completion-' + completion.state} aria-label="Final completion state" data-state={completion.state} role="status" aria-live="polite">
      <span className="eyebrow">FINAL RESULT</span><strong>{completion.final}</strong><p>{completion.reason}</p>
    </div>
    {item.error && v && <p>Earlier verification details are retained below. The current result is unavailable.</p>}
    {result && <dl className="outcome-facts" aria-label="Returned backend states"><div><dt>{item.error ? 'Earlier backend state' : 'Backend state'}</dt><dd>{result.current_state}</dd></div><div><dt>{item.error ? 'Earlier action state' : 'Action state'}</dt><dd>{result.action_state}</dd></div></dl>}
    <p>CompletionGate result: <b>{v?.overall_status ?? 'Not returned'}</b></p>
    {!v ? <p>{state === 'pending' ? 'Verification is pending. No evidence-backed completion has been returned.' : 'Verification and coverage details are unavailable.'}</p> : <>
      <div className="verification-metrics"><div><b>{v.report.verified} / {v.report.total_requirements}</b><span>requirements verified</span></div><div><b>{v.report.evidence_count}</b><span>evidence records</span></div><div><b>{v.report.tests_executed}</b><span>test executions</span></div></div>
      <p>{v.report.partially_verified} partially verified · {v.report.unverified} not verified · {v.report.inconclusive} inconclusive</p>
      <small>Test executions are backend test-tool calls, not passing test cases. Test case counts are not supplied.</small>
      <details className="verification-detail"><summary>Tests performed</summary>
        {tests.length ? tests.map((t, i) => <p key={i}>{t.tool_call_id ?? 'ID withheld'} · {t.executed ? t.success ? 'Passed execution' : 'Failed execution' : 'Not executed'}{t.exit_code !== null ? ' · exit ' + t.exit_code : ''}</p>) : <p>No test-tool details were returned.</p>}
      </details>
      {!!builds.length && <details className="verification-detail"><summary>Builds performed</summary>{builds.map((t, i) => <p key={i}>{t.tool_call_id ?? 'ID withheld'} · {t.executed ? t.success ? 'Passed build' : 'Failed build' : 'Not executed'} · exit {t.exit_code ?? 'unavailable'}</p>)}<small>Build evidence does not mean tests ran.</small></details>}
      <details className="verification-detail" open><summary>Requirement coverage</summary>
        {v.requirement_results.length ? v.requirement_results.map(q => <article className="verification-row" key={q.requirement_id}>
          <b>{result?.data.requirements.find(r => r.requirement_id === q.requirement_id)?.title ?? q.requirement_id}</b><span className="outcome-badge">{verificationState(q.status)}</span>
          <small>{q.requirement_id} · {q.status} · {q.confidence} confidence</small><p>{q.explanation}</p>
          {!!q.evidence_used.length && <p>Evidence used: {q.evidence_used.join(', ')}</p>}
          {!!q.missing_evidence.length && <><h4>Missing / stale / invalid evidence</h4><ul>{q.missing_evidence.map((e, i) => <li key={i}>{e}</li>)}</ul></>}
          {!!q.contradictions.length && <p className="evidence-failed">Failed / contradictory evidence: {q.contradictions.join(', ')}</p>}
        </article>) : <p>Requirement-level results were not returned.</p>}
      </details>
      <details className="verification-detail"><summary>Evidence summary · {result?.data.evidence.length ?? 0} displayed</summary>
        {result?.data.evidence.length ? result.data.evidence.map(e => <article className="verification-row" key={e.evidence_id}>
          <b>{e.evidence_type} · {e.strength}</b><small>{e.evidence_id} · requirement {e.requirement_id}</small><p>{e.summary}</p>
          {e.stale && <span className="evidence-stale">Stale evidence{e.superseded ? ' · superseded' : ''}</span>}
          {(e.evidence_type === 'TEST_FAIL' || e.strength === 'CONTRADICTORY' || e.success === false || e.exit_code !== null && e.exit_code !== 0) && <span className="evidence-failed">Failed / contradictory evidence</span>}
          <small>{e.timestamp}</small>
        </article>) : <p>No evidence records were returned.</p>}
      </details>
      {!!v.remaining_issues.length && <><h4>CompletionGate remaining issues</h4><ul>{v.remaining_issues.map((issue, i) => <li key={i}>{issue}</li>)}</ul></>}
      {(v.truncated || result?.data.truncated) && <p className="outcome-partial">Partial presentation: bounded records are displayed; totals belong to the backend.</p>}
      <small>Verification returned at {v.timestamp}. Refresh the request to retrieve its latest retained result.</small>
    </>}
  </section>;
}
