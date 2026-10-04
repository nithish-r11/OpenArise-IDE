import { useEffect, useRef, useState } from 'react';
import type { useTerminal } from '../../workspace/useTerminal';
import { parseCommand } from '../../../shared/terminal-ipc';
export function TerminalPanel({ terminal, blocked, revisions, fileError }: {
  terminal: ReturnType<typeof useTerminal>; blocked: boolean; revisions: Record<string, string>; fileError: string;
}) {
  const [expanded, setExpanded] = useState(true);
  const [panel, setPanel] = useState<'terminal' | 'problems'>('terminal');
  const [input, setInput] = useState('');
  const output = useRef<HTMLPreElement>(null);
  const sessions = terminal.snapshot?.sessions ?? [];
  const active = sessions.find(s => s.id === terminal.active);
  const running = active?.state === 'starting' || active?.state === 'running';
  const problems = [...new Set([terminal.error, fileError, ...sessions.map(s => s.problem)].filter(Boolean))];
  useEffect(() => { if (output.current) output.current.scrollTop = output.current.scrollHeight; }, [active?.output]);
  const control = (operation: 'stop' | 'clear' | 'close' | 'restart') => {
    if (active) void terminal.action({ operation, sessionId: active.id });
  };
  const execute = () => {
    const cmd = parseCommand(input);
    if (!cmd) { terminal.setError('Allowed commands: python --version, python <opened saved file.py>, pytest. Shell syntax is not supported.'); return; }
    if (blocked) { terminal.setError('Save or discard unsaved changes and resolve save errors before running.'); return; }
    if (cmd.kind === 'run' && !revisions[cmd.path]) { terminal.setError('Open and review that Python file in the editor before running.'); return; }
    void terminal.action({ operation: 'execute', sessionId: active?.id, command: input, ...(cmd.kind === 'run' ? { revision: revisions[cmd.path] } : {}) });
  };
  return <section className={'terminal-panel' + (expanded ? '' : ' collapsed')} aria-label="Integrated terminal">
    <div className="terminal-heading">
      <button aria-expanded={expanded} onClick={() => setExpanded(!expanded)}>TERMINAL {expanded ? '⌄' : '⌃'}</button>
      <button className={panel === 'problems' ? 'selected' : ''} onClick={() => { setPanel(panel === 'problems' ? 'terminal' : 'problems'); setExpanded(true); }}>Problems {problems.length > 0 && <b>{problems.length}</b>}</button>
      <button className="new-terminal" disabled={!terminal.snapshot || terminal.pending} onClick={() => { setExpanded(true); setPanel('terminal'); void terminal.action({ operation: 'create' }); }}>+ Session</button>
    </div>
    {expanded && <>
      {panel === 'problems' ? <div className="problems-list" role="log">{problems.length ? problems.map(p => <p key={p}>{p}</p>) : <p>No reported problems.</p>}</div> : <>
        <div className="terminal-sessions" role="tablist" aria-label="Terminal sessions">
          {sessions.map((s, i) => <button role="tab" aria-selected={active?.id === s.id} key={s.id} onClick={() => terminal.setActive(s.id)}>Terminal {i + 1}<span className={'process-state ' + s.state}>{s.state}</span></button>)}
        </div>
        {active ? <>
          <div className="terminal-tools"><span title={'Session: ' + active.id + '\nRoot: ' + active.root + '\nStarted: ' + (active.startedAt ?? 'Not started')}>{active.command || 'Ready for a command'} · {active.state}{active.exitCode !== null ? ' · exit ' + active.exitCode : ''}{active.testResult ? ' · pytest ' + active.testResult : ''}</span>
            <button disabled={!running || terminal.pending} onClick={() => control('stop')}>Stop</button>
            <button disabled={terminal.pending} onClick={() => control('clear')}>Clear</button>
            <button disabled={terminal.pending} onClick={() => control('restart')}>Restart</button>
            <button disabled={terminal.pending} onClick={() => control('close')}>Close</button>
          </div>
          <pre className="terminal-output" ref={output} aria-label="Terminal output">{active.truncated && <span className="subtle">Earlier output truncated (128 KiB limit).{'\n'}</span>}{active.output.map((part, i) => <span className={part.stream} key={i}>{part.text}</span>)}</pre>
        </> : <div className="terminal-empty">Run a saved Python file or open a session.<small>Commands: python --version · python &lt;opened file.py&gt; · pytest</small></div>}
        <form className="terminal-input" onSubmit={event => { event.preventDefault(); execute(); }}><span>›_</span><input aria-label="Terminal command" maxLength={2100} value={input} onChange={event => setInput(event.target.value)} placeholder="python --version" disabled={!terminal.snapshot || running || terminal.pending} /><button disabled={!terminal.snapshot || running || terminal.pending || blocked}>Execute</button></form>
      </>}
      {(terminal.error || blocked) && <p className="terminal-error" role="alert">{terminal.error || 'Save or discard unsaved changes and resolve save errors before running.'}</p>}
    </>}
  </section>;
}
