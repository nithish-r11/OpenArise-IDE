import type { DesktopBridge } from './backend';
declare global { interface Window { openarise?: DesktopBridge } }
