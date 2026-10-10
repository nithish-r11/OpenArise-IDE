import { useCallback, useEffect, useRef, useState } from 'react';
import type { Project } from '../types/project';
import type { TerminalBridge, TerminalRequest, TerminalSnapshot } from '../types/terminal';
export function useTerminal(project: Project | undefined, bridge?: TerminalBridge) {
  const [snapshot, setSnapshot] = useState<TerminalSnapshot | null>(null);
  const [active, setActive] = useState('');
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);
  const current = useRef(project?.id);
  current.current = project?.id;
  const busy = useRef(false);
  const send = useCallback(async (request: Omit<TerminalRequest, 'projectId'>) => {
    const id = project?.id;
    if (!id || !bridge) { setError('Open a project in the desktop app to use the terminal.'); return; }
    try {
      const result = await bridge.request({ ...request, projectId: id });
      if (current.current !== id) return;
      if (result.ok) {
        setSnapshot(result.data);
        setActive(previous => result.data.sessions.some(s => s.id === previous) ? previous : result.data.sessions.at(-1)?.id ?? '');
        return result.data;
      }
      setError(result.message);
    } catch { if (current.current === id) setError('Terminal connection unavailable.'); }
  }, [project?.id, bridge]);
  useEffect(() => {
    setSnapshot(null); setActive(''); setError('');
    if (!project || !bridge) return;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => { await send({ operation: 'snapshot' }); if (!disposed) timer = setTimeout(() => void poll(), 500); };
    void poll();
    return () => { disposed = true; clearTimeout(timer); };
  }, [send, project?.id, bridge]);
  const action = async (request: Omit<TerminalRequest, 'projectId'>) => {
    if (busy.current) return;
    busy.current = true; setPending(true); setError('');
    try {
      let sessionId = request.sessionId;
      if (['execute', 'executeCapability'].includes(request.operation) && !sessionId) {
        const data = await send({ operation: 'create' });
        sessionId = data?.sessions.at(-1)?.id;
        if (!sessionId) return;
      }
      const data = await send({ ...request, ...(sessionId ? { sessionId } : {}) });
      if (request.operation === 'create' && data) setActive(data.sessions.at(-1)?.id ?? '');
    } finally { busy.current = false; setPending(false); }
  };
  return { snapshot, active, setActive, error, setError, pending, action };
}
