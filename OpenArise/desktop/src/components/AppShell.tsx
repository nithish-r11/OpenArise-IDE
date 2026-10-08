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
const MonacoEditor = lazy(() => import('../editor/MonacoEditor'));
export function AppShell({ connection }: { connection: ConnectionState }) {
  const bridge = window.openarise?.project;
  const workspace = useWorkspace(bridge);
  const ai = useAI(workspace.project, true);
  useEffect(() => { if (workspace.project) void ai.loadContext(); }, [workspace.project?.id]);
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
  const cannotRun = blocked || terminal.pending || environment?.status !== 'ready' || running === 'starting' || running === 'running';
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
        <span className="rail-bottom">05</span>
      </nav>
      <aside className="explorer-panel">
        <div className="panel-heading"><span>{section === 'AI' ? 'Explorer' : section}</span><span className="subtle">⌘</span></div>
        {section === 'Explorer' || section === 'AI' ? <>
          <Explorer project={workspace.project} bridge={bridge} active={workspace.active} opening={workspace.opening} onOpen={path => void workspace.openFile(path)} />
          <div className="project-summary">
            <span className="eyebrow">PROJECT CONTEXT</span><button className="quiet-button intelligence-shortcut" onClick={() => setIntelligenceView('Overview')}>Project Intelligence</button>
            <div className="python-environment" title={environment?.executable}><b>{environment?.version || 'Python environment'}</b><span>{environment?.label ?? 'Open a project to inspect Python'}</span><span>{environment?.status ?? 'Not inspected'}</span><code>{environment?.executable}</code><small>{environment?.message}</small><button className="quiet-button" disabled={!workspace.project || terminal.pending} onClick={() => void terminal.action({ operation: 'refresh' })}>Refresh Python</button></div>
            <p title={workspace.project?.rootPath}>{workspace.project?.rootPath ?? 'Choose a local folder to begin.'}</p>
            {workspace.observation ? <p>{workspace.observation.files} files · {workspace.observation.modules} Python modules<br /><span title={workspace.observation.observedAt}>Observed snapshot · refresh after edits</span></p> : <p className="subtle">Project state not loaded</p>}
            <button className="quiet-button" disabled={!workspace.project || workspace.observing} onClick={() => void workspace.observe()}>{workspace.observing ? 'Reading state…' : 'Refresh project state'}</button>
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
            <span className="save-label">{status}</span><button className="save-button" disabled={active.readOnly || active.saving || active.content === active.savedContent} onClick={() => void workspace.save(active.path)}>Save <kbd>Ctrl S</kbd></button>
          </div>
          <div className="editor-container"><EditorBoundary key={workspace.project?.id}><Suspense fallback={<div className="loading-banner">Loading editor...</div>}><MonacoEditor key={workspace.project?.id} tabs={workspace.tabs} active={workspace.active} onChange={workspace.change} onSave={path => void workspace.save(path)} /></Suspense></EditorBoundary></div>
        </> : <section className="editor-welcome">
          <OrbitMark large /><span className="eyebrow">YOUR IDE. YOUR NEXT IDEA.</span><h1>A clearer space to build.</h1>
          <p>{workspace.project ? 'Select a file in Explorer to start working.' : 'Open a local Python folder. Your files stay on your computer.'}</p>
          <button className="primary-button" disabled={workspace.opening} onClick={() => void workspace.openProject()}><Icon name="Explorer" />Open a project<span>↗</span></button>
          {!workspace.project && <ol className="welcome-steps" aria-label="Getting started"><li>Open a Python project folder.</li><li>Select a .py file, edit it, and save.</li><li>Use Run or Test with the detected Python environment.</li></ol>}<div className="welcome-details"><span>Local workspace</span><i /> <span>Python first</span><i /><span>Built with intention</span></div>
        </section>}
        </div><TerminalPanel terminal={terminal} blocked={blocked} revisions={Object.fromEntries(workspace.tabs.map(t => [t.path, t.revision]))} fileError={active?.error || workspace.error} />
      </main>
      <AIPanel ai={ai} project={workspace.project} blocked={blocked} expanded={section === 'AI'} onToggle={() => navigate(section === 'AI' ? 'Explorer' : 'AI')} />
    </div>
    <footer className="status-bar" role="status"><span><span className="status-dot" />{workspace.project?.name ?? 'No project open'}</span><span title={active?.path}>{active?.path ?? 'No file'} · {status}</span><span className="status-right">{active ? /\.pyw?$/i.test(active.path) ? 'Python' : 'Plain text · read-only' : 'Python workspace'}<span className="status-divider">|</span>{connection.reason === 'bridge_unavailable' ? 'Desktop connection unavailable' : (environment?.version || 'Python unavailable') + ' · ' + (environment?.status ?? 'Not inspected') + ' · terminal ' + (running ?? 'closed')}</span></footer>
  </div>;
}
