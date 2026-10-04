import { useEffect, useState } from 'react';
import type { Entry, Project, ProjectBridge } from '../types/project';
export function FileIcon({ path }: { path: string }) {
  return <span className={/\.pyw?$/.test(path) ? 'file-icon python' : 'file-icon'} aria-hidden="true">{/\.pyw?$/.test(path) ? 'Py' : '▤'}</span>;
}
function Folder({ project, bridge, path, name, active, onOpen, root = false }: {
  project: Project; bridge: ProjectBridge; path: string; name: string; active: string;
  onOpen: (path: string) => void; root?: boolean;
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
  }, [bridge, project.id, path, expanded, reload]);
  return <div className={root ? 'root-folder' : 'folder'}>
    <button className="tree-folder" aria-expanded={expanded} onClick={() => setExpanded(!expanded)} title={root ? project.rootPath : path}>
      <span aria-hidden="true" className="chevron">{expanded ? '⌄' : '›'}</span><span aria-hidden="true" className="folder-glyph">▱</span><span>{name}</span>
    </button>
    {expanded && <div className={root ? 'tree-children root-children' : 'tree-children'} role="group" aria-label={name}>
      {loading && <p className="tree-message" role="status">Loading folder…</p>}
      {error && <div className="tree-message" role="alert">{error}<button onClick={() => setReload(n => n + 1)}>Retry</button></div>}
      {!loading && !error && entries?.length === 0 && <p className="tree-message">{root ? 'This project has no visible files.' : 'Empty folder'}</p>}
      {!error && entries?.map(entry => entry.kind === 'folder' ?
        <Folder key={entry.path} project={project} bridge={bridge} path={entry.path} name={entry.name} active={active} onOpen={onOpen} /> :
        <button key={entry.path} className={'tree-file' + (active === entry.path ? ' active-file' : '')}
          aria-current={active === entry.path ? 'true' : undefined} title={entry.path} onClick={() => onOpen(entry.path)}>
          <FileIcon path={entry.path} /><span>{entry.name}</span>
        </button>)}
    </div>}
  </div>;
}
export function Explorer({ project, bridge, active, onOpen, opening }: {
  project?: Project; bridge?: ProjectBridge; active: string; onOpen: (path: string) => void; opening: boolean;
}) {
  return <section className="explorer-tree" aria-label="Project files">
    {opening ? <p className="tree-message" role="status">Opening project...</p> :
      project && bridge ? <Folder key={project.id} project={project} bridge={bridge} path="" name={project.name} active={active} onOpen={onOpen} root /> :
      <p className="tree-message">No project open</p>}
  </section>;
}
