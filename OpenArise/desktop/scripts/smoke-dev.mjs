import { createServer } from 'vite';
import { spawn } from 'node:child_process';
import electron from 'electron';

const server = await createServer();
try {
  await server.listen();
  const page = await (await fetch('http://127.0.0.1:5173/')).text();
  if (!page.includes("'nonce-") || !page.includes('nonce=')) throw new Error('Development CSP nonce missing.');
  const child = spawn(electron, ['tests/electron-smoke.cjs', '--openarise-dev'], { stdio: 'inherit', windowsHide: true });
  process.exitCode = await new Promise((resolve, reject) => {
    child.once('error', reject);
    child.once('exit', (code) => resolve(code ?? 1));
  });
} finally {
  await server.close();
}
