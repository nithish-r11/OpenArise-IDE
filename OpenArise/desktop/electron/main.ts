import { WorkspaceBackendAdapter } from './agent-process';
import type { BackendProcessAdapter } from './backend-service';
import { TerminalService } from './terminal-service';
import { registerTerminalIpc } from './terminal-ipc';
import { ProjectService } from './project-service';
import { registerProjectIpc } from './project-ipc';
import { app, BrowserWindow, ipcMain, session, dialog, Menu } from 'electron';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { DesktopBackendService } from './backend-service';
import { channels, isScopedBackendRequest } from '../shared/ipc';
import { DEV_URL, trustedPage, windowOptions } from './security';
export function startDesktop(testAdapter?: BackendProcessAdapter) {
app.setName('OpenArise');
if (!app.requestSingleInstanceLock()) { app.quit(); return; }
const dev = !app.isPackaged && process.argv.includes('--openarise-dev');
const rendererPath = path.join(__dirname, '../dist/index.html');
const expectedPage = dev ? DEV_URL : pathToFileURL(rendererPath).href;
const projects = new ProjectService();
const adapter = new WorkspaceBackendAdapter(projects);
const backend = new DesktopBackendService(testAdapter ?? adapter, testAdapter ? 'test_fixture' : 'backend');
const dirty = { value: false };
const terminals = new TerminalService(projects, dirty);
projects.canChange = () => !adapter.blocked && !backend.blocked;
projects.beforeChange = async () => { await adapter.reset(); await terminals.reset(); };
let window: BrowserWindow | null = null;
let quitting = false;
app.on('second-instance', () => {
  if (!window) return;
  if (window.isMinimized()) window.restore();
  window.show(); window.focus();
});
function createWindow() {
  window = new BrowserWindow({ ...windowOptions(path.join(__dirname, 'preload.cjs')), icon: path.join(__dirname, '../build/icon.png') });
  const current = window;
  current.webContents.on('before-input-event', (event, input) => {
    if (dirty.value && (input.key === 'F5' || ((input.control || input.meta) && input.key.toLowerCase() === 'r'))) event.preventDefault();
  });
  current.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  current.webContents.on('will-navigate', (event) => event.preventDefault());
  current.webContents.on('will-redirect', (event) => event.preventDefault());
  current.webContents.on('will-attach-webview', (event) => event.preventDefault());
  current.once('ready-to-show', () => current.show());
  current.webContents.on('render-process-gone', () => {
    if (current.isDestroyed() || quitting) return;
    dialog.showErrorBox('OpenArise interface stopped', 'The renderer process stopped unexpectedly. Any unsaved edits may be lost. Close OpenArise and reopen the project; review files and any action already started before retrying.');
    current.close();
  });
  current.on('closed', () => { window = null; });
  current.on('close', (event) => {
    if (!dirty.value) return;
    event.preventDefault();
    const choice = dialog.showMessageBoxSync(current, { type: 'warning', message: 'Discard unsaved changes?', detail: 'Your editor buffers have not been saved.', buttons: ['Keep editing', 'Discard and close'], defaultId: 0, cancelId: 0 });
    if (choice === 1) { dirty.value = false; current.close(); }
  });
  const loading = dev ? current.loadURL(DEV_URL) : current.loadFile(rendererPath);
  void loading.then(() => { if (!current.isDestroyed()) current.show(); }).catch(() => { dialog.showErrorBox('OpenArise could not open', 'The desktop interface failed to load. Reinstall OpenArise or contact support.'); app.quit(); });
}
void app.whenReady().then(() => {
  Menu.setApplicationMenu(null);
  session.defaultSession.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));
  session.defaultSession.setPermissionCheckHandler(() => false);
  for (const channel of Object.values(channels)) {
    ipcMain.handle(channel, async (event, ...args: unknown[]) => {
      if (!window || event.sender !== window.webContents || event.senderFrame !== window.webContents.mainFrame || !trustedPage(event.senderFrame.url, expectedPage)) throw new Error('Untrusted IPC sender.');
      if (channel === channels.request) {
        if (!isScopedBackendRequest(args, projects.current?.id)) return { kind: 'unavailable', request_id: 'invalid', code: 'invalid_message', message: 'Invalid desktop request.' };
        if (dirty.value && ['request_agent_execution', 'resume_agent_execution'].includes(args[0].method)) return { kind: 'unavailable', request_id: args[0].request_id, code: 'invalid_message', message: 'Save or discard unsaved changes before AI execution.' };
        return backend.request(args[0]);
      }
      if (args.length !== 0) throw new Error('Unexpected IPC arguments.');
      if (channel === channels.connect) return backend.connect();
      if (channel === channels.disconnect) return backend.disconnect();
      return backend.getStatus();
    });
  }
  registerProjectIpc(projects, () => window, (event) => !!window && event.sender === window.webContents && event.senderFrame === window.webContents.mainFrame && trustedPage(event.senderFrame.url, expectedPage), dirty);
  registerTerminalIpc(terminals, event => !!window && event.sender === window.webContents && event.senderFrame === window.webContents.mainFrame && trustedPage(event.senderFrame.url, expectedPage));
  createWindow();
  app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
});
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
app.on('before-quit', (event) => {
  if (quitting) return;
  if (dirty.value && window) {
    event.preventDefault(); window.close(); return;
  }
  event.preventDefault();
  quitting = true;
  void terminals.close().then(() => Promise.all([backend.disconnect(), projects.close()])).catch(() => console.error('Backend shutdown did not acknowledge.')).finally(() => app.quit());
});

}

