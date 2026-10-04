import { build } from 'esbuild';
await build({ entryPoints: ['electron/entry.ts', 'electron/main.ts', 'electron/preload.ts'], outdir: 'dist-electron', outExtension: { '.js': '.cjs' }, bundle: true, platform: 'node', format: 'cjs', target: 'node22', external: ['electron'] });
