// Release QA only. Not packaged and never reachable from renderer IPC.
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readdir, readFile, realpath, mkdtemp, writeFile } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
const require = createRequire(import.meta.url);
const asar = require('@electron/asar');
const root = await realpath(process.argv[2] ?? 'release/win-unpacked');
const archive = path.join(root, 'resources/app.asar');
const version = JSON.parse(await readFile(new URL('../package.json', import.meta.url), 'utf8')).version;
const entries = asar.listPackage(archive).map(p => p.replaceAll(String.fromCharCode(92), '/'));
for (const name of ['/dist/index.html', '/dist-electron/entry.cjs', '/dist-electron/main.cjs', '/dist-electron/preload.cjs', '/build/icon.png', '/package.json']) assert.ok(entries.includes(name), 'Missing application entry: ' + name);
assert.ok(entries.every(p => !/(?:node_modules|__pycache__|\.pytest_cache|\.openarise|\.git|\.packaging|tests|coverage)(?:\/|$)|\.(?:map|log|pyc)$/.test(p)), 'Development content in app.asar');
const metadata = JSON.parse(asar.extractFile(archive, 'package.json').toString());
assert.equal(metadata.version, version);
assert.equal(metadata.main, 'dist-electron/entry.cjs');
assert.equal(metadata.productName, 'OpenArise');
assert.ok(asar.extractFile(archive, 'dist/index.html').toString().includes('<title>OpenArise</title>'));
for (const entry of entries.filter(p => /^\/(?:dist|dist-electron|build)\//.test(p) && /\.(?:html|js|cjs|css|jpeg|png)$/.test(p))) {
  assert.deepEqual(asar.extractFile(archive, path.normalize(entry.slice(1))), await readFile(new URL('..' + entry, import.meta.url)), 'Packaged bundle differs from final build: ' + entry);
}
const config = require('../electron-builder.config.cjs');
assert.equal(config.productName, 'OpenArise');
assert.equal(config.executableName, 'OpenArise');
async function files(dir) {
  const result = [];
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const target = path.join(dir, entry.name);
    assert.equal(entry.isSymbolicLink(), false, 'Linked package content: ' + target);
    if (entry.isDirectory()) result.push(...await files(target));
    else result.push(path.relative(root, target).replaceAll(String.fromCharCode(92), '/'));
  }
  return result;
}
const contents = await files(root);
const forbidden = contents.filter(p => /(?:^|\/)(?:node_modules|__pycache__|\.pytest_cache|\.openarise|\.git|\.packaging|coverage|tests|test)(?:\/|$)|(?:^|\/)\.env(?:\.|$)|\.(?:map|log|pyc|pyo)$/.test(p));
assert.deepEqual(forbidden, [], 'Unexpected development/cache/secret/test artifacts');
assert.ok(!contents.some(p => /(?:^|\/)pip(?:-|\/)/.test(p)), 'pip is not a product runtime dependency');
const resources = path.join(root, 'resources');
async function comparePythonSource(source, destination) {
  let count = 0;
  for (const entry of await readdir(source, { withFileTypes: true })) {
    if (entry.name === '__pycache__') continue;
    const sourcePath = path.join(source, entry.name), packagedPath = path.join(destination, entry.name);
    assert.equal(entry.isSymbolicLink(), false, 'Linked source: ' + sourcePath);
    if (entry.isDirectory()) count += await comparePythonSource(sourcePath, packagedPath);
    else if (entry.name.endsWith('.py')) {
      assert.deepEqual(await readFile(packagedPath), await readFile(sourcePath), 'Packaged Python differs from current source: ' + sourcePath);
      count++;
    }
  }
  return count;
}
const backendSourceFiles = await comparePythonSource(fileURLToPath(new URL('../../ai-engine/app/', import.meta.url)), path.join(resources, 'ai-engine/app'));
const hostSourceFiles = await comparePythonSource(fileURLToPath(new URL('../python/', import.meta.url)), path.join(resources, 'desktop/python'));
assert.equal(contents.filter(p => p.startsWith('resources/ai-engine/app/') && p.endsWith('.py')).length, backendSourceFiles);
assert.equal(contents.filter(p => p.startsWith('resources/desktop/python/') && p.endsWith('.py')).length, hostSourceFiles);
const python = path.join(resources, 'ai-engine/.venv/Scripts/python.exe');
const supervisor = path.join(resources, 'desktop/python/process_supervisor.py');
const env = { ...process.env, PATH: path.join(process.env.SystemRoot ?? 'C:/Windows', 'System32'), PYTHONIOENCODING: 'utf-8' };
delete env.PYTHONHOME; delete env.PYTHONPATH;
const project = await mkdtemp(path.join(os.tmpdir(), 'openarise-phase8-package-'));
const original = 'print("PACKAGED_PYTHON_RUN")\n';
const saved = '# Saved by bundled real file host\n' + original;
await writeFile(path.join(project, 'main.py'), original);
await writeFile(path.join(project, 'test_main.py'), 'def test_packaged_runtime():\n    assert 2 + 2 == 4\n');
function run(args, input = '') {
  return new Promise((resolve, reject) => {
    const child = spawn(python, args, { cwd: project, env, shell: false, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'] });
    let stdout = '', stderr = '';
    const timeout = setTimeout(() => { child.kill(); reject(new Error('Packaged runtime check timed out')); }, 30000);
    child.stdout.on('data', data => { stdout += data; }); child.stderr.on('data', data => { stderr += data; });
    child.once('error', error => { clearTimeout(timeout); reject(error); });
    child.once('close', code => { clearTimeout(timeout); code === 0 ? resolve({ stdout, stderr }) : reject(new Error('Packaged Python exit ' + code + ': ' + stderr.slice(0, 1000))); });
    child.stdin.end(input);
  });
}
const imported = await run(['-I', '-B', '-c', 'import sys,pytest,pydantic,requests;print(sys.executable);print(pytest.__file__);print(pydantic.__file__);print(requests.__file__)']);
assert.ok(imported.stdout.trim().split(/\r?\n/).every(line => line.toLowerCase().startsWith(python.substring(0, python.lastIndexOf(path.sep)).toLowerCase())), 'Imports escaped bundled Python');
const revision = createHash('sha256').update(original).digest('hex');
const fileRequests = [
  { id: 'info', method: 'info', params: {} },
  { id: 'read', method: 'read', params: { path: 'main.py' } },
  { id: 'save', method: 'save', params: { path: 'main.py', content: saved, revision } },
  { id: 'environment', method: 'environment', params: {} },
  { id: 'shutdown', method: 'shutdown', params: {} },
];
const fileResult = await run(['-I', '-B', '-u', path.join(resources, 'desktop/python/file_host.py'), project], fileRequests.map(r => JSON.stringify(r)).join('\n') + '\n');
const fileResponses = fileResult.stdout.trim().split(/\r?\n/).map(line => JSON.parse(line));
assert.equal(fileResponses.length, fileRequests.length);
assert.ok(fileResponses.every(r => r.ok), 'Bundled file host rejected an operation');
assert.equal(await readFile(path.join(project, 'main.py'), 'utf8'), saved.replaceAll('\n', '\r\n')); // Existing Windows writer uses CRLF.
assert.equal(fileResponses.find(r => r.id === 'environment').data.executable.toLowerCase(), python.toLowerCase());
const requests = ['get_project_information', 'get_environment_status', 'shutdown'].map((method, i) => ({ request_id: 'package-' + i, method, params: {} }));
const backend = await run(['-I', '-B', '-u', path.join(resources, 'desktop/python/agent_host.py'), project], requests.map(r => JSON.stringify(r)).join('\n') + '\n');
const responses = backend.stdout.trim().split(/\r?\n/).map(line => JSON.parse(line)).filter(r => r.request_id);
assert.equal(responses.length, requests.length);
assert.ok(responses.every(r => r.success), 'Bundled real backend failed');
const executed = await run(['-I', '-B', '-u', supervisor, python, '-B', path.join(project, 'main.py')]);
assert.match(executed.stdout, /PACKAGED_PYTHON_RUN/);
const tested = await run(['-I', '-B', '-u', supervisor, python, '-B', '-m', 'pytest', '-q']);
assert.match(tested.stdout, /1 passed/);
console.log(JSON.stringify({ status: 'VERIFIED', root, version, asarEntries: entries.length, packageFiles: contents.length, backendSourceFiles, hostSourceFiles,
  applicationArchiveSHA256: createHash('sha256').update(await readFile(archive)).digest('hex'),
  checks: ['clean package contents', 'identity/version', 'current backend/host source bytes', 'isolated bundled imports', 'real file read/save', 'real backend project/environment', 'supervised Python', 'real pytest: 1 passed'],
  minimalPATH: env.PATH, project, liveAI: 'NOT VERIFIED', electronLaunch: 'SEPARATE CHECK REQUIRED' }, null, 2));