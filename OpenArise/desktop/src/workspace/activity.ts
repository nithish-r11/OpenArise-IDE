import type { AIHistoryItem } from '../types/ai';
import type { ActivityEvent, ActivityPresentation, ActivityState } from '../types/activity';
import { completionPresentation } from './completion';
const states: Record<string, ActivityState> = { IDLE: 'idle', THINKING: 'running', PLANNING: 'running', EXECUTING: 'running', OBSERVING: 'running', FAILED: 'failure', RECOVERING: 'recovering', RETESTING: 'retesting', VERIFYING: 'verifying', COMPLETED: 'completed', PERMISSION_REQUIRED: 'waiting_for_permission', APPROVED: 'waiting_for_permission', DENIED: 'denied', CANCELLED: 'cancelled' };
const titles: Record<string, string> = { state_changed: 'State returned', tool_started: 'Tool started', tool_finished: 'Tool finished', permission_required: 'Permission required', permission_approved: 'Permission approved', recovery_finished: 'Recovery attempt finished (outcome not supplied)' };
const tools = new Set(['read_file', 'write_file', 'execute_python', 'execute_tests', 'execute_project_tests', 'build_project', 'unregistered_tool']);
const id = (s: unknown): string | undefined => typeof s === 'string' && /^[A-Za-z0-9_-]{1,128}$/.test(s) ? s : undefined;
const stamp = (s: string) => s.length <= 40 && !Number.isNaN(Date.parse(s)) ? s : 'Timestamp unavailable';
/** Presents explicit returned fields; elapsed time never produces agent activity. */
export function activityPresentation(item?: AIHistoryItem): ActivityPresentation {
  if (!item) return { state: 'idle', provenance: 'UNAVAILABLE_ACTIVITY', label: 'Idle', detail: 'No request selected. No agent activity reported.', verified: false, events: [], dataSource: 'unknown' };
  const result = item.result, requestId = id(item.request.requestId), dataSource = item.source ?? 'unknown';
  const lastRecoveryEvent = [...item.events].reverse().find(e => e.event_type === 'recovery_finished');
  const events: ActivityEvent[] = item.events.slice(-200).filter(e => e.request_id === item.request.requestId && titles[e.event_type]).map(e => {
    const tool = result?.data.tool_results.find(t => t.tool_call_id === e.tool_call_id);
    const state = states[e.current_state] ?? 'unavailable';
    return { eventId: e.request_id + ':' + e.sequence, requestId: requestId ?? 'ID withheld', timestamp: stamp(e.timestamp),
      state, title: e === lastRecoveryEvent && result?.data.recovery && Date.parse(e.timestamp) >= Date.parse(result.data.recovery.timestamp) ? 'Recovery attempt returned: ' + result.data.recovery.status : titles[e.event_type], detail: states[e.current_state] ? 'Recorded ' + (dataSource === 'test_fixture' ? 'fixture' : 'backend') + ' state: ' + e.current_state : 'Backend state unavailable.',
      toolId: id(e.tool_call_id), toolName: tool && tools.has(tool.tool_name) ? tool.tool_name : undefined,
      outcome: e.event_type === 'tool_finished' && tool ? tool.executed ? tool.success ? 'Tool succeeded' : 'Tool failed' : 'Not executed' : 'Outcome not supplied',
      provenance: 'RECORDED_ACTIVITY' };
  });
  if (item.state === 'submitting') return { state: 'submitting', provenance: 'UNAVAILABLE_ACTIVITY', label: 'Waiting for a response', detail: 'Local request sent. Waiting for the synchronous response; agent activity is unavailable.', requestId, verified: false, events, dataSource };
  if (item.error || item.state === 'backend unavailable' || !result) return { state: 'unavailable', provenance: 'UNAVAILABLE_ACTIVITY', label: 'Activity unavailable', detail: 'No current backend state is available. Any history below contains earlier returned observations.', requestId, verified: false, events, dataSource };
  const completion = completionPresentation(item), verified = completion.state === 'verified';
  const status: Record<string, ActivityState> = { success: verified ? 'completed' : completion.state === 'failed' ? 'failure' : 'unverified', unverified: completion.state === 'failed' ? 'failure' : 'unverified', failure: 'failure', permission_required: 'waiting_for_permission', approved: 'waiting_for_permission', denied: 'denied', cancelled: 'cancelled' };
  const state = status[result.status] ?? 'unavailable';
  const answerOnly = state === 'unverified' && !result.pending_action && result.data.tool_results.length === 0 && !!result.data.model_response;
  const labels: Record<ActivityState, string> = { idle: 'Idle', submitting: 'Submitting', running: 'Running', waiting_for_permission: result.status === 'approved' ? 'Approved · ready to resume' : 'Waiting for permission', failure: 'Failed', recovering: 'Recovering', retesting: 'Retesting', verifying: 'Verifying', completed: 'Completed · verified', unverified: 'Unverified', denied: 'Denied', cancelled: 'Cancelled', unavailable: 'Activity unavailable' };
  return { state, provenance: state === 'unavailable' ? 'UNAVAILABLE_ACTIVITY' : 'ACTUAL_STATE', label: answerOnly ? 'Answer returned' : labels[state],
    detail: answerOnly ? 'Read-only answer returned. It does not establish execution or test verification.' : state === 'completed' ? 'CompletionGate returned VERIFIED.' : state === 'unverified' ? 'Completion has not been verified. Dispatch or tool success is not verification.' : 'Last backend response: ' + (states[result.current_state] ? result.current_state : 'state unavailable') + '. Not a live observation.',
    requestId, verified, events, dataSource };
}
