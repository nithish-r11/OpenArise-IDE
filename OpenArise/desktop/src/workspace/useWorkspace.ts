import { useCallback, useEffect, useRef, useState } from 'react';
import type { FileBuffer, Project, ProjectBridge, ProjectObservation } from '../types/project';
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
  const tabsRef = useRef(tabs); tabsRef.current = tabs;
  const projectRef = useRef(project); projectRef.current = project;
  const busyOpen = useRef(false);
  const inFlight = useRef(new Set<string>());
  const saves = useRef(new Set<string>());
  const selection = useRef(0);
  const dirty = tabs.some(t => t.content !== t.savedContent);
  useEffect(() => { void bridge?.setDirty(dirty).catch(() => {}); }, [bridge, dirty]);

  const openProject = async () => {
    if (busyOpen.current) return;
    if (saves.current.size || tabsRef.current.some(t => t.saving || t.content !== t.savedContent)) {
      setError('Save or close unsaved tabs before opening another project.'); return;
    }
    if (!bridge) { setError('Open the Electron desktop application to choose a local project.'); return; }
    busyOpen.current = true; setOpening(true); setError('');
    try {
      const result = await bridge.openProject();
      if (!result.ok) { setError(result.message); return; }
      if (result.data) {
        selection.current++;
        setProject(result.data); projectRef.current = result.data;
        setTabs([]); setActive(''); setLoading(''); setObservation(undefined); setClosePrompt('');
      }
    } catch { setError('Unable to open project. The desktop connection is unavailable.'); }
    finally { busyOpen.current = false; setOpening(false); }
  };
  const openFile = async (path: string) => {
    const current = projectRef.current;
    if (!bridge || !current || busyOpen.current) return;
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
    setTabs(prev => prev.map(t => t.path === path && !t.readOnly ? { ...t, content } : t));
    // Notify the close guard immediately, in addition to the derived state effect.
    void bridge?.setDirty(true).catch(() => {});
  }, [bridge]);
  const save = async (path: string) => {
    const current = projectRef.current;
    const snapshot = tabsRef.current.find(t => t.path === path);
    if (!bridge || !current || !snapshot || snapshot.readOnly || saves.current.has(path) || snapshot.content === snapshot.savedContent) return;
    saves.current.add(path);
    setTabs(prev => prev.map(t => t.path === path ? { ...t, saving: true, error: undefined } : t));
    try {
      const result = await bridge.saveFile({ projectId: current.id, path, content: snapshot.content, revision: snapshot.revision });
      if (projectRef.current?.id !== current.id) return;
      setTabs(prev => prev.map(t => t.path !== path ? t : result.ok ?
        { ...t, revision: result.data.revision, savedContent: result.data.content, saving: false } :
        { ...t, saving: false, error: result.message }));
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
  return { project, tabs, active, setActive: (path: string) => { selection.current++; setLoading(''); setActive(path); }, opening, loading, error, setError, observation, observing,
    dirty, closePrompt, setClosePrompt, openProject, openFile, change, save, closeTab, observe };
}
