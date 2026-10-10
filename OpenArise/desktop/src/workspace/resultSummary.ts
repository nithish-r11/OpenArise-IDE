import type { AIHistoryItem } from '../types/ai';
import { completionPresentation } from './completion';
/** Wording only: the existing completion projection remains the authority. */
export function resultSummary(item: AIHistoryItem) {
  const proof = completionPresentation(item), r = item.result;
  if (item.state === 'submitting') return { title: 'Working…', message: '', answer: undefined };
  if (!item.error && r?.status === 'denied') return { title: 'Denied', message: 'Permission denied. The pending action did not run.', answer: undefined };
  if (!item.error && r?.status === 'cancelled') return { title: 'Cancelled', message: 'The pending action was cancelled.', answer: undefined };
  if (!item.error && r?.pending_action) return { title: r.pending_action.approved ? 'Approved' : 'Permission required', message: '', answer: undefined };
  const answer = r?.data.model_response;
  const readonly = !!answer && !r.pending_action && r.data.tool_results.length === 0 && ['success', 'unverified'].includes(r.status) && ['verified', 'unverified'].includes(proof.state);
  if (readonly) return { title: 'Answer', message: '', answer };
  if (proof.state === 'verified') return { title: 'Verified', message: 'The requested work passed verification.', answer };
  if (proof.state === 'failed' && r?.data.recovery?.status === 'ROLLED_BACK')
    return { title: 'Rolled back', message: "Recovery failed. The recovery changes were rolled back; the request remains failed.", answer };
  const title = ({ failed: 'Failed', blocked: 'Blocked', unavailable: 'Unavailable', denied: 'Denied', cancelled: 'Cancelled', pending: 'Waiting for approval', unverified: 'Not verified' } as Record<string, string>)[proof.state] ?? 'Not verified';
  const changed = r?.data.tool_results.some(t => t.tool_name === 'write_file' && t.executed && t.success);
  const message = proof.state === 'unverified' ? changed ? "Changes were made, but I couldn't verify the result." : 'The result has not been verified.'
    : r?.status === 'denied' ? 'Permission denied. The pending action did not run.'
    : r?.status === 'cancelled' ? 'The pending action was cancelled.'
    : proof.state === 'failed' ? r?.data.tool_results.length === 0 ? r.message : 'The action failed. Review the details before retrying.'
    : proof.state === 'blocked' ? 'The action is blocked. Review the permission or verification details.' : '';
  return { title, message, answer };
}
