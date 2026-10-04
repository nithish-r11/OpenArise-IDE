import { describe, expect, it, vi } from 'vitest';
import { readFileSync, readdirSync } from 'node:fs';
import path from 'node:path';
import { DEV_URL, trustedPage, windowOptions } from '../electron/security';
describe('Electron security', () => {
  it('uses isolated, sandboxed renderer and native window controls', () => {
    expect(windowOptions('/safe/preload.cjs')).toMatchObject({
      minWidth: 760, minHeight: 540,
      webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true, webSecurity: true, webviewTag: false },
    });
    expect(windowOptions('/safe/preload.cjs')).not.toHaveProperty('frame', false);
  });
  it('trusts only the exact application page, including optional anchor', () => {
    expect(trustedPage(DEV_URL + '#workspace', DEV_URL)).toBe(true);
    for (const url of ['https://evil.test/', DEV_URL + 'evil', 'http://localhost:5173/', DEV_URL + '?source=evil', 'invalid']) expect(trustedPage(url, DEV_URL)).toBe(false);
    expect(trustedPage('file:///app/dist/other.html', 'file:///app/dist/index.html')).toBe(false);
  });
  it('bundles preload with only the Electron runtime import', () => {
    // Source bridge exposure is additionally exercised in the real Electron smoke test.
    const preload = readFileSync('electron/preload.ts', 'utf8');
    expect(preload).toContain("exposeInMainWorld('openarise'");
    expect(preload).not.toMatch(/exposeInMainWorld\([^,]+,\s*ipcRenderer\)/);
  });
  it('keeps Node and Electron imports and globals out of renderer sources', () => {
    function visit(dir: string): string[] {
      return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => entry.isDirectory() ? visit(path.join(dir, entry.name)) : [path.join(dir, entry.name)]);
    }
    for (const file of visit('src').filter((file) => /\.[tj]sx?$/.test(file))) {
      const source = readFileSync(file, 'utf8');
      expect(source, file).not.toMatch(/from\s+['"](?:node:|electron|fs['"]|child_process)/);
      expect(source, file).not.toMatch(/\brequire\s*\(|\bprocess\.(?:env|execPath)|\bipcRenderer\b/);
    }
  });
});
