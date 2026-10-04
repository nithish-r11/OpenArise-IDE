export const DEV_URL = 'http://127.0.0.1:5173/';
export function windowOptions(preload: string) {
  return {
    width: 1320, height: 880, minWidth: 760, minHeight: 540, backgroundColor: '#0b0e16',
    title: 'OpenArise', show: false, autoHideMenuBar: true,
    webPreferences: { preload, contextIsolation: true, nodeIntegration: false, sandbox: true, webSecurity: true, webviewTag: false, navigateOnDragDrop: false },
  };
}
export function trustedPage(actual: string, expected: string): boolean {
  try { const url = new URL(actual); url.hash = ''; return url.href === expected; }
  catch { return false; }
}
