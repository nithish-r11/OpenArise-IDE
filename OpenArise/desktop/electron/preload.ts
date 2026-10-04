import { contextBridge, ipcRenderer } from 'electron';
import { createBridge } from '../shared/ipc';
contextBridge.exposeInMainWorld('openarise', createBridge((channel, ...args) => ipcRenderer.invoke(channel, ...args)));
