import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { RuntimeBoundary } from '../src/components/RuntimeBoundary';
import App from '../src/App';
afterEach(() => { cleanup(); vi.restoreAllMocks(); delete window.openarise; });
function BrokenPanel(): never { throw new Error('private raw trace and model details'); }
it('shows a renderer fallback without claiming success or exposing raw error details', () => {
  vi.spyOn(console, 'error').mockImplementation(() => {});
  render(<RuntimeBoundary><BrokenPanel /></RuntimeBoundary>);
  expect(screen.getByRole('heading', { level: 1 }).textContent).toContain('could not continue');
  expect(screen.getByRole('alert').textContent).toContain('No successful action');
  expect(screen.queryByText(/private raw trace/)).toBeNull();
  expect(screen.queryByRole('button', { name: 'Reload and discard unsaved edits' })).toBeNull();
});
it('requires a visible discard decision before offering runtime reload and permits cancellation', () => {
  vi.spyOn(console, 'error').mockImplementation(() => {});
  render(<RuntimeBoundary><BrokenPanel /></RuntimeBoundary>);
  fireEvent.click(screen.getByRole('button', { name: 'Reload OpenArise' }));
  expect(screen.getByText(/Reloading discards unsaved in-memory edits/)).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Reload and discard unsaved edits' })).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Keep this screen' }));
  expect(screen.queryByRole('button', { name: 'Reload and discard unsaved edits' })).toBeNull();
});
it('starts with truthful local-project guidance and no fixture or fabricated activity', async () => {
  render(<App />);
  expect(screen.getByRole('list', { name: 'Getting started' })).toBeTruthy();
  expect(screen.getByText('Open a Python project folder.')).toBeTruthy();
  expect(await screen.findByText(/Desktop connection unavailable. Close this window/)).toBeTruthy();
  expect(screen.queryByText('TEST FIXTURE')).toBeNull();
  expect(screen.queryByRole('tab')).toBeNull();
  expect(screen.getByLabelText('Arise Activity Visualizer').getAttribute('data-state')).toBe('idle');
});
it('keeps project failures visible when switching to intelligence', async () => {
  window.openarise = { getStatus: async () => ({ status: 'disconnected', reason: 'no_project' }), project: {
    openProject: async () => ({ ok: false, code: 'project_unavailable', message: 'Selected project is unavailable. Choose another folder.' }),
    setDirty: async () => {},
  } } as any;
  render(<App />);
  fireEvent.click(screen.getByRole('button', { name: 'Open Project' }));
  await screen.findByText(/Selected project is unavailable/);
  fireEvent.click(screen.getByRole('button', { name: 'Health' }));
  const message = screen.getByText(/Selected project is unavailable/);
  expect(message.closest('[hidden]')).toBeNull();
  expect(message.closest('[role=alert]')).toBeTruthy();
});