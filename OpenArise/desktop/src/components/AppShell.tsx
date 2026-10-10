import '../styles/intelligence.css';
import { useIntelligence } from '../workspace/useIntelligence';
import { IntelligencePanel } from './Intelligence/IntelligencePanel';
import { intelligenceViews, type IntelligenceView } from '../types/intelligence';
import '../styles/terminal.css';
import '../styles/ai.css';
import { useAI } from '../workspace/useAI';
import { AIPanel } from './AI/AIPanel';
import { useTerminal } from '../workspace/useTerminal';
import { TerminalPanel } from './Terminal/TerminalPanel';
import { EditorBoundary } from '../editor/EditorBoundary';
import { lazy, Suspense, useEffect, useState, type CSSProperties } from 'react';
import type { ConnectionState } from '../types/backend';
import { useWorkspace } from '../workspace/useWorkspace';
import { Explorer, FileIcon } from './Explorer';
import { Icon, OrbitMark } from './Icon';
import { sections, type Section } from './Sidebar';
import { ProjectCapabilities } from './ProjectCapabilities';
import { editorLanguage } from '../editor/language';
import { resultSummary } from '../workspace/resultSummary';
const MonacoEditor = lazy(() => import('../editor/MonacoEditor'));
export function AppShell({ connection }: { connection: ConnectionState }) {
  const bridge = window.openarise?.project;
  const workspace = useWorkspace(bridge);
  const ai = useAI(workspace.project, true);
  useEffect(() => {
    const keyboard = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'p') {
        event.preventDefault(); (document.querySelector('[aria-label="Search project filenames"]') as HTMLInputElement | null)?.focus();
      }
    };
    window.addEventListener('keydown', keyboard); return () => window.removeEventListener('keydown', keyboard);
  }, []);
  useEffect(() => { if (workspace.project) void ai.loadContext(); }, [workspace.project?.id]);
  useEffect(() => {
    if (workspace.savedVersion > 0 && ai.current?.result && !ai.busy && !ai.pending) void ai.command('refresh');
  }, [workspace.savedVersion]);
  const intelligence = useIntelligence(workspace.project);
  const [intelligenceView, setIntelligenceView] = useState<IntelligenceView | null>(null);
  const navigate = (name: Section) => { setSection(name); setIntelligenceView(name === 'Explorer' || name === 'AI' ? null : name); };
  const [section, setSection] = useState<Section>('Explorer');
  const [width, setWidth] = useState(224);
  const terminal = useTerminal(workspace.project, window.openarise?.terminal);
  const blocked = workspace.dirty || workspace.tabs.some(t => t.saving || !!t.error);
  const environment = terminal.snapshot?.environment;
  const run = (command: string, revision?: string) => { if (!blocked) void terminal.action({ operation: 'execute', sessionId: terminal.active || undefined, command, ...(revision ? { revision } : {}) }); };
  const running = terminal.snapshot?.sessions.find(s => s.id === terminal.active)?.state;
  const cannotRun = blocked || terminal.pending || ai.busy || !!ai.pending || environment?.status !== 'ready' || running === 'starting' || running === 'running';
  const active = workspace.tabs.find(t => t.path === workspace.active);
  const status = active?.saving ? 'Saving…' : active?.error ? 'Save failed' :
    active?.readOnly ? 'Read-only' : active && active.content !== active.savedContent ? 'Unsaved changes' : active ? 'Saved' : 'Ready';
  return <div className="app-shell phase-two">
    <a className="skip-link" href="#workspace">Skip to editor</a>
    <header className="top-bar">
      <div className="wordmark"><OrbitMark /><span>Open<span className="wordmark-accent">Arise</span><small> IDE</small></span></div>
      <div className="project-label" title={workspace.project?.rootPath}>{workspace.project?.name ?? 'No project open'}<span className="project-separator">/</span><span>Workspace</span></div>
      <button className="open-project" onClick={() => void workspace.openProject()} disabled={workspace.opening}><Icon name="Explorer" />{workspace.opening ? 'Opening project...' : 'Open Project'}</button>
    </header>
    <div className="ide-frame" style={{ '--explorer-width': width + 'px' } as CSSProperties}>
      <nav className="activity-rail" aria-label="Workspace sections">{sections.map(name =>
        <button key={name} title={name} aria-label={name} aria-current={section === name ? 'page' : undefined} className={section === name ? 'rail-active' : ''} onClick={() => navigate(name)}><Icon name={name} /></button>)}
      </nav>
      <aside className="explorer-panel">
        <div className="panel-heading"><span>{section === 'AI' ? 'Explorer' : section}</span><span className="subtle">Local workspace</span></div>
        {section === 'Explorer' || section === 'AI' ? <>
          <Explorer project={workspace.project} bridge={bridge} active={workspace.active} opening={workspace.opening} onOpen={path => void workspace.openFile(path)} version={workspace.treeVersion} onRefresh={workspace.refreshTree} onCreate={workspace.createFile} onCreateFolder={workspace.createFolder} onRename={workspace.renamePath} creating={workspace.creating} blocked={ai.busy || !!ai.pending} />
          <div className="project-summary">
            <span className="eyebrow">PROJECT CONTEXT</span><button className="quiet-button intelligence-shortcut" onClick={() => setIntelligenceView('Overview')}>Project Intelligence</button>
            {workspace.project && <ProjectCapabilities data={workspace.observation?.capabilities} loading={workspace.observing} blocked={blocked || terminal.pending || ai.busy || !!ai.pending || running === 'starting' || running === 'running'} onCommand={command => { if (command.kind === 'pytest') run('pytest'); else void terminal.action({ operation: 'executeCapability', sessionId: terminal.active || undefined, capabilityId: command.id }); }} />}
            <details className="project-details"><summary>Project information</summary>
            <div className="python-environment" title={environment?.executable}><b>{environment?.version || 'Python environment'}</b><span>{environment?.label ?? 'Open a project to inspect Python'}</span><span>{environment?.status ?? 'Not inspected'}</span><code>{environment?.executable}</code><small>{environment?.message}</small><button className="quiet-button" disabled={!workspace.project || terminal.pending} onClick={() => void terminal.action({ operation: 'refresh' })}>Refresh Python</button></div>
            <p title={workspace.project?.rootPath}>{workspace.project?.rootPath ?? 'Choose a local folder to begin.'}</p>
            {workspace.observation ? <p>{workspace.observation.files} files · {workspace.observation.modules} Python modules<br /><span title={workspace.observation.observedAt}>Observed snapshot · refresh after edits</span></p> : <p className="subtle">Project state not loaded</p>}
            <button className="quiet-button" disabled={!workspace.project || workspace.observing} onClick={() => void workspace.observe()}>{workspace.observing ? 'Reading state…' : 'Refresh project state'}</button>
            </details>
          </div>
        </> : <div className="intelligence-sidebar"><span className="eyebrow">PROJECT INTELLIGENCE</span>{intelligenceViews.map(v => <button className="quiet-button" key={v} onClick={() => setIntelligenceView(v)}>{v}</button>)}<p>Backend observations. Refresh after saved changes.</p><button className="quiet-button" onClick={() => navigate('Explorer')}>Back to Explorer</button></div>}
      </aside>
      <div className="panel-splitter" role="separator" tabIndex={0} aria-label="Explorer width" aria-orientation="vertical" aria-valuemin={170} aria-valuemax={340} aria-valuenow={width}
        onKeyDown={event => { if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') { event.preventDefault(); setWidth(w => Math.max(170, Math.min(340, w + (event.key === 'ArrowRight' ? 16 : -16)))); } }}
        onPointerDown={event => { event.currentTarget.setPointerCapture(event.pointerId); }}
        onPointerMove={event => { if (event.currentTarget.hasPointerCapture(event.pointerId)) setWidth(Math.max(170, Math.min(340, event.clientX - 66))); }}
        onPointerUp={event => event.currentTarget.releasePointerCapture(event.pointerId)} />
      <main className="editor-workspace" id="workspace" tabIndex={-1}>
        {workspace.error && <div className="error-banner" role="alert"><span>{workspace.error}</span><button aria-label="Dismiss error" onClick={() => workspace.setError('')}>×</button></div>}
        {workspace.closePrompt && <div className="discard-banner" role="alert"><span>Unsaved changes in {workspace.closePrompt}</span><button onClick={() => workspace.setClosePrompt('')}>Keep editing</button><button onClick={() => workspace.closeTab(workspace.closePrompt, true)}>Discard changes</button></div>}
        {workspace.reloadPrompt && <div className="discard-banner" role="alert"><span>Reload {workspace.reloadPrompt} from disk? Unsaved edits will be replaced.</span><button onClick={() => workspace.setReloadPrompt('')}>Keep editing</button><button onClick={() => void workspace.reloadFile(workspace.reloadPrompt, true)}>Discard and reload</button></div>}
        {workspace.loading && <div className="loading-banner" role="status">Loading file...</div>}
        {connection.reason === 'bridge_unavailable' && <div className="error-banner" role="alert">Desktop connection unavailable. Close this window and launch OpenArise again. Local project actions require the Electron application.</div>}
        {intelligenceView && <IntelligencePanel view={intelligenceView} onView={setIntelligenceView} model={intelligence} project={workspace.project} />}<div className="editor-surface" hidden={!!intelligenceView}><div className="editor-tabs" role="tablist" aria-label="Open files">
          {workspace.tabs.length ? workspace.tabs.map(tab => <div className={'editor-tab' + (tab.path === workspace.active ? ' tab-active' : '')} key={tab.path}>
            <button role="tab" aria-selected={tab.path === workspace.active} onClick={() => workspace.setActive(tab.path)} title={tab.path}><FileIcon path={tab.path} /><span>{tab.path.split('/').at(-1)}</span>{tab.content !== tab.savedContent && <span className="dirty-dot" aria-label="Unsaved changes">●</span>}</button>
            <button className="close-tab" aria-label={'Close ' + tab.path} disabled={tab.saving} onClick={() => workspace.closeTab(tab.path)}>×</button>
          </div>) : <div className="welcome-tab"><Icon name="layers" /> Workspace</div>}
        </div>

        {active?.error && <div className="error-banner" role="alert">{active.error}</div>}
        {active ? <>
          <div className="editor-toolbar"><span className="breadcrumb">{workspace.project?.name} <b>›</b> {active.path}</span>
            <button className="run-python" disabled={cannotRun || !/\.pyw?$/i.test(active.path)} onClick={() => run('python ' + active.path, active.revision)}>▷ Run</button>
            <button className="run-tests" disabled={cannotRun} onClick={() => run('pytest')}>Test</button>
            <button className="reload-file" disabled={active.saving || !!workspace.loading || ai.busy || !!ai.pending} title="Reload current file from disk; unsaved edits require confirmation" onClick={() => void workspace.reloadFile(active.path)}>Reload</button><span className="save-label">{status}</span><button className="save-button" disabled={active.readOnly || active.saving || ai.busy || !!ai.pending || active.content === active.savedContent} onClick={() => void workspace.save(active.path)}>Save <kbd>Ctrl S</kbd></button>
          </div>
          <div className="editor-container"><EditorBoundary key={workspace.project?.id}><Suspense fallback={<div className="loading-banner">Loading editor...</div>}><MonacoEditor key={workspace.project?.id} tabs={workspace.tabs} active={workspace.active} onChange={workspace.change} onSave={path => void workspace.save(path)} locked={workspace.creating || ai.busy || !!ai.pending} /></Suspense></EditorBoundary></div>
        </> : <section className="editor-welcome">
          <OrbitMark large /><span className="eyebrow">YOUR IDE. YOUR NEXT IDEA.</span><h1>A clearer space to build.</h1>
          <p>{workspace.project ? 'Select a file in Explorer, or create a new source file.' : 'Open a local project folder. Your files stay on your computer.'}</p>
          <button className="primary-button" disabled={workspace.opening} onClick={() => void workspace.openProject()}><Icon name="Explorer" />Open a project<span>↗</span></button>
          {!!workspace.recent.length && <details className="recent-projects"><summary>Recent projects · this session</summary>{workspace.recent.map(p => <button key={p.id} title={p.rootPath} disabled={workspace.opening} onClick={() => void workspace.openProject(p.id)}>{p.name}</button>)}</details>}
          {!workspace.project && <ol className="welcome-steps" aria-label="Getting started"><li>Open a project to inspect its real files and capabilities.</li><li>Edit source files and save with conflict protection.</li><li>Run supported commands and ask AI about the project.</li></ol>}<div className="welcome-details"><span>Local workspace</span><i /> <span>Controlled execution</span><i /><span>Evidence-based results</span></div>
        </section>}
        </div><TerminalPanel terminal={terminal} blocked={blocked} revisions={Object.fromEntries(workspace.tabs.map(t => [t.path, t.revision]))} fileError={active?.error || workspace.error} />
      </main>
      <AIPanel ai={ai} project={workspace.project} blocked={blocked} expanded={section === 'AI'} onToggle={() => navigate(section === 'AI' ? 'Explorer' : 'AI')} />
    </div>
    <footer className="status-bar" role="status"><span><span className="status-dot" />{workspace.project?.name ?? 'No project open'}</span><span title={active?.path}>{active?.path ?? 'No file'} · {status}</span><span title={environment?.message}>{active ? editorLanguage(active.path) : 'No language'}{workspace.observation?.capabilities?.languages.includes('Python') ? ' · ' + (environment?.version || 'Python not ready') : ''}</span><span className="status-right">{ai.busy ? 'Working…' : ai.contextState === 'ready' ? 'Project context ready' : ai.contextState === 'unavailable' ? 'AI connection unavailable' : 'Open a project'} · {ai.current ? resultSummary(ai.current).title : 'Ready'} · {running ?? 'terminal closed'}</span></footer>
  </div>;
}
