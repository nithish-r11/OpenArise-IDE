// Strict allowlisted DTO validation. No project analysis or relationship inference.
type Check = (v: unknown) => boolean;
const text: Check = v => typeof v === 'string' && v.length <= 800 && !/[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(v);
const bool: Check = v => typeof v === 'boolean';
const count: Check = v => Number.isSafeInteger(v) && Number(v) >= 0 && Number(v) <= 1e9;
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v);
const nullable = (check: Check): Check => v => v === null || check(v);
const array = (check: Check): Check => v => Array.isArray(v) && v.length <= 100 && v.every(check);
const shape = (fields: Record<string, Check>): Check => v => object(v) && Object.keys(v).sort().join() === Object.keys(fields).sort().join() && Object.entries(fields).every(([key, check]) => check(v[key]));
const dictionary = (keys: string[], check: Check): Check => v => object(v) && Object.keys(v).every(k => keys.includes(k) && check(v[k]));
const enumeration = (...values: string[]): Check => v => typeof v === 'string' && values.includes(v);
const strings = array(text), maybe = nullable(text);
const lifecycle = enumeration('pending', 'in_progress', 'completed', 'blocked');
const verification = enumeration('PENDING', 'PARTIALLY_VERIFIED', 'VERIFIED', 'NOT_VERIFIED', 'INCONCLUSIVE');
const info = shape({ project_id: text, root_path: text, name: text, created_at: text });
const environment = shape({ python_available: bool, python_executable: maybe, python_version: maybe, virtualenv_present: bool, virtualenv_path: maybe, virtualenv_usable: bool, platform: maybe, git_available: bool, inspection_scope: enumeration('current_environment', 'project_virtualenv_detected_but_not_inspected') });
const requirement = shape({ requirement_id: text, title: text, description: text, lifecycle_status: lifecycle, status: verification, acceptance_criteria: strings, implementation_references: strings, evidence_references: strings });
const feature = shape({ feature_id: text, title: text, description: text, status: lifecycle, requirement_ids: strings });
const task = shape({ task_id: text, feature_id: text, title: text, description: text, status: lifecycle, dependencies: strings });
const implementation = shape({ implementation_id: text, file_path: text, module_name: maybe, symbol_name: maybe, symbol_type: maybe, feature_id: maybe, requirement_ids: strings, evidence_ids: strings });
const test = shape({ test_id: text, file_path: text, test_name: maybe, requirement_ids: strings, evidence_ids: strings });
const link = shape({ link_id: text, source_id: text, target_id: text, link_type: enumeration('requirement_to_feature', 'feature_to_task', 'task_to_implementation', 'requirement_to_implementation', 'implementation_to_test', 'test_to_evidence', 'requirement_to_evidence'), created_at: text, evidence_backed: bool, is_inferred: bool });
const drift = shape({ requirement_id: text, state: enumeration('NO_DRIFT', 'POTENTIAL_DRIFT', 'CONFIRMED_STRUCTURAL_DRIFT', 'UNRESOLVED'), reason: text, related_implementations: strings, related_tasks: strings });
const timeline = shape({ event_id: text, timestamp: text, event_type: enumeration('PROJECT_CREATED', 'PROJECT_SCANNED', 'BLUEPRINT_CREATED', 'REQUIREMENT_CREATED', 'REQUIREMENT_UPDATED', 'FEATURE_CREATED', 'TASK_CREATED', 'IMPLEMENTATION_MAPPED', 'EVIDENCE_LINKED', 'HEALTH_CHECKED', 'DRIFT_DETECTED', 'AGENT_STATE_CHANGED'), title: text, description: text, related_requirement_ids: strings, related_feature_ids: strings, related_task_ids: strings });
const bounded = shape({ project_name: text, total_files: count, requirements_count: count, traceability_nodes: count, health_issues: count, missing_dependencies: count });
const withOllama = (check: Check): Check => value => {
  if (!object(value)) return false;
  const { ollama, ...rest } = value;
  return check(rest) && (!('ollama' in value) || shape({ status: enumeration('ready', 'ollama_unavailable', 'model_unavailable'),
    message: text, model: v => text(v) && String(v).length <= 200,
    timeout_seconds: v => count(v) && Number(v) >= 30 && Number(v) <= 900 })(ollama));
};
const snapshot = withOllama(shape({ project_id: text, project_name: text, scan_timestamp: text,
  project_state_summary: dictionary(['total_files', 'python_modules', 'dependencies_declared'], count),
  blueprint_summary: dictionary(['requirements', 'features', 'tasks'], count),
  traceability_summary: dictionary(['nodes', 'links'], count),
  environment_summary: dictionary(['python_available', 'virtualenv_present', 'git_available'], bool),
  health_summary: dictionary(['total_checks', 'blocked', 'errors', 'warnings', 'missing_dependencies'], count),
  requirement_summary: shape({ total: count, by_verification_status: dictionary(['PENDING', 'PARTIALLY_VERIFIED', 'VERIFIED', 'NOT_VERIFIED', 'INCONCLUSIVE'], count) }),
  drift_summary: array(drift), intelligence_summary: v => bounded(v) || v === 'Context unavailable' || object(v) && Object.keys(v).length === 0 }));
export const intelligenceChecks: Record<string, Check> = {
  get_project_information: info,
  get_project_state: shape({ project_info: info, scan_timestamp: text, git_available: bool, counts: shape({ files: count, python_modules: count, test_files: count }), files: array(shape({ relative_path: text, file_type: text, size: count, is_test: bool, is_source: bool, is_config: bool })), frameworks: strings, dependencies: array(shape({ name: text, version_specifier: maybe, source_file: text })), truncated: bool }),
  get_requirements: shape({ items: array(requirement), total: count, truncated: bool }),
  get_blueprint: shape({ project_id: text, project_name: text, description: text, generated_at: text, requirements: strings, features: array(feature), tasks: array(task), truncated: bool }),
  get_traceability_graph: shape({ project_id: text, requirements: strings, features: strings, tasks: strings, evidence: strings, implementations: array(implementation), tests: array(test), links: array(link), validation: shape({ valid: bool, issues: strings }), truncated: bool }),
  get_environment_status: environment,
  get_health_report: shape({ project_id: text, generated_at: text, environment, checks: array(shape({ check_id: text, name: text, status: text, severity: enumeration('INFO', 'WARNING', 'ERROR', 'BLOCKED'), message: text, evidence: maybe })), dependency_status: array(shape({ name: text, version_specifier: maybe, declared: bool, installed: bool, installed_version: maybe, status: enumeration('declared', 'installed', 'missing', 'version_mismatch', 'unknown', 'inspection_not_available'), source_file: maybe, action: enumeration('INSTALL_REQUIRED', 'REVIEW_REQUIRED', 'READY', 'BLOCKED'), message: maybe })), truncated: bool }),
  get_intelligence_snapshot: snapshot, refresh_workspace: snapshot,
  get_timeline: shape({ items: array(timeline), total: count, truncated: bool }),
  get_drift_report: drift,
  create_requirement_baseline: shape({ requirement_id: text, captured: v => v === true }),
};
