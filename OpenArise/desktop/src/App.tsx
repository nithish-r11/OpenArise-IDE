import { useEffect, useMemo, useState } from 'react';
import { AppShell } from './components/AppShell';
import { BackendClient } from './backend/client';
import type { ConnectionState } from './types/backend';

export default function App() {
  const client = useMemo(() => new BackendClient(window.openarise), []);
  const [connection, setConnection] = useState<ConnectionState>({ status: 'disconnected', reason: 'transport_not_implemented' });
  useEffect(() => {
    let active = true;
    void client.getStatus().then((state) => { if (active) setConnection(state); }).catch(() => {
      if (active) setConnection({ status: 'disconnected', reason: 'bridge_unavailable' });
    });
    return () => { active = false; };
  }, [client]);
  return <AppShell connection={connection} />;
}
