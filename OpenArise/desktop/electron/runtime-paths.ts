import { app } from 'electron';
import path from 'node:path';

// Python cannot import source from an Electron asar archive. Windows builds
// place the fixed backend and interpreter under process.resourcesPath.
const resources = () => app?.isPackaged ? process.resourcesPath : path.resolve(__dirname, '../..');
export const backendRoot = () => path.join(resources(), 'ai-engine');
export const desktopPython = (script: string) => path.join(resources(), 'desktop', 'python', script);
export const backendPython = () => path.join(backendRoot(), '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
