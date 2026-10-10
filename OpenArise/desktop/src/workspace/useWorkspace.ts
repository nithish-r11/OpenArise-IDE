import { useCallback, useEffect, useRef, useState } from 'react';
import type { FileBuffer, Project, ProjectBridge, ProjectObservation, RenameInspection } from '../types/project';
export interface EditorTab extends FileBuffer { savedContent: string; saving: boolean; error?: string }
export function useWorkspace(bridge?: ProjectBridge) {
  const [project, setProject] = useState<Project>();
  const [tabs, setTabs] = useState<EditorTab[]>([]);
  const [active, setActive] = useState('');
  const [opening, setOpening] = useState(false);
  const [loading, setLoading] = useState('');
  const [error, setError] = useState('');
  const [observation, setObservation] = useState<ProjectObservation>();
  const [observing, setObserving] = useState(false);
  const [closePrompt, setClosePrompt] = useState('');
  const [creating, setCreating] = useState(false);
  const [treeVersion, setTreeVersion] = useState(0);
  const [savedVersion, setSavedVersion] = useState(0);
  const [recent, setRecent] = useState<Project[]>([]);
  const [reloadPrompt, setReloadPrompt] = useState('');
  const createLock = useRef(false);
  const renameLock = useRef(false);
  const tabsRef = useRef(tabs); tabsRef.current = tabs;
  const projectRef = useRef(project); projectRef.current = project;
  const busyOpen = useRef(false);
  const inFlight = useRef(new Set<string>());
  const saves = useRef(new Set<string>());
  const selection = useRef(0);
  const dirty = tabs.some(t => t.content !== t.savedContent);
  useEffect(() => { void bridge?.setDirty(dirty).catch(() => setError('Unsaved-change protection could not connect. Save your work before closing or switching projects.')); }, [bridge, dirty]);

  const loadRecent = async () => {
    if (!bridge?.recentProjects) return;
    try { const result = await bridge.recentProjects(); if (result.ok) setRecent(result.data); }
    catch { /* Session shortcuts are optional; native Open Project remains available. */ }
  };
  useEffect(() => { void loadRecent(); }, [bridge]);
  const openProject = async (recentId?: string) => {
    if (busyOpen.current || createLock.current) return;
    if (saves.current.size || tabsRef.current.some(t => t.saving || t.content !== t.savedContent)) {
      setError('Save or close unsaved tabs before opening another project.'); return;
    }
    if (!bridge) { setError('Open the Electron desktop application to choose a local project.'); return; }
    busyOpen.current = true; setOpening(true); setError('');
    try {
      const result = recentId ? await bridge.openRecent(recentId) : await bridge.openProject();
      if (!result.ok) { setError(result.message); return; }
      if (result.data) {
        selection.current++;
        setProject(result.data); projectRef.current = result.data;
        setTabs([]); setActive(''); setLoading(''); setObservation(undefined); setClosePrompt('');
        setReloadPrompt(''); void loadRecent();
      }
    } catch { setError('Unable to open project. The desktop connection is unavailable.'); }
    finally { busyOpen.current = false; setOpening(false); }
  };
  const openFile = async (path: string) => {
    const current = projectRef.current;
    if (!bridge || !current || busyOpen.current || renameLock.current) return;
    if (inFlight.current.has(path)) return;
    const index = ++selection.current;
    setError('');
    if (tabsRef.current.some(t => t.path === path)) { setActive(path); setLoading(''); return; }
    if (inFlight.current.has(path)) return;
    inFlight.current.add(path); setLoading(path);
    try {
      const result = await bridge.readFile({ projectId: current.id, path });
      if (projectRef.current?.id !== current.id) return;
      if (!result.ok) { setError('Unable to open file: ' + result.message); return; }
      setTabs(prev => prev.some(t => t.path === path) ? prev : [...prev, { ...result.data, savedContent: result.data.content, saving: false }]);
      if (selection.current === index) setActive(path);
    } catch { setError('Unable to open file. The desktop connection is unavailable.'); }
    finally { inFlight.current.delete(path); if (selection.current === index) setLoading(''); }
  };
  const change = useCallback((path: string, content: string) => {
    if (renameLock.current) return;
    setTabs(prev => prev.map(t => t.path === path && !t.readOnly ? { ...t, content } : t));
    // Notify the close guard immediately, in addition to the derived state effect.
    void bridge?.setDirty(true).catch(() => setError('Unsaved-change protection could not connect. Save your work before closing or switching projects.'));
  }, [bridge]);
  const save = async (path: string) => {
    const current = projectRef.current;
    const snapshot = tabsRef.current.find(t => t.path === path);
    if (!bridge || !current || renameLock.current || !snapshot || snapshot.readOnly || saves.current.has(path) || snapshot.content === snapshot.savedContent) return;
    saves.current.add(path);
    setTabs(prev => prev.map(t => t.path === path ? { ...t, saving: true, error: undefined } : t));
    try {
      const result = await bridge.saveFile({ projectId: current.id, path, content: snapshot.content, revision: snapshot.revision });
      if (projectRef.current?.id !== current.id) return;
      setTabs(prev => prev.map(t => t.path !== path ? t : result.ok ?
        // The backend may normalize line endings. Synchronize the acknowledged
        // buffer only if no newer edit occurred during the request.
        { ...t, content: t.content === snapshot.content ? result.data.content : t.content,
          revision: result.data.revision, savedContent: result.data.content, saving: false } :
        { ...t, saving: false, error: result.message }));
      if (result.ok) setSavedVersion(v => v + 1);
    } catch {
      setTabs(prev => prev.map(t => t.path === path ? { ...t, saving: false, error: 'Save could not be confirmed. Check the file on disk before retrying.' } : t));
    } finally { saves.current.delete(path); }
  };
  const closeTab = (path: string, discard = false) => {
    const tab = tabsRef.current.find(t => t.path === path);
    if (tab?.saving) return;
    if (tab && tab.content !== tab.savedContent && !discard) { setClosePrompt(path); return; }
    const remaining = tabsRef.current.filter(t => t.path !== path);
    setTabs(remaining);
    if (active === path) setActive(remaining.at(-1)?.path ?? '');
    setClosePrompt('');
  };
  const reloadFile = async (path: string, discard = false) => {
    const current = projectRef.current, tab = tabsRef.current.find(t => t.path === path);
    if (!bridge || !current || !tab || tab.saving || inFlight.current.has(path)) return;
    if (tab.content !== tab.savedContent && !discard) { setReloadPrompt(path); return; }
    inFlight.current.add(path); setLoading(path); setReloadPrompt('');
    try {
      const result = await bridge.readFile({ projectId: current.id, path });
      if (projectRef.current?.id !== current.id) return;
      if (!result.ok) { setError(result.message); return; }
      if (tabsRef.current.find(t => t.path === path)?.content !== tab.content) { setError('Your buffer changed while reloading. Edits were retained; review them before trying again.'); return; }
      setTabs(previous => previous.map(t => t.path === path ? { ...result.data, savedContent: result.data.content, saving: false } : t));
      setError(''); if (result.data.revision !== tab.revision) setSavedVersion(v => v + 1);
    } catch { setError('Reload could not complete. Your editor buffer was retained. Check project access and retry.'); }
    finally { inFlight.current.delete(path); setLoading(''); }
  };
  const observe = async () => {
    const current = projectRef.current;
    if (!current || !bridge || observing) return;
    setObserving(true); setError('');
    try {
      const result = await bridge.observeProject(current.id);
      if (projectRef.current?.id !== current.id) return;
      if (result.ok) setObservation(result.data); else setError(result.message);
    } catch { setError('Project state is unavailable.'); }
    finally { setObserving(false); }
  };
  const createFile = async (path: string): Promise<boolean> => {
    const current = projectRef.current;
    if (!bridge || !current || createLock.current || busyOpen.current) return false;
    createLock.current = true; setCreating(true); setError('');
    try {
      const result = await bridge.createFile({ projectId: current.id, path });
      if (projectRef.current?.id !== current.id) return false;
      if (!result.ok) { setError(result.message); return false; }
      setTabs(previous => [...previous, { ...result.data, savedContent: result.data.content, saving: false }]);
      setActive(result.data.path); setTreeVersion(v => v + 1); setSavedVersion(v => v + 1); return true;
    } catch { setError('File creation could not be confirmed. Refresh Explorer and check the path before retrying.'); return false; }
    finally { createLock.current = false; setCreating(false); }
  };
  const createFolder = async (path: string): Promise<boolean> => {
    const current = projectRef.current;
    if (!bridge || !current || createLock.current || busyOpen.current) return false;
    createLock.current = true; setCreating(true); setError('');
    try {
      const result = await bridge.createFolder({ projectId: current.id, path });
      if (projectRef.current?.id !== current.id) return false;
      if (!result.ok) { setError(result.message); return false; }
      setTreeVersion(v => v + 1); setSavedVersion(v => v + 1); void observe(); return true;
    } catch { setError('Folder creation could not be confirmed. Refresh Explorer before retrying.'); return false; }
    finally { createLock.current = false; setCreating(false); }
  };
  const renamePath = async (source: RenameInspection, destination: string): Promise<boolean> => {
    const current = projectRef.current;
    if (!bridge || !current || createLock.current || busyOpen.current) return false;
    if (saves.current.size || inFlight.current.size || tabsRef.current.some(t => t.content !== t.savedContent)) {
      setError('Save editor changes and wait for file operations before renaming.'); return false;
    }
    createLock.current = true; renameLock.current = true; setCreating(true); setError('');
    try {
      const result = await bridge.renamePath({ projectId: current.id, path: source.path, destination, revision: source.revision });
      if (projectRef.current?.id !== current.id) return false;
      if (!result.ok) { setError(result.message); return false; }
      const remaining = tabsRef.current.filter(t => t.path !== source.path && !t.path.startsWith(source.path + '/'));
      setTabs(remaining); setActive(remaining.at(-1)?.path ?? '');
      setTreeVersion(v => v + 1); setSavedVersion(v => v + 1); void observe();
      if (source.kind === 'file') { renameLock.current = false; await openFile(destination); }
      return true;
    } catch { setError('Rename could not be confirmed. Refresh Explorer and check both paths before retrying.'); return false; }
    finally { createLock.current = false; renameLock.current = false; setCreating(false); }
  };
  useEffect(() => { if (project) void observe(); }, [project?.id]);
  return { project, tabs, active, setActive: (path: string) => { selection.current++; setLoading(''); setActive(path); }, opening, loading, error, setError, observation, observing,
    dirty, closePrompt, setClosePrompt, openProject, openFile, change, save, closeTab, observe, createFile, creating, treeVersion,
    savedVersion, reloadFile, reloadPrompt, setReloadPrompt, recent, createFolder, renamePath,
    refreshTree: () => { setTreeVersion(v => v + 1); void observe(); } };
}
