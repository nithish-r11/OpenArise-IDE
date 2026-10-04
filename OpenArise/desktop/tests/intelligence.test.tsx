import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useState } from 'react';
import { IntelligencePanel } from '../src/components/Intelligence/IntelligencePanel';
import { useIntelligence } from '../src/workspace/useIntelligence';
import { intelligenceChecks } from '../shared/intelligence-response';
import fixtures from './fixtures/intelligence.json';
import type { IntelligenceView } from '../src/types/intelligence';
const project = { id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', name: 'orbit-workspace', rootPath: 'C:/orbit-workspace' };
let request: ReturnType<typeof vi.fn>;
const response = (r: any, data = (fixtures as any)[r.method]) => ({ kind: 'backend', response: { request_id: r.request_id, success: true, action_state: 'completed', data, error: null, events: [] } });
function Harness({ initial = 'Overview', selected = project }: { initial?: IntelligenceView; selected?: typeof project | null }) {
  const model = useIntelligence(selected), [view, setView] = useState(initial);
  return <IntelligencePanel view={view} onView={setView} model={model} project={selected} />;
}
beforeEach(() => { request = vi.fn(async r => response(r)); window.openarise = { request } as any; });
afterEach(() => { cleanup(); delete window.openarise; });
async function ready(view: IntelligenceView = 'Overview') { render(<Harness initial={view} />); await waitFor(() => expect((screen.getByRole('button', { name: 'Refresh intelligence' }) as HTMLButtonElement).disabled).toBe(false)); }
it('renders factual project information, counts and unavailable mapping coverage', async () => { await ready(); expect(screen.getByText('C:/orbit-workspace')).toBeTruthy(); expect(screen.getByText('Test files')).toBeTruthy(); expect(screen.getByText('Not reported by backend')).toBeTruthy(); expect(screen.queryByText(/quality score/i)).toBeNull(); });
it('keeps completed lifecycle separate from NOT_VERIFIED and renders criteria and links', async () => { await ready('Requirements'); for (const text of ['completed', 'NOT_VERIFIED', 'A greeting is returned', 'Greeting feature', 'Implement greeting']) expect(screen.getByText(text)).toBeTruthy(); expect(screen.queryByText('Verified by CompletionGate')).toBeNull(); });
it('renders expandable blueprint requirements features tasks and dependencies', async () => { await ready('Blueprint'); expect(document.querySelectorAll('details').length).toBe(2); expect(screen.getByText('Implement greeting')).toBeTruthy(); expect(screen.getByText(/Dependencies: None reported/)).toBeTruthy(); fireEvent.click(document.querySelector('summary')!); });
it('renders graph nodes and recorded edges with separate inferred and evidence-backed labels', async () => { await ready('Traceability'); expect(screen.getByText('Inferred')).toBeTruthy(); expect(screen.getByText('Evidence-backed')).toBeTruthy(); expect(document.querySelectorAll('.trace-node').length).toBe(6); expect(document.querySelectorAll('.trace-edge').length).toBe(5); expect(screen.queryByText('VERIFIED')).toBeNull(); });
it('shows backend invalid graph findings without manufacturing per-link classifications', async () => { request.mockImplementation(async r => response(r, r.method === 'get_traceability_graph' ? { ...fixtures.get_traceability_graph, validation: { valid: false, issues: ['Requirement req-1 has no feature mapping (Orphan)'] } } : (fixtures as any)[r.method])); await ready('Traceability'); expect(screen.getByText(/Invalid · backend/)).toBeTruthy(); expect(screen.getByRole('alert').textContent).toContain('Orphan'); });
it('shows interpreter dependency framework and pytest observations', async () => { await ready('Environment'); for (const text of ['C:/Python/python.exe', 'FastAPI', 'installed', 'READY', 'Pytest availability']) expect(screen.getAllByText(text).length).toBeGreaterThan(0); expect(screen.queryByRole('button', { name: /install/i })).toBeNull(); });
it('shows health severity and factual evidence', async () => { await ready('Health'); expect(screen.getByText('WARNING')).toBeTruthy(); expect(screen.getByText('Evidence: pytest 9.0')).toBeTruthy(); });
it('renders snapshot summaries without AI conclusions', async () => { await ready('Snapshot'); expect(screen.getByText('project state summary')).toBeTruthy(); expect(screen.getByText('NOT VERIFIED')).toBeTruthy(); expect(screen.getByText(/does not establish absence of drift/)).toBeTruthy(); });
it('shows only recorded timeline events and related IDs', async () => { await ready('Timeline'); expect(screen.getByText('Workspace scanned')).toBeTruthy(); expect(screen.getByText('PROJECT_SCANNED')).toBeTruthy(); expect(document.querySelectorAll('.intelligence-timeline li').length).toBe(1); });
it.each(['NO_DRIFT', 'POTENTIAL_DRIFT', 'CONFIRMED_STRUCTURAL_DRIFT', 'UNRESOLVED'])('requires an explicit baseline before comparison and presents %s unchanged', async state => {
  request.mockImplementation(async r => response(r, r.method === 'get_drift_report' ? { ...fixtures.get_drift_report, state } : (fixtures as any)[r.method]));
  await ready('Drift'); expect((screen.getByRole('button', { name: 'Compare drift' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: 'Capture baseline' })); await screen.findByRole('button', { name: 'Replace baseline' });
  fireEvent.click(screen.getByRole('button', { name: 'Compare drift' })); expect(await screen.findByText(state)).toBeTruthy(); expect(screen.getByText('app/main.py')).toBeTruthy();
  expect(request.mock.calls.find(([r]) => r.method === 'get_drift_report')?.[0].params).toEqual({ baseline_dict: { requirement_id: 'req-1' } });
});
it('shows loading and avoids concurrent duplicate refreshes', async () => {
  let finish!: (v: any) => void; request.mockImplementationOnce(r => new Promise(resolve => { finish = () => resolve(response(r)); }));
  render(<Harness />); expect(screen.getByText('Loading info…')).toBeTruthy(); expect(request).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByRole('button', { name: 'Reading…' })); expect(request).toHaveBeenCalledTimes(1);
  await act(async () => finish(null)); await screen.findByText('C:/orbit-workspace');
});
it('shows unavailable without fabricated counts when the bridge is absent', async () => { delete window.openarise; render(<Harness />); await screen.findByText(/Backend data unavailable for info/); expect(screen.queryByText('C:/orbit-workspace')).toBeNull(); });
it('shows errors and can retry a failed refresh', async () => {
  request.mockImplementationOnce(async r => ({ kind: 'backend', response: { request_id: r.request_id, success: false } }));
  await ready(); expect(screen.getByText(/Unable to load info/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Refresh intelligence' })); expect(await screen.findByText('C:/orbit-workspace')).toBeTruthy();
});
it('rejects malformed read data instead of rendering unsafe fields', async () => { request.mockImplementation(async r => response(r, r.method === 'get_project_information' ? { ...fixtures.get_project_information, raw_source: 'secret' } : (fixtures as any)[r.method])); await ready(); expect(screen.getByText(/Unable to load info/)).toBeTruthy(); expect(screen.queryByText('secret')).toBeNull(); });
it('shows empty records and project unavailable states', async () => { request.mockImplementation(async r => response(r, r.method === 'get_requirements' ? { items: [], total: 0, truncated: false } : (fixtures as any)[r.method])); await ready('Requirements'); expect(screen.getByText('No requirements reported.')).toBeTruthy(); cleanup(); render(<Harness selected={null} />); expect(screen.getByText(/Open a local project/)).toBeTruthy(); });
it('navigates between views without duplicate reads and refreshes explicitly', async () => { await ready(); const count = request.mock.calls.length; fireEvent.click(screen.getByRole('button', { name: 'Timeline' })); expect(screen.getByText('Workspace scanned')).toBeTruthy(); expect(request).toHaveBeenCalledTimes(count); fireEvent.click(screen.getByRole('button', { name: 'Refresh intelligence' })); await waitFor(() => expect(request).toHaveBeenCalledTimes(count * 2)); expect(request.mock.calls.every(([, id]) => id === project.id)).toBe(true); });
it('ignores responses from an earlier selected project', async () => {
  let finish!: () => void; request.mockImplementationOnce(r => new Promise(resolve => { finish = () => resolve(response(r)); }));
  const rendered = render(<Harness />); rendered.rerender(<Harness selected={null} />);
  await act(async () => finish()); expect(screen.queryByText('C:/orbit-workspace')).toBeNull();
});
it('validates every offline fixture and rejects extra unrestricted fields', () => { for (const [method, fixture] of Object.entries(fixtures)) { expect(intelligenceChecks[method](fixture), method).toBe(true); expect(intelligenceChecks[method]({ ...fixture, source: 'private' }), method).toBe(false); } });

it('updates snapshot and timeline after comparison without refreshing away the drift result', async () => {
  let compared = false;
  request.mockImplementation(async r => {
    if (r.method === 'get_drift_report') compared = true;
    if (compared && r.method === 'get_intelligence_snapshot') return response(r, { ...fixtures.get_intelligence_snapshot, drift_summary: [fixtures.get_drift_report] });
    if (compared && r.method === 'get_timeline') return response(r, { ...fixtures.get_timeline, items: [{ ...fixtures.get_timeline.items[0], event_type: 'DRIFT_DETECTED', title: 'Drift evaluated' }] });
    return response(r);
  });
  await ready('Drift'); fireEvent.click(screen.getByRole('button', { name: 'Capture baseline' })); await screen.findByRole('button', { name: 'Replace baseline' });
  fireEvent.click(screen.getByRole('button', { name: 'Compare drift' }));
  await waitFor(() => expect((screen.getByRole('button', { name: 'Refresh intelligence' }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole('button', { name: 'Snapshot' })); expect(screen.getByText(/req-1 · POTENTIAL_DRIFT/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Timeline' })); expect(screen.getByText('Drift evaluated')).toBeTruthy();
  expect(request.mock.calls.filter(([r]) => r.method === 'refresh_workspace').length).toBe(1);
});
