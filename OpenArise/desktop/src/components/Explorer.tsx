import { useEffect, useState } from 'react';
import type { Entry, Project, ProjectBridge, RenameInspection } from '../types/project';
import { validPath } from '../../shared/project-ipc';
export function FileIcon({ path }: { path: string }) {
  return <span className={/\.pyw?$/.test(path) ? 'file-icon python' : 'file-icon'} aria-hidden="true">{/\.pyw?$/.test(path) ? 'Py' : '▤'}</span>;
}
function Folder({ project, bridge, path, name, active, onOpen, onSelect, root = false, version = 0 }: {
  project: Project; bridge: ProjectBridge; path: string; name: string; active: string;
  onOpen: (path: string) => void; onSelect: (path: string) => void; root?: boolean; version?: number;
}) {
  const [expanded, setExpanded] = useState(root);
  const [entries, setEntries] = useState<Entry[]>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [reload, setReload] = useState(0);
  useEffect(() => {
    if (!expanded) return;
    let cancelled = false;
    setLoading(true); setError('');
    void bridge.listDirectory({ projectId: project.id, path }).then(result => {
      if (cancelled) return;
      if (result.ok) setEntries(result.data); else setError(result.message);
    }).catch(() => { if (!cancelled) setError('Unable to read folder.'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [bridge, project.id, path, expanded, reload, version]);
  return <div className={root ? 'root-folder' : 'folder'}>
    <button className="tree-folder" aria-expanded={expanded} onClick={() => { onSelect(path); setExpanded(!expanded); }} title={root ? project.rootPath : path}>
      <span aria-hidden="true" className="chevron">{expanded ? '⌄' : '›'}</span><span aria-hidden="true" className="folder-glyph">▱</span><span>{name}</span>
    </button>
    {expanded && <div className={root ? 'tree-children root-children' : 'tree-children'} role="group" aria-label={name}>
      {loading && <p className="tree-message" role="status">Loading folder…</p>}
      {error && <div className="tree-message" role="alert">{error}<button onClick={() => setReload(n => n + 1)}>Retry</button></div>}
      {!loading && !error && entries?.length === 0 && <p className="tree-message">{root ? 'This project has no visible files.' : 'Empty folder'}</p>}
      {!error && entries?.map(entry => entry.kind === 'folder' ?
        <Folder key={entry.path} project={project} bridge={bridge} path={entry.path} name={entry.name} active={active} onOpen={onOpen} onSelect={onSelect} version={version} /> :
        <button key={entry.path} className={'tree-file' + (active === entry.path ? ' active-file' : '')}
          aria-current={active === entry.path ? 'true' : undefined} title={entry.path} onClick={() => { onSelect(entry.path); onOpen(entry.path); }}>
          <FileIcon path={entry.path} /><span>{entry.name}</span>
        </button>)}
    </div>}
  </div>;
}
export function Explorer({ project, bridge, active, onOpen, opening, version = 0, onRefresh, onCreate, onCreateFolder, onRename, creating = false, blocked = false }: {
  project?: Project; bridge?: ProjectBridge; active: string; onOpen: (path: string) => void; opening: boolean;
  version?: number; onRefresh?: () => void; onCreate?: (path: string) => Promise<boolean>; creating?: boolean; blocked?: boolean;
  onCreateFolder?: (path: string) => Promise<boolean>; onRename?: (source: RenameInspection, destination: string) => Promise<boolean>;
}) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Entry[]>([]);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState('');
  const [newFile, setNewFile] = useState(false);
  const [newFolder, setNewFolder] = useState(false);
  const [selected, setSelected] = useState('');
  const [rename, setRename] = useState<RenameInspection>();
  const [reviewing, setReviewing] = useState(false);
  const [name, setName] = useState('');
  useEffect(() => { setQuery(''); setResults([]); setNewFile(false); setNewFolder(false); setRename(undefined); setSelected(''); setName(''); setError(''); }, [project?.id]);
  useEffect(() => { if (active) setSelected(active); }, [active]);
  const reviewRename = async () => {
    if (!project || !bridge || !selected || reviewing) return;
    setReviewing(true); setError(''); setNewFile(false); setNewFolder(false);
    try {
      const result = await bridge.inspectRename({ projectId: project.id, path: selected });
      if (result.ok) { setRename(result.data); setName(selected); } else setError(result.message);
    } catch { setError('Unable to review this path. Refresh Explorer and retry.'); }
    finally { setReviewing(false); }
  };
  useEffect(() => {
    if (!project || !bridge || !query.trim()) { setSearching(false); return; }
    let cancelled = false;
    setSearching(true); setError('');
    const timer = setTimeout(() => {
      void bridge.searchFiles({ projectId: project.id, query: query.trim() }).then(result => {
        if (cancelled) return;
        if (result.ok) setResults(result.data); else setError(result.message);
      }).catch(() => { if (!cancelled) setError('Filename search is unavailable. Reopen the project and retry.'); })
        .finally(() => { if (!cancelled) setSearching(false); });
    }, 250);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [project?.id, bridge, query, version]);
  return <section className="explorer-tree" aria-label="Project files">
    <div className="explorer-actions"><input aria-label="Search project filenames" placeholder="Find a file…" value={query} maxLength={120} disabled={!project || opening} onChange={e => setQuery(e.target.value)} />
      <button title="Refresh project files" aria-label="Refresh Explorer" disabled={!project || opening} onClick={onRefresh}>↻</button>
      <button title="Create a source file" aria-label="New file" disabled={!project || blocked || creating || opening} onClick={() => { setNewFile(v => !v); setNewFolder(false); setRename(undefined); setName(''); setError(''); }}>+</button>
      <button title="Create folder" aria-label="New folder" disabled={!project || blocked || creating || opening} onClick={() => { setNewFolder(v => !v); setNewFile(false); setRename(undefined); setName(''); setError(''); }}>▱+</button>
      <button title={selected ? 'Rename ' + selected : 'Select a file or folder to rename'} aria-label="Rename selected path" disabled={!project || !selected || blocked || creating || opening || reviewing} onClick={() => void reviewRename()}>✎</button></div>
    {(newFolder || rename) && <form className="new-file-form" onSubmit={event => {
      event.preventDefault();
      if (!name.trim() || !validPath(name.trim())) { setError('Use a relative path inside this project.'); return; }
      const operation = rename ? onRename?.(rename, name.trim()) : onCreateFolder?.(name.trim());
      void operation?.then(done => { if (done) { setNewFolder(false); setRename(undefined); setSelected(name.trim()); setName(''); } });
    }}><label htmlFor="explorer-path">{rename ? 'New name or relative path' : 'New folder in this project'}</label>
      <input id="explorer-path" autoFocus maxLength={2048} value={name} disabled={creating} onChange={e => setName(e.target.value)} />
      <small>{rename ? 'Renaming ' + rename.path + '. Save all editor changes first. Existing paths are never replaced.' : 'Creates one folder in an existing parent folder.'}</small>
      <div><button type="button" disabled={creating} onClick={() => { setNewFolder(false); setRename(undefined); }}>Cancel</button><button disabled={!name.trim() || creating || blocked}>{creating ? 'Working…' : rename ? 'Rename' : 'Create folder'}</button></div>
    </form>}
    {newFile && <form className="new-file-form" onSubmit={event => { event.preventDefault(); if (!name.trim() || !validPath(name.trim())) { setError('Use a relative path in an existing folder, such as frontend/src/view.tsx.'); return; } void onCreate?.(name.trim()).then(created => { if (created) { setNewFile(false); setName(''); } }); }}>
      <label htmlFor="new-file-path">New file in this project</label><input id="new-file-path" autoFocus maxLength={2048} placeholder="folder/file.py" value={name} disabled={creating} onChange={e => setName(e.target.value)} /><small>Creates an empty UTF-8 file. Existing files are never replaced.</small>
      <div><button type="button" disabled={creating} onClick={() => setNewFile(false)}>Cancel</button><button disabled={!name.trim() || creating || blocked}>{creating ? 'Creating…' : 'Create file'}</button></div></form>}
    {error && <p className="tree-message" role="alert">{error}</p>}
    {opening ? <p className="tree-message" role="status">Opening project...</p> :
      project && bridge ? query.trim() ? <div className="search-results">{searching ? <p className="tree-message" role="status">Searching project filenames…</p> : <>
        <p className="tree-message">{results.length === 200 ? 'First 200 matches · refine your search' : results.length + ' matches'}</p>{results.map(entry => <button className={'tree-file' + (active === entry.path ? ' active-file' : '')} key={entry.path} title={entry.path} onClick={() => { setSelected(entry.path); onOpen(entry.path); }}><FileIcon path={entry.path} /><span>{entry.path}</span></button>)}</>}</div> :
      <Folder key={project.id} project={project} bridge={bridge} path="" name={project.name} active={active} onOpen={onOpen} onSelect={setSelected} root version={version} /> :
      <p className="tree-message">No project open</p>}
  </section>;
}
