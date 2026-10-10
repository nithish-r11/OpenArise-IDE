import type { FileAddress, ProjectBridge, SaveRequest, RenameRequest } from '../src/types/project';
export const projectChannels = Object.freeze({
  open: 'openarise:project:open', list: 'openarise:project:list',
  read: 'openarise:project:read', save: 'openarise:project:save',
  observe: 'openarise:project:observe', dirty: 'openarise:project:dirty',
  create: 'openarise:project:create',
  createFolder: 'openarise:project:create-folder', inspectRename: 'openarise:project:inspect-rename', rename: 'openarise:project:rename',
  search: 'openarise:project:search',
  recent: 'openarise:project:recent', reopen: 'openarise:project:reopen',
});
export const validId = (id: unknown): id is string => typeof id === 'string' && /^[a-f0-9-]{36}$/.test(id);
export function validPath(path: unknown): path is string {
  return typeof path === 'string' && path.length <= 2048 && !/[\\:\x00-\x1f]/.test(path)
    && !path.startsWith('/') && (path === '' || path.split('/').every(p => p !== '' && p !== '.' && p !== '..'
      && !/[<>"|?*]/.test(p) && !/[. ]$/.test(p) && !/^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(p)));
}
export function validAddress(value: unknown, save = false): value is FileAddress | SaveRequest {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const obj = value as Record<string, unknown>;
  const keys = save ? ['content', 'path', 'projectId', 'revision'] : ['path', 'projectId'];
  if (Object.keys(obj).sort().join() !== keys.join() || !validId(obj.projectId) || !validPath(obj.path)) return false;
  return !save || (obj.path !== '' && typeof obj.content === 'string' && obj.content.length <= 2 * 1024 * 1024
    && !obj.content.includes('\0') && typeof obj.revision === 'string' && /^[a-f0-9]{64}$/.test(obj.revision));
}
export function createProjectBridge(invoke: (channel: string, ...args: unknown[]) => Promise<unknown>): ProjectBridge {
  return Object.freeze({
    openProject: () => invoke(projectChannels.open) as ReturnType<ProjectBridge['openProject']>,
    listDirectory: (address: FileAddress) => invoke(projectChannels.list, address) as ReturnType<ProjectBridge['listDirectory']>,
    readFile: (address: FileAddress) => invoke(projectChannels.read, address) as ReturnType<ProjectBridge['readFile']>,
    saveFile: (request: SaveRequest) => invoke(projectChannels.save, request) as ReturnType<ProjectBridge['saveFile']>,
    observeProject: (id: string) => invoke(projectChannels.observe, id) as ReturnType<ProjectBridge['observeProject']>,
    setDirty: (dirty: boolean) => invoke(projectChannels.dirty, dirty) as Promise<void>,
    createFile: (address: FileAddress) => invoke(projectChannels.create, address) as ReturnType<ProjectBridge['createFile']>,
    createFolder: (address: FileAddress) => invoke(projectChannels.createFolder, address) as ReturnType<ProjectBridge['createFolder']>,
    inspectRename: (address: FileAddress) => invoke(projectChannels.inspectRename, address) as ReturnType<ProjectBridge['inspectRename']>,
    renamePath: (request: RenameRequest) => invoke(projectChannels.rename, request) as ReturnType<ProjectBridge['renamePath']>,
    searchFiles: (request: { projectId: string; query: string }) => invoke(projectChannels.search, request) as ReturnType<ProjectBridge['searchFiles']>,
    recentProjects: () => invoke(projectChannels.recent) as ReturnType<ProjectBridge['recentProjects']>,
    openRecent: (id: string) => invoke(projectChannels.reopen, id) as ReturnType<ProjectBridge['openRecent']>,
  });
}
