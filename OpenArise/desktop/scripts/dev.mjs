import { spawn } from 'node:child_process';
import { createServer } from 'vite';
import electron from 'electron';
import './build-electron.mjs';
const server = await createServer();
await server.listen();
server.printUrls();
const child = spawn(electron, ['.', '--openarise-dev'], { stdio: 'inherit', windowsHide: true });
let closing = false;
async function close(code = 0) {
  if (closing) return;
  closing = true;
  if (child.exitCode === null) child.kill();
  await server.close();
  process.exitCode = code;
}
child.on('exit', (code) => void close(code ?? 0));
child.on('error', (error) => { console.error(error.message); void close(1); });
process.on('SIGINT', () => void close());
process.on('SIGTERM', () => void close());
