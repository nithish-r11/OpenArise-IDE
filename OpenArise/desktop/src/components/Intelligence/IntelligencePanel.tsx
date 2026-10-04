import { useEffect, type ReactNode } from 'react';
import { intelligenceViews, type IntelligenceView, type IntelligenceBundle, type TraceGraph } from '../../types/intelligence';
import type { IntelligenceController } from '../../workspace/useIntelligence';
import type { Project } from '../../types/project';
const label = (s: string) => s.replaceAll('_', ' ');
function Facts({ values }: { values: Record<string, unknown> }) { return <dl className="intelligence-facts">{Object.entries(values).map(([key, value]) => <div key={key}><dt>{label(key)}</dt><dd>{value == null ? 'Not reported' : typeof value === 'boolean' ? value ? 'Yes' : 'No' : String(value)}</dd></div>)}</dl>; }
function Empty({ children = 'No records reported by the backend.' }: { children?: ReactNode }) { return <p className="intelligence-empty">{children}</p>; }
function Badge({ children }: { children: ReactNode }) { return <span className="intelligence-badge">{children}</span>; }
function Source({ name, model, children }: { name: keyof IntelligenceBundle; model: IntelligenceController; children: ReactNode }) {
  const state = model.states[name];
  if (state !== 'ready') return <div className="intelligence-empty" role={state === 'error' ? 'alert' : 'status'}>{state === 'loading' ? 'Loading ' + name + '…' : state === 'error' ? 'Unable to load ' + name + '. Refresh to retry.' : 'Backend data unavailable for ' + name + '. Refresh to retry.'}</div>;
  const value = model.data[name];
  return <>{value && 'truncated' in value && value.truncated && <p className="intelligence-notice">Bounded view: some records are omitted. Counts and relationships shown here may be partial.</p>}{children}</>;
}
function Traceability({ graph }: { graph: TraceGraph }) {
  const groups = [
    ['Requirements', graph.requirements], ['Features', graph.features], ['Tasks', graph.tasks],
    ['Implementations', graph.implementations.map(n => n.implementation_id)], ['Tests', graph.tests.map(n => n.test_id)], ['Evidence', graph.evidence],
  ] as const;
  return <>
    <p>Observed = a stored link without inference or evidence flags. Inferred mappings are suggestions, not proof. Evidence-backed describes a link, not completion verification.</p>
    <p><Badge>{graph.validation.valid ? 'Backend graph validation passed' : 'Invalid · backend graph validation failed'}</Badge></p>
    {graph.validation.issues.map((s, i) => <p role="alert" key={i}>{s}</p>)}
    <div className="trace-lanes">{groups.map(([name, ids]) => <section key={name}><h3>{name}</h3>{ids.length ? ids.map(id => <div className="trace-node" key={id}><code>{id}</code><small>{graph.implementations.find(n => n.implementation_id === id)?.file_path ?? graph.tests.find(n => n.test_id === id)?.file_path}</small></div>) : <Empty>No nodes</Empty>}</section>)}</div>
    <h3>Recorded relationships</h3>
    {!graph.links.length && <Empty>Unresolved: no relationships reported.</Empty>}
    <div className="trace-edges">{graph.links.map(link => <article className={'trace-edge ' + (link.is_inferred ? 'inferred' : link.evidence_backed ? 'evidence' : '')} key={link.link_id}>
      <code>{link.source_id}</code><span aria-label="links to">→</span><code>{link.target_id}</code>
      <Badge>{link.is_inferred ? 'Inferred' : link.evidence_backed ? 'Evidence-backed' : 'Observed'}</Badge>{link.is_inferred && link.evidence_backed && <Badge>Evidence-backed flag also reported</Badge>}<small>{label(link.link_type)}</small>
    </article>)}</div>
    <p className="subtle">Unresolved node mappings and per-link invalid classifications are not reported separately by this backend. Validation findings above are authoritative.</p>
  </>;
}
export function IntelligencePanel({ view, onView, model, project }: { view: IntelligenceView; onView: (view: IntelligenceView) => void; model: IntelligenceController; project: Project | null | undefined }) {
  useEffect(() => { if (project && !Object.keys(model.states).length) void model.refresh(); }, [project?.id, model.states]);
  const d = model.data;
  const source = (name: keyof IntelligenceBundle, child: ReactNode) => <Source name={name} model={model}>{child}</Source>;
  return <section className="intelligence-panel" aria-label="Project Intelligence">
    <header className="intelligence-header"><div><span className="eyebrow">PROJECT INTELLIGENCE</span><h1>{view}</h1><p>{project?.name ?? 'No project open'} · Observed backend data</p></div><button className="quiet-button" disabled={!project || model.busy} onClick={() => void model.refresh()}>{model.busy ? 'Reading…' : 'Refresh intelligence'}</button></header>
    <nav className="intelligence-nav" aria-label="Intelligence views">{intelligenceViews.map(v => <button key={v} aria-current={view === v ? 'page' : undefined} onClick={() => onView(v)}>{v}</button>)}</nav>
    <div className="intelligence-content">
      {!project ? <Empty>Open a local project to inspect its intelligence.</Empty> : <>
      {model.message && <p role="alert">{model.message}</p>}
      {view === 'Overview' && <>
        {source('info', d.info && <Facts values={{ Project: d.info.name, Root: d.info.root_path, ID: d.info.project_id, Created: d.info.created_at }} />)}
        {source('state', d.state && <><Facts values={{ Files: d.state.counts.files, Python_modules: d.state.counts.python_modules, Test_files: d.state.counts.test_files, Last_scan: d.state.scan_timestamp, Git_available: d.state.git_available }} /><details><summary>Project files ({d.state.counts.files})</summary>{d.state.files.map(f => <p key={f.relative_path}><code>{f.relative_path}</code> · {f.size} bytes · {f.is_test ? 'Test' : f.is_source ? 'Source' : f.file_type}</p>)}</details></>)}
        {source('snapshot', d.snapshot && <Facts values={{ Requirements: d.snapshot.blueprint_summary.requirements, Features: d.snapshot.blueprint_summary.features, Tasks: d.snapshot.blueprint_summary.tasks, Recorded_links: d.snapshot.traceability_summary.links, Health_warnings: d.snapshot.health_summary.warnings, Health_errors: d.snapshot.health_summary.errors, Drift_findings: d.snapshot.drift_summary.length }} />)}
        {source('graph', d.graph && <Facts values={{ Implementations_in_view: d.graph.implementations.length, Evidence_nodes_in_view: d.graph.evidence.length, Mapping_coverage: 'Not reported by backend' }} />)}
        {source('environment', d.environment && <Facts values={{ Python_version: d.environment.python_version, Python_available: d.environment.python_available, Inspection_scope: d.environment.inspection_scope }} />)}
      </>}
      {view === 'Requirements' && source('requirements', <>{!d.requirements?.items.length && <Empty>No requirements reported.</Empty>}{d.requirements?.items.map(r => <article className="intelligence-card" key={r.requirement_id}><code>{r.requirement_id}</code><h2>{r.title}</h2><p>{r.description}</p><Facts values={{ Lifecycle: r.lifecycle_status, Verification: r.status }} /><p className="subtle">Verification is the stored backend requirement status. Lifecycle completion alone does not establish verification.</p><h3>Acceptance criteria</h3>{r.acceptance_criteria.length ? <ul>{r.acceptance_criteria.map((c, i) => <li key={i}>{c}</li>)}</ul> : <Empty>No criteria reported.</Empty>}
        <Facts values={{ Implementation_references: r.implementation_references.join(', ') || 'None reported', Evidence_references: r.evidence_references.join(', ') || 'None reported' }} />
        {source('blueprint', <Facts values={{ Linked_features: d.blueprint?.features.filter(f => f.requirement_ids.includes(r.requirement_id)).map(f => f.title).join(', ') || 'None reported', Linked_tasks: d.blueprint?.tasks.filter(t => d.blueprint?.features.some(f => f.feature_id === t.feature_id && f.requirement_ids.includes(r.requirement_id))).map(t => t.title).join(', ') || 'None reported' }} />)}
      </article>)}</>)}
      {view === 'Blueprint' && source('blueprint', <>{!d.blueprint?.requirements.length && !d.blueprint?.features.length && <Empty>No blueprint records reported.</Empty>}{d.blueprint?.requirements.map(id => <details className="intelligence-card" key={id} open><summary>Requirement · {id} · {d.requirements?.items.find(r => r.requirement_id === id)?.title}</summary>{d.blueprint?.features.filter(f => f.requirement_ids.includes(id)).map(f => <details className="blueprint-feature" key={f.feature_id} open><summary>Feature · {f.title} · {f.status}</summary><p>{f.description}</p>{d.blueprint?.tasks.filter(t => t.feature_id === f.feature_id).map(t => <article className="blueprint-task" key={t.task_id}><h3>{t.title}</h3><Badge>{t.status}</Badge><p>{t.description}</p><small>{t.task_id} · Dependencies: {t.dependencies.join(', ') || 'None reported'}</small></article>)}</details>)}</details>)}{d.blueprint?.features.filter(f => !f.requirement_ids.some(id => d.blueprint?.requirements.includes(id))).map(f => <article className="intelligence-card" key={f.feature_id}><h3>Unlinked feature · {f.title}</h3><Badge>{f.status}</Badge>{d.blueprint?.tasks.filter(t => t.feature_id === f.feature_id).map(t => <p key={t.task_id}>{t.title} · {t.status} · Dependencies: {t.dependencies.join(', ') || 'None reported'}</p>)}</article>)}{d.blueprint?.tasks.filter(t => !d.blueprint?.features.some(f => f.feature_id === t.feature_id)).map(t => <p key={t.task_id}>Unlinked task · {t.title} · {t.status}</p>)}</>)}
      {view === 'Traceability' && source('graph', d.graph && <Traceability graph={d.graph} />)}
      {view === 'Environment' && <>
        {source('environment', d.environment && <Facts values={{ ...d.environment }} />)}
        {source('state', d.state && <><h2>Detected frameworks</h2><p>{d.state.frameworks.join(', ') || 'None reported'}</p><h2>Dependency declarations</h2>{d.state.dependencies.length ? d.state.dependencies.map((dep, i) => <p key={i}>{dep.name} {dep.version_specifier} · {dep.source_file}</p>) : <Empty>No declarations reported.</Empty>}</>)}
        {source('health', <><h2>Dependency inspection</h2>{!d.health?.dependency_status.length && <Empty>No dependency inspection records.</Empty>}{d.health?.dependency_status.map((dep, i) => <article className="intelligence-card" key={i}><h3>{dep.name}</h3><Facts values={{ Status: dep.status, Declared: dep.declared, Installed: dep.installed, Version: dep.installed_version, Required: dep.version_specifier, Action: dep.action }} /><p>{dep.message}</p></article>)}<h2>Test tooling and environment findings</h2><Facts values={{ Pytest_status: d.health?.dependency_status.find(dep => dep.name.toLowerCase() === 'pytest')?.status ?? 'Not reported by backend' }} />{d.health?.checks.map(c => <p key={c.check_id}><b>{c.name}</b> · {c.status} · {c.message}</p>)}</>)}
      </>}
      {view === 'Health' && source('health', <>{!d.health?.checks.length && <Empty>No health checks reported.</Empty>}{d.health?.checks.map(c => <article className="intelligence-card" key={c.check_id}><Badge>{c.severity}</Badge><h2>{c.name}</h2><p>{c.status} · {c.message}</p><p>Evidence: {c.evidence || 'Not reported'}</p></article>)}</>)}
      {view === 'Snapshot' && source('snapshot', d.snapshot && <><p>Snapshot observed at {d.snapshot.scan_timestamp}</p>{(['project_state_summary', 'blueprint_summary', 'traceability_summary', 'environment_summary', 'health_summary'] as const).map(key => <section className="intelligence-card" key={key}><h2>{label(key)}</h2><Facts values={d.snapshot![key]} /></section>)}<h2>Requirements summary</h2><Facts values={{ Total: d.snapshot.requirement_summary.total, ...d.snapshot.requirement_summary.by_verification_status }} /><h2>Drift summary</h2>{d.snapshot.drift_summary.length ? d.snapshot.drift_summary.map(f => <p key={f.requirement_id}>{f.requirement_id} · {f.state} · {f.reason}</p>) : <Empty>No drift findings in this snapshot. This does not establish absence of drift.</Empty>}</>)}
      {view === 'Timeline' && source('timeline', <>{!d.timeline?.items.length && <Empty>No timeline events recorded.</Empty>}<ol className="intelligence-timeline">{d.timeline?.items.map(e => <li key={e.event_id}><time>{e.timestamp}</time><Badge>{e.event_type}</Badge><h2>{e.title}</h2><p>{e.description}</p><small>{[...e.related_requirement_ids, ...e.related_feature_ids, ...e.related_task_ids].join(' · ')}</small></li>)}</ol></>)}
      {view === 'Drift' && source('requirements', <><p>Capture an explicit in-memory baseline, then compare after saved changes. Baselines last for this backend session. Capturing again replaces the previous baseline. Potential drift is not confirmed semantic failure.</p>{model.actionMessage && <p role="status">{model.actionMessage}</p>}{!d.requirements?.items.length && <Empty>No requirements available for a baseline.</Empty>}{d.requirements?.items.map(r => { const finding = model.findings[r.requirement_id]; return <article className="intelligence-card" key={r.requirement_id}><h2>{r.title}</h2><code>{r.requirement_id}</code><div className="intelligence-actions"><button disabled={model.busy} onClick={() => void model.baselineAction(r.requirement_id)}>{model.baselines.includes(r.requirement_id) ? 'Replace baseline' : 'Capture baseline'}</button><button disabled={model.busy || !model.baselines.includes(r.requirement_id)} onClick={() => void model.baselineAction(r.requirement_id, true)}>Compare drift</button></div>{finding ? <><Badge>{finding.state}</Badge><p>{finding.reason}</p><Facts values={{ Implementations: finding.related_implementations.map(id => d.graph?.implementations.find(n => n.implementation_id === id)?.file_path ?? id).join(', ') || 'None reported', Tasks: finding.related_tasks.join(', ') || 'None reported' }} /><small>Last explicit comparison. Compare again after saved changes.</small></> : <Empty>No comparison recorded.</Empty>}</article>; })}</>)}
      </>}
    </div>
  </section>;
}
