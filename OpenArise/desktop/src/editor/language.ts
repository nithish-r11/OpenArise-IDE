/** Syntax selection only; project analysis belongs to the backend capability layer. */
export function editorLanguage(path: string): string {
  const extension = path.split('.').at(-1)?.toLowerCase();
  return ({ py: 'python', pyw: 'python', ts: 'typescript', tsx: 'typescript', js: 'javascript',
    jsx: 'javascript', mjs: 'javascript', cjs: 'javascript', json: 'json', html: 'html', css: 'css',
    scss: 'scss', md: 'markdown', yaml: 'yaml', yml: 'yaml', toml: 'ini', ini: 'ini', cfg: 'ini', svg: 'xml' } as Record<string, string>)[extension ?? ''] ?? 'plaintext';
}
