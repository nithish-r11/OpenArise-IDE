import { useEffect, useRef } from 'react';
import type { AIHistoryItem } from '../../types/ai';
import type { useAI } from '../../workspace/useAI';
export function PermissionCard({ item, busy, blocked, command, inFlight }: {
  item: AIHistoryItem; busy: boolean; blocked: boolean; command: ReturnType<typeof useAI>['command']; inFlight: ReturnType<typeof useAI>['commandInFlight'];
}) {
  const ref = useRef<HTMLElement>(null);
  const action = item.result?.pending_action ?? item.permissionAction;
  const pending = !!item.result?.pending_action;
  const active = inFlight?.requestId === item.request.requestId ? inFlight : undefined;
  useEffect(() => { if (pending) ref.current?.scrollIntoView?.({ block: 'nearest' }); }, [pending, action?.tool_call_id]);
  if (!action) return null;
  const state = active ? 'pending' : item.error ? 'unavailable' : pending ? action.approved ? 'approved' : 'permission_required'
    : item.result?.status === 'denied' ? 'denied' : item.result?.status === 'cancelled' ? 'cancelled' : item.result?.action_state === 'failed' ? 'failed' : 'completed';
  const names: Record<string, string> = { pending: 'Pending decision', permission_required: 'Permission required', approved: 'Approved · ready to resume', unavailable: 'State unavailable', denied: 'Denied', cancelled: 'Cancelled', failed: 'Action failed', completed: 'Action completed' };
  const reasons = { WRITE: 'Allow OpenArise to change this file?', EXECUTE: 'Allow this project command to run?', READ: 'Allow OpenArise to read this file?' };
  const tools: Record<string, string> = { write_file: 'Save file', read_file: 'Read file', execute_python: 'Run Python', execute_tests: 'Run pytest', execute_project_tests: 'Run npm tests', build_project: 'Build project' };
  const commandUnavailable = ['execute_project_tests', 'build_project'].includes(action.tool_name) && !action.command;
  return <section ref={ref} className="ai-permission outcome-card" aria-label="Permission request" data-state={state} aria-busy={!!active}>
    <header><span className="eyebrow">PERMISSION</span><span className="outcome-badge">{names[state]}</span></header>
    <strong>{pending ? 'OpenArise needs permission' : 'Permission decision returned'}</strong>
    <p>{tools[action.tool_name] ?? 'Project action'}</p>
    <p>{reasons[action.risk_level]}</p>
    <dl className="outcome-facts"><div><dt>Scope</dt><dd>{action.resource ?? 'Selected project · exact resource not reported'}</dd></div></dl>
    {action.command && <div className="permission-script"><b>{action.command.label}</b><pre>{action.command.script}</pre><small>Reviewed script preview. Runs project code with your user privileges; pre/post hooks are disabled.</small></div>}
    {commandUnavailable && <p role="alert">The manifest changed or this command is unavailable. Cancel and submit a new request before running it.</p>}
    <details><summary>Action details</summary><p>{action.risk_level} · {action.tool_name}</p><small>Tool ID: {action.tool_call_id}</small></details>
    {active && <p role="status">{active.stage === 'resume' ? 'Approval returned. Waiting for the backend to resume the retained action.' : 'Waiting for the backend to confirm ' + active.kind + '.'}</p>}
    {item.error && <p role="alert">The last decision is unconfirmed. Refresh the request before allowing execution.</p>}
    {pending ? <><p>Allow runs this retained action. Deny or Cancel stops pending work; earlier changes are retained.</p>
      {blocked && <p>Save or discard editor changes before allowing execution.</p>}
      <div className="permission-actions"><button disabled={busy || blocked || !!item.error || commandUnavailable} onClick={() => void command('allow', blocked)}>{action.approved ? 'Resume' : 'Allow'}</button><button disabled={busy} onClick={() => void command('deny')}>Deny</button><button disabled={busy} onClick={() => void command('cancel')}>Cancel</button></div></>
      : <p>{state === 'denied' ? 'The backend denied this action.' : state === 'cancelled' ? 'The backend cancelled the pending request.' : 'The backend returned a final action state. Verification is shown separately.'}</p>}
  </section>;
}
