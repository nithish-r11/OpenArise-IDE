import { randomBytes } from 'node:crypto';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig(({ command }) => {
  const nonce = randomBytes(18).toString('base64');
  return {
    plugins: [
      react(),
      ...(command === 'serve' ? [{
        name: 'development-csp',
        transformIndexHtml: {
          order: 'pre' as const,
          handler: (html: string) => html
            .replace("script-src 'self'", "script-src 'self' 'nonce-" + nonce + "'")
            .replace("connect-src 'none'", "connect-src 'self' ws://127.0.0.1:5173"),
        },
      }] : []),
    ],
    html: command === 'serve' ? { cspNonce: nonce } : undefined,
    base: './',
    server: { host: '127.0.0.1', port: 5173, strictPort: true, watch: { ignored: ['**/.packaging/**', '**/release/**', '**/dist/**', '**/dist-electron/**', '**/python/**'] } },
  };
});
