import { ipcMain, type IpcMainInvokeEvent } from 'electron';
import { terminalChannel, validTerminalRequest } from '../shared/terminal-ipc';
import type { TerminalService } from './terminal-service';
export function registerTerminalIpc(service: TerminalService, trusted: (event: IpcMainInvokeEvent) => boolean) {
  ipcMain.handle(terminalChannel, (event, ...args: unknown[]) => {
    if (!trusted(event)) throw new Error('Untrusted IPC sender.');
    if (args.length !== 1 || !validTerminalRequest(args[0])) return { ok: false, code: 'invalid_request', message: 'Invalid command. Use python --version, python <opened saved file.py>, or pytest.' };
    return service.request(args[0]).catch(() => ({ ok: false, code: 'unavailable', message: 'Terminal operation could not complete.' }));
  });
}
