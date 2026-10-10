import type { ProjectCapabilities as Capabilities, ProjectCommand } from '../../shared/capabilities';
export function ProjectCapabilities({ data, loading, blocked, onCommand }: {
  data?: Capabilities; loading: boolean; blocked: boolean; onCommand: (command: ProjectCommand) => void;
}) {
  if (loading) return <p role="status">Scanning project capabilities…</p>;
  if (!data) return <p>Capabilities not loaded. Refresh project state to retry.</p>;
  return <div className="project-capabilities" aria-label="Detected project capabilities">
    <strong>{data.projectType === 'unknown' ? 'Project type not identified' : data.projectType + ' project'}</strong>
    {!!data.frontend.length && <p>Frontend: {data.frontend.join(' · ')}</p>}
    {!!data.backend.length && <p>Backend: {data.backend.join(' · ')}</p>}
    <p>{data.languages.join(' · ') || 'No supported language detected'}</p>
    {!!data.dependencyManagers.length && <p>Manifests: {data.dependencyManagers.join(' · ')}</p>}
    {!!data.entryPoints.length && <details><summary>Candidate entry points</summary>{data.entryPoints.map(p => <code key={p}>{p}</code>)}</details>}
    {!!data.runCandidates.length && <details><summary>Candidate run commands</summary>{data.runCandidates.map(command => <p key={command}>{command}</p>)}</details>}
    {!!data.commands.length && <details className="project-commands" open><summary>Project commands</summary>{data.commands.map(command => <div key={command.id}>
      <button disabled={blocked || !command.supported} title={command.reason} onClick={() => onCommand(command)}>{command.label}{command.approvalRequired ? ' ↗' : ''}</button>
      {!command.supported && <small>{command.reason}</small>}
    </div>)}<small>Execution uses your user privileges. Agent verification is separate.</small></details>}
    {data.warnings.map(w => <p role="status" key={w}>{w}</p>)}
    <small title={data.observedAt}>Static observations · refresh after changes</small>
  </div>;
}
