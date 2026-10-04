import { cp, mkdir, readFile, realpath, rm, stat } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const desktop = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const target = path.resolve(desktop, '.packaging/windows-python');
const relative = path.relative(desktop, target);
if (relative.startsWith('..') || path.isAbsolute(relative) || relative === '') throw new Error('Runtime target escaped the desktop workspace.');
if (process.platform !== 'win32' || process.arch !== 'x64') throw new Error('Windows x64 runtime packaging requires a Windows x64 build host.');
const cfgPath = path.resolve(desktop, '../ai-engine/.venv/pyvenv.cfg');
const cfg = await readFile(cfgPath, 'utf8');
const match = /^home\s*=\s*(.+)$/m.exec(cfg);
if (!match) throw new Error('The existing backend Python environment has no base installation.');
const base = path.resolve(match[1].trim());
const packages = path.resolve(desktop, '../ai-engine/.venv/Lib/site-packages');
for (const required of [path.join(base, 'python.exe'), path.join(base, 'python313.dll'), path.join(base, 'Lib'), path.join(base, 'DLLs'), packages]) {
  if (!existsSync(required)) throw new Error('Packaging dependency missing: ' + required);
}
await mkdir(path.dirname(target), { recursive: true });
const parent = await realpath(path.dirname(target));
const desktopReal = await realpath(desktop);
if (parent.toLowerCase() !== path.join(desktopReal, '.packaging').toLowerCase()) throw new Error('Runtime staging parent must be inside the desktop workspace.');
if (existsSync(target) && (await realpath(target)).toLowerCase() !== path.join(parent, 'windows-python').toLowerCase()) throw new Error('Runtime staging target must not be a link.');
await rm(target, { recursive: true, force: true });
await mkdir(target, { recursive: true });
const include = source => !source.split(path.sep).some(part => ['__pycache__', '.pytest_cache', 'tests', 'test'].includes(part)) && !/\.(?:pyc|pyo|log)$/i.test(source);
const baseLib = path.join(base, 'Lib');
// The source venv is authoritative. Do not merge global site-packages into it.
const includeStdlib = source => include(source) && !['site-packages', 'idlelib', 'turtledemo', 'ensurepip'].includes(path.relative(baseLib, source).split(path.sep)[0]);
const includePackage = source => include(source) && !/^pip(?:-|$)/.test(path.relative(packages, source).split(path.sep)[0]);
await cp(baseLib, path.join(target, 'Lib'), { recursive: true, filter: includeStdlib });
await cp(path.join(base, 'DLLs'), path.join(target, 'DLLs'), { recursive: true, filter: include });
for (const name of ['python.exe', 'pythonw.exe', 'LICENSE.txt', 'python3.dll', 'python313.dll', 'vcruntime140.dll', 'vcruntime140_1.dll']) {
  const source = path.join(base, name);
  if (existsSync(source)) await cp(source, path.join(target, name));
}
await cp(packages, path.join(target, 'Lib/site-packages'), { recursive: true, filter: includePackage, force: true });
const result = await stat(path.join(target, 'python.exe'));
if (!result.isFile()) throw new Error('Packaged Python executable is missing.');
process.stdout.write('Prepared isolated Python runtime at ' + target + '\n');
