import type { AIHistoryItem, PresentationState, VerificationStatus } from '../types/ai';
export const verificationState = (status?: VerificationStatus): PresentationState => status === 'VERIFIED' ? 'verified' : status === 'NOT_VERIFIED' ? 'failed' : status === 'PENDING' ? 'pending' : status ? 'unverified' : 'unavailable';
/** Displays the gate result defensively; it never performs independent verification. */
export function completionPresentation(item?: AIHistoryItem): { state: PresentationState; final: string; reason: string } {
  if (!item || item.error || !item.result) return { state: 'unavailable', final: 'UNAVAILABLE', reason: item?.state === 'submitting' ? 'Waiting for the backend result.' : 'A current backend result is unavailable.' };
  const r = item.result, v = r.data.verification;
  if (r.pending_action || ['permission_required', 'approved', 'denied', 'cancelled'].includes(r.status))
    return { state: 'blocked', final: 'BLOCKED', reason: r.status === 'denied' ? 'The backend denied the pending action.' : r.status === 'cancelled' ? 'The backend cancelled the pending request.' : 'Permission must be resolved before completion.' };
  const resolved = (e: typeof r.data.evidence[number]) => {
    const proof = r.data.evidence.find(p => p.evidence_id === e.resolved_by);
    const recovery = r.data.evidence.find(p => p.evidence_id === e.recovery_evidence);
    return r.data.recovery?.status === 'RECOVERED' && !!proof && !!recovery
      && recovery.evidence_type === 'RECOVERY_RESULT' && recovery.requirement_id === e.requirement_id
      && proof.requirement_id === e.requirement_id && proof.evidence_type === 'TEST_PASS' && proof.strength === 'DIRECT'
      && proof.success === true && proof.exit_code === 0 && !proof.stale && !proof.superseded
      && r.data.tool_results.some(t => t.tool_call_id === proof.tool_call_id && t.executed && t.success && t.exit_code === 0);
  };
  const failedEvidence = r.data.evidence.some(e => !resolved(e) && (e.evidence_type === 'TEST_FAIL' || e.strength === 'CONTRADICTORY' || e.success === false || (e.exit_code !== null && e.exit_code !== 0)));
  if (r.status === 'failure' || r.action_state === 'failed' || r.data.tool_results.some(t => !t.success && !r.data.evidence.some(e => e.tool_call_id === t.tool_call_id && e.resolved_by === t.resolved_by && resolved(e))) || failedEvidence || v?.overall_status === 'NOT_VERIFIED')
    return { state: 'failed', final: 'FAILED', reason: 'Returned failure or contradictory evidence prevents verified completion.' };
  if (!v) return { state: 'unavailable', final: 'UNAVAILABLE', reason: 'The backend did not return a CompletionGate result.' };
  const report = v.report;
  const consistent = report.total_requirements > 0 && report.verified === report.total_requirements
    && report.partially_verified === 0 && report.unverified === 0 && report.inconclusive === 0
    && v.requirement_results.length > 0 && v.remaining_issues.length === 0 && v.requirement_results.every(q => q.status === 'VERIFIED' && q.missing_evidence.length === 0 && q.contradictions.length === 0)
    && !r.data.evidence.some(e => e.stale && !(e.superseded && e.evidence_type === 'TEST_PASS'));
  if (r.status === 'success' && r.current_state === 'COMPLETED' && r.action_state === 'completed' && v.overall_status === 'VERIFIED' && consistent)
    return { state: 'verified', final: 'VERIFIED', reason: 'Verified by CompletionGate' };
  return { state: v.overall_status === 'PENDING' ? 'pending' : 'unverified', final: 'UNVERIFIED', reason: v.overall_status === 'VERIFIED' ? 'The returned action and verification fields disagree; verified completion is withheld.' : 'CompletionGate has not verified this request.' };
}