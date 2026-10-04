import { afterEach, expect, it } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { readFileSync } from 'node:fs';
import { AriseActivityVisualizer } from '../src/components/Activity/AriseActivityVisualizer';
import { activityPresentation } from '../src/workspace/activity';
import type { AIHistoryItem } from '../src/types/ai';
import { agentFixture, stamp } from './ai-fixtures';
const item = (status: Parameters<typeof agentFixture>[1] = 'unverified'): AIHistoryItem => {
  const r = agentFixture('req-1', status);
  return { request: { requestId: 'req-1', prompt: 'Private request' }, timestamp: stamp, state: status!, result: r.data as any, events: r.events };
};
afterEach(cleanup);
it('renders idle with explicit unavailable activity and accessible text', () => { render(<AriseActivityVisualizer activity={activityPresentation()} />); expect(screen.getByText('Idle')).toBeTruthy(); expect(screen.getByText('UNAVAILABLE_ACTIVITY')).toBeTruthy(); expect(screen.getByRole('status').getAttribute('aria-live')).toBe('polite'); expect(document.querySelector('.activity-orbit')?.getAttribute('aria-hidden')).toBe('true'); });
it('submitting describes local transport and invents no lifecycle or progress', () => { const i = item(); i.state = 'submitting'; i.result = undefined; i.events = []; const p = activityPresentation(i); render(<AriseActivityVisualizer activity={p} />); expect(p.state).toBe('submitting'); expect(p.provenance).toBe('UNAVAILABLE_ACTIVITY'); expect(p.events).toEqual([]); expect(screen.queryByText(/Thinking|Planning|Running/)).toBeNull(); expect(screen.queryByRole('progressbar')).toBeNull(); });
it.each([['permission_required', 'waiting_for_permission'], ['approved', 'waiting_for_permission'], ['failure', 'failure'], ['success', 'completed'], ['unverified', 'unverified'], ['denied', 'denied'], ['cancelled', 'cancelled']] as const)('preserves returned %s as %s', (status, state) => {
  const p = activityPresentation(item(status)); render(<AriseActivityVisualizer activity={p} />);
  expect(document.querySelector('.arise-activity')?.getAttribute('data-state')).toBe(state); expect(p.provenance).toBe('ACTUAL_STATE'); expect(p.verified).toBe(status === 'success');
});
it.each([['EXECUTING', 'running'], ['RECOVERING', 'recovering'], ['VERIFYING', 'verifying'], ['COMPLETED', 'completed'], ['NEW_STATE', 'unavailable']] as const)('presents returned %s only as recorded activity', (state, visual) => {
  const i = item(); i.events[0].current_state = state; const p = activityPresentation(i);
  render(<AriseActivityVisualizer activity={p} />); fireEvent.click(screen.getByRole('button', { name: 'State returned' }));
  expect(document.querySelector('.arise-activity')?.getAttribute('data-state')).toBe(visual); expect(document.querySelector('.arise-activity')?.getAttribute('data-provenance')).toBe('RECORDED_ACTIVITY');
  expect(screen.getByText(/historical state only/)).toBeTruthy(); expect(document.querySelector('.activity-symbol')?.textContent).not.toBe('✓');
  fireEvent.click(screen.getByRole('button', { name: 'Return to current result' })); expect(document.querySelector('.arise-activity')?.getAttribute('data-state')).toBe('unverified');
});
it('does not turn dispatch success without CompletionGate verification into verified completion', () => { const i = item('success'); i.result!.data.verification!.overall_status = 'INCONCLUSIVE'; expect(activityPresentation(i)).toMatchObject({ state: 'unverified', verified: false }); });
it('keeps explicit unverified even with contradictory verification metadata', () => { const i = item(); i.result!.data.verification!.overall_status = 'VERIFIED'; expect(activityPresentation(i)).toMatchObject({ state: 'unverified', verified: false }); });
it('unavailable takes priority over an earlier successful result', () => { const i = item('success'); i.error = 'transport unavailable'; expect(activityPresentation(i)).toMatchObject({ state: 'unavailable', provenance: 'UNAVAILABLE_ACTIVITY', verified: false }); });
it('retains timestamps, IDs and safe tool outcomes without arbitrary metadata', () => {
  const i = item(); i.events[0] = { ...i.events[0], event_type: 'tool_finished', tool_call_id: 'tool-1' };
  i.result!.data.tool_results = [{ tool_name: 'execute_tests', tool_call_id: 'tool-1', success: false, executed: true, exit_code: 1, timestamp: stamp }];
  Object.assign(i.events[0], { arguments: { token: 'private-secret' }, detail: 'Traceback private-secret' }); Object.assign(i.result!, { raw_output: 'private-secret' });
  const p = activityPresentation(i); expect(JSON.stringify(p)).not.toContain('private-secret'); expect(p.events[0]).toMatchObject({ toolId: 'tool-1', toolName: 'execute_tests', outcome: 'Tool failed', timestamp: stamp });
  render(<AriseActivityVisualizer activity={p} />); expect(screen.getByText(stamp).tagName).toBe('TIME'); expect(screen.getByText('Tool tool-1')).toBeTruthy();
});
it('never assigns later tool outcomes to earlier start events', () => { const i = item(); i.events[0].event_type = 'tool_started'; i.events[0].tool_call_id = 'tool-1'; i.result!.data.tool_results = [{ tool_name: 'write_file', tool_call_id: 'tool-1', success: true, executed: true, exit_code: 0, timestamp: stamp }]; expect(activityPresentation(i).events[0].outcome).toBe('Outcome not supplied'); });
it('drops foreign-request and unknown event kinds and withholds unsafe IDs', () => { const i = item(); i.events.push({ ...i.events[0], request_id: 'other', sequence: 2 }); i.events.push({ ...i.events[0], event_type: 'secret=unsafe', sequence: 3 }); i.events[0].tool_call_id = 'token=secret'; i.events[0].timestamp = 'not-a-time'; const p = activityPresentation(i); expect(p.events).toHaveLength(1); expect(p.events[0].toolId).toBeUndefined(); expect(p.events[0].timestamp).toBe('Timestamp unavailable'); });
it('disables all activity animation for reduced motion without targeting the brand mark', () => { const css = readFileSync('src/styles/activity.css', 'utf8'); expect(css).toContain('@media(prefers-reduced-motion:reduce)'); expect(css).toContain('animation:none!important'); expect(css).toContain('transition:none!important'); expect(css).not.toContain('.orbit-mark'); expect(css).not.toContain('img'); expect(css).toContain('max-height:110px'); });
