import { validPath } from './project-ipc';
export interface ProjectCommand {
  id: string; kind: 'node_script' | 'pytest'; directory: string; label: string;
  manager: string; action: 'test' | 'build'; manifest: string; revision: string;
  script: string; approvalRequired: boolean; supported: boolean; reason: string;
}
export interface ProjectCapabilities {
  projectType: 'full-stack' | 'frontend' | 'backend' | 'unknown'; frontend: string[]; backend: string[];
  languages: string[]; dependencyManagers: string[]; entryPoints: string[]; manifests: string[];
  commands: ProjectCommand[]; warnings: string[]; observedAt: string; interpretation: string;
  runCandidates: string[];
}
const object = (v: unknown): v is Record<string, any> => !!v && typeof v === 'object' && !Array.isArray(v);
const text = (v: unknown, max = 1000) => typeof v === 'string' && v.length <= max && !/[\x00-\x1f]/.test(v);
const strings = (v: unknown, max: number, paths = false) => Array.isArray(v) && v.length <= max && v.every(x => text(x, 2048) && (!paths || validPath(x)));
export function validProjectCommand(v: unknown): v is ProjectCommand {
  return object(v) && Object.keys(v).sort().join() === 'action,approvalRequired,directory,id,kind,label,manager,manifest,reason,revision,script,supported'
    && /^(?:[a-f0-9]{24}|python-tests)$/.test(v.id) && ['node_script', 'pytest'].includes(v.kind)
    && (v.directory === '.' || validPath(v.directory)) && text(v.label) && text(v.manager, 20)
    && ['test', 'build'].includes(v.action) && validPath(v.manifest)
    && (v.revision === '' || typeof v.revision === 'string' && /^[a-f0-9]{64}$/.test(v.revision))
    && text(v.script) && typeof v.approvalRequired === 'boolean' && typeof v.supported === 'boolean' && text(v.reason);
}
export function validCapabilities(v: unknown): v is ProjectCapabilities {
  return object(v) && Object.keys(v).sort().join() === 'backend,commands,dependencyManagers,entryPoints,frontend,interpretation,languages,manifests,observedAt,projectType,runCandidates,warnings'
    && ['full-stack', 'frontend', 'backend', 'unknown'].includes(v.projectType)
    && ['frontend', 'backend', 'languages', 'dependencyManagers'].every(k => strings(v[k], 20))
    && strings(v.entryPoints, 20, true) && strings(v.manifests, 30, true) && strings(v.warnings, 10) && strings(v.runCandidates, 20)
    && text(v.observedAt, 40) && !Number.isNaN(Date.parse(v.observedAt)) && text(v.interpretation)
    && Array.isArray(v.commands) && v.commands.length <= 20 && v.commands.every(validProjectCommand);
}
