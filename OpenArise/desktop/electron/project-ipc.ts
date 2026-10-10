import { dialog, ipcMain, type BrowserWindow, type IpcMainInvokeEvent } from 'electron';
import { projectChannels, validAddress, validId, validPath } from '../shared/project-ipc';
import type { SaveRequest, RenameRequest } from '../src/types/project';
import { ProjectService } from './project-service';
export function registerProjectIpc(service: ProjectService, getWindow: () => BrowserWindow | null,
  trusted: (event: IpcMainInvokeEvent) => boolean, dirty: { value: boolean }) {
  let picking = false;
  for (const channel of Object.values(projectChannels)) {
    ipcMain.handle(channel, async (event, ...args: unknown[]) => {
      if (!trusted(event)) throw new Error('Untrusted IPC sender.');
      const invalid = { ok: false, code: 'invalid_request', message: 'Invalid project request.' };
      if (channel === projectChannels.recent) return args.length ? invalid : service.recentProjects();
      if (channel === projectChannels.reopen) {
        if (args.length !== 1 || !validId(args[0])) return invalid;
        if (dirty.value) return { ok: false, code: 'conflict', message: 'Save or close unsaved tabs before opening another project.' };
        return service.openRecent(args[0]);
      }
      if (channel === projectChannels.open) {
        if (args.length || picking) return invalid;
        if (dirty.value) return { ok: false, code: 'conflict', message: 'Save or close unsaved tabs before opening another project.' };
        const parent = getWindow();
        if (!parent) return invalid;
        picking = true;
        try {
          const picked = await dialog.showOpenDialog(parent, { title: 'Open OpenArise project', properties: ['openDirectory'] });
          if (picked.canceled || !picked.filePaths[0]) return { ok: true, data: null };
          if (dirty.value) return { ok: false, code: 'conflict', message: 'Save or close unsaved tabs before changing projects.' };
          return await service.open(picked.filePaths[0]);
        } finally { picking = false; }
      }
      if (channel === projectChannels.dirty) {
        if (args.length !== 1 || typeof args[0] !== 'boolean') return invalid;
        dirty.value = args[0]; return;
      }
      if (channel === projectChannels.observe) {
        if (args.length !== 1 || !validId(args[0])) return invalid;
        return service.observe(args[0]);
      }
      if (channel === projectChannels.search) {
        const request = args[0] as { projectId?: unknown; query?: unknown } | undefined;
        if (args.length !== 1 || !request || Object.keys(request).sort().join() !== 'projectId,query'
          || !validId(request.projectId) || typeof request.query !== 'string' || !request.query.trim() || request.query.length > 120) return invalid;
        return service.search(request.projectId, request.query);
      }
      if (channel === projectChannels.rename) {
        const r = args[0] as RenameRequest;
        if (args.length !== 1 || !r || Object.keys(r).sort().join() !== 'destination,path,projectId,revision'
          || !validId(r.projectId) || !validPath(r.path) || !r.path || !validPath(r.destination) || !r.destination
          || typeof r.revision !== 'string' || !/^[a-f0-9]{64}$/.test(r.revision)) return invalid;
        if (dirty.value || service.canChange && !service.canChange()) return { ok: false, code: 'conflict', message: 'Save editor changes and finish the active AI request before renaming.' };
        return service.rename(r.projectId, r.path, r.destination, r.revision);
      }
      if (args.length !== 1 || !validAddress(args[0], channel === projectChannels.save)) return invalid;
      const address = args[0];
      if (channel === projectChannels.list) return service.list(address.projectId, address.path);
      if (channel === projectChannels.read) return service.read(address.projectId, address.path);
      if (channel === projectChannels.inspectRename) return address.path ? service.inspectRename(address.projectId, address.path) : invalid;
      if (service.canChange && !service.canChange()) return { ok: false, code: 'conflict', message: 'Finish or cancel the active AI request before saving or creating files.' };
      if (channel === projectChannels.create) {
        if (!address.path) return invalid;
        return service.create(address.projectId, address.path);
      }
      if (channel === projectChannels.createFolder) return address.path ? service.createFolder(address.projectId, address.path) : invalid;
      const save = address as SaveRequest;
      return service.save(save.projectId, save.path, save.content, save.revision);
    });
  }
}
