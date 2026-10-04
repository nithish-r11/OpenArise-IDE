import type { ConnectionState } from '../types/backend';
export function StatusBar({ connection }: { connection: ConnectionState }) {
  return <footer className="status-bar" role="status">
    <span><span className="status-dot" /> Backend not connected</span>
    <span className="status-detail">{connection.reason === 'bridge_unavailable' ? 'Browser preview' : 'Transport deferred'}</span>
    <span className="status-right">Desktop foundation <span className="status-divider">|</span> Phase 1</span>
  </footer>;
}
