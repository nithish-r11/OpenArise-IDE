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
    // Monaco is lazy-loaded. Discover its registrations before opening a file,
    // rather than invalidating an in-flight editor import on the first dev use.
    optimizeDeps: { include: [
      'monaco-editor/editor/editor.api.js',
      'monaco-editor/editor/contrib/find/browser/findController.js',
      'monaco-editor/editor/contrib/folding/browser/folding.js',
      'monaco-editor/editor/standalone/browser/quickAccess/standaloneGotoLineQuickAccess.js',
      ...['python', 'typescript', 'javascript', 'html', 'css', 'markdown', 'yaml', 'ini', 'xml']
        .map(language => `monaco-editor/languages/definitions/${language}/register.js`),
      'monaco-editor/languages/features/json/register.js',
    ] },
    base: './',
    server: { host: '127.0.0.1', port: 5173, strictPort: true, watch: { ignored: ['**/.packaging/**', '**/release/**', '**/dist/**', '**/dist-electron/**', '**/python/**'] } },
  };
});
