import { spawnSync } from 'node:child_process';
import path from 'node:path';
const python = path.resolve('../ai-engine/.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const result = spawnSync(python, ['-I', '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-p', 'test_*.py', '-v'], { stdio: 'inherit', windowsHide: true });
process.exitCode = result.status ?? 1;
