/** Desktop editor contract, separate from the unchanged backend dispatcher. */
export interface Project { id: string; name: string; rootPath: string }
export interface Entry { name: string; path: string; kind: 'folder' | 'file' }
export interface FileBuffer { path: string; content: string; revision: string; readOnly: boolean }
export interface ProjectObservation { files: number; modules: number; observedAt: string }
export type ProjectErrorCode = 'invalid_request' | 'unavailable' | 'no_project' | 'stale_project' | 'access_denied' | 'not_found' | 'too_large' | 'unsupported_encoding' | 'read_only' | 'conflict' | 'permission_required' | 'io_error';
export type Result<T> = { ok: true; data: T } | { ok: false; code: ProjectErrorCode; message: string };
export interface FileAddress { projectId: string; path: string }
export interface SaveRequest extends FileAddress { content: string; revision: string }
export interface ProjectBridge {
  openProject(): Promise<Result<Project | null>>;
  listDirectory(address: FileAddress): Promise<Result<Entry[]>>;
  readFile(address: FileAddress): Promise<Result<FileBuffer>>;
  saveFile(request: SaveRequest): Promise<Result<FileBuffer>>;
  observeProject(projectId: string): Promise<Result<ProjectObservation>>;
  setDirty(dirty: boolean): Promise<void>;
}
