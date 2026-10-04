import { intelligenceChecks } from './intelligence-response';
import type { BackendResponse } from '../src/types/backend';
const obj = (v: unknown): v is Record<string, any> => !!v && typeof v === 'object' && !Array.isArray(v);
const keys = (v: Record<string, any>, names: string) => Object.keys(v).sort().join() === names.split(',').sort().join();
const id = (v: unknown) => typeof v === 'string' && /^[A-Za-z0-9_-]{1,128}$/.test(v);
const text = (v: unknown, max = 500) => typeof v === 'string' && v.length <= max && !/[\x00-\x08\x0b\x0c\x0e-\x1f]/.test(v);
const number = (v: unknown) => Number.isSafeInteger(v) && Number(v) >= 0 && Number(v) <= 1e9;
const states = ['IDLE', 'THINKING', 'PLANNING', 'EXECUTING', 'OBSERVING', 'FAILED', 'RECOVERING', 'VERIFYING', 'COMPLETED', 'PERMISSION_REQUIRED', 'APPROVED', 'DENIED', 'CANCELLED'];
const statuses = ['success', 'unverified', 'failure', 'permission_required', 'approved', 'denied', 'cancelled'];
const actions = ['running', 'permission_required', 'approved', 'completed', 'failed', 'denied', 'cancelled'];
const toolNames = ['read_file', 'write_file', 'execute_python', 'execute_tests', 'unregistered_tool'];
const timestamp = (v: unknown) => typeof v === 'string' && v.length <= 40 && !Number.isNaN(Date.parse(v));
export function validAgentEnvelope(value: unknown, commandId: string, method: string): value is BackendResponse {
  if (!obj(value) || !keys(value, 'request_id,success,action_state,data,error,events') || value.request_id !== commandId || !Array.isArray(value.events) || value.events.length > 200) return false;
  if (value.success === false) return value.data === null && value.action_state === null && value.events.length === 0
    && obj(value.error) && keys(value.error, 'success,code,message,details') && value.error.success === false
    && ['project_not_found', 'invalid_project_root', 'project_state_unavailable', 'environment_unavailable', 'unsupported_operation', 'permission_required', 'verification_unavailable', 'internal_error', 'invalid_request', 'request_not_found', 'action_conflict', 'service_closed'].includes(value.error.code)
    && text(value.error.message) && obj(value.error.details) && Object.keys(value.error.details).length === 0;
  if (value.success !== true || value.error !== null || !actions.includes(value.action_state) || !obj(value.data)) return false;
  const data = value.data;
  if (method === 'shutdown') return keys(data, 'closed') && data.closed === true && value.events.length === 0;
  if (intelligenceChecks[method]?.(data) && value.events.length === 0 && value.action_state === 'completed') return true;
  if (method === 'get_intelligence_snapshot') {
    if (!keys(data, 'intelligence_summary') || value.events.length) return false;
    const s = data.intelligence_summary;
    return s === 'Context unavailable' || obj(s) && Object.entries(s).every(([k, v]) => k === 'project_name' ? text(v, 120) :
      ['total_files', 'requirements_count', 'traceability_nodes', 'health_issues', 'missing_dependencies'].includes(k) && number(v));
  }
  if (method === 'get_environment_status') return keys(data, 'python_available,python_version,virtualenv_present,virtualenv_usable,inspection_scope')
    && typeof data.python_available === 'boolean' && typeof data.virtualenv_present === 'boolean' && typeof data.virtualenv_usable === 'boolean'
    && text(data.python_version, 40) && text(data.inspection_scope, 80) && !value.events.length;
  if (method in intelligenceChecks) return false;
  if (!keys(data, 'request_id,status,current_state,action_state,message,pending_action,data') || !id(data.request_id) || !statuses.includes(data.status)
    || !states.includes(data.current_state) || data.action_state !== value.action_state || !text(data.message)) return false;
  if (method === 'request_agent_execution' && data.request_id !== commandId) return false;
  let previous = 0;
  for (const e of value.events) {
    if (!obj(e) || !keys(e, 'request_id,sequence,event_type,current_state,tool_call_id,timestamp') || e.request_id !== data.request_id
      || !number(e.sequence) || e.sequence <= previous || !states.includes(e.current_state) || !timestamp(e.timestamp)
      || !(e.tool_call_id === null || id(e.tool_call_id)) || !['state_changed', 'tool_started', 'tool_finished', 'permission_required', 'permission_approved', 'recovery_finished'].includes(e.event_type)) return false;
    previous = e.sequence;
  }
  const p = data.pending_action;
  if (p !== null && (!obj(p) || !keys(p, 'request_id,tool_call_id,risk_level,approved,tool_name,resource') || p.request_id !== data.request_id || !id(p.tool_call_id)
    || !['READ', 'WRITE', 'EXECUTE'].includes(p.risk_level) || typeof p.approved !== 'boolean' || !toolNames.includes(p.tool_name)
    || !(p.resource === null || text(p.resource, 200) && !/[\\:]/.test(p.resource) && !p.resource.startsWith('/') && !p.resource.split('/').includes('..')))) return false;
  if (!obj(data.data) || !keys(data.data, 'tool_results,verification,evidence,requirements,failure,recovery,truncated')
    || !Array.isArray(data.data.tool_results) || data.data.tool_results.length > 100 || typeof data.data.truncated !== 'boolean') return false;
  for (const t of data.data.tool_results) if (!obj(t) || !keys(t, 'tool_name,tool_call_id,success,exit_code,timestamp,executed') ||
    !toolNames.includes(t.tool_name) || !(t.tool_call_id === null || id(t.tool_call_id)) || typeof t.success !== 'boolean' ||
    typeof t.executed !== 'boolean' || !(t.exit_code === null || Number.isSafeInteger(t.exit_code)) || !timestamp(t.timestamp)) return false;
  const rows = (v: unknown, max: number, check: (v: any) => boolean) => Array.isArray(v) && v.length <= max && v.every(check);
  const strings = (v: unknown, max = 10) => rows(v, max, s => text(s, 160));
  if (!rows(data.data.requirements, 30, r => obj(r) && keys(r, 'requirement_id,title') && id(r.requirement_id) && text(r.title, 160))) return false;
  if (!rows(data.data.evidence, 40, e => obj(e) && keys(e, 'evidence_id,requirement_id,evidence_type,strength,summary,tool_call_id,success,exit_code,stale,superseded,timestamp')
    && id(e.evidence_id) && id(e.requirement_id) && ['FILE_EXISTS', 'SYMBOL_EXISTS', 'CODE_INSPECTION', 'TEST_PASS', 'TEST_FAIL', 'COMMAND_RESULT', 'TOOL_RESULT', 'RECOVERY_RESULT', 'RUNTIME_RESULT'].includes(e.evidence_type)
    && ['DIRECT', 'SUPPORTING', 'WEAK', 'CONTRADICTORY'].includes(e.strength) && text(e.summary, 300)
    && (e.tool_call_id === null || id(e.tool_call_id)) && (e.success === null || typeof e.success === 'boolean')
    && (e.exit_code === null || Number.isSafeInteger(e.exit_code)) && typeof e.stale === 'boolean' && typeof e.superseded === 'boolean' && timestamp(e.timestamp))) return false;
  const f = data.data.failure, r = data.data.recovery;
  if (f !== null && (!obj(f) || !keys(f, 'category,severity,summary,root_cause,tool_name')
    || !(f.category === null || ['SYNTAX_ERROR', 'IMPORT_ERROR', 'DEPENDENCY_ERROR', 'TEST_FAILURE', 'RUNTIME_ERROR', 'FILE_NOT_FOUND', 'PERMISSION_ERROR', 'TIMEOUT', 'CONFIGURATION_ERROR', 'ENVIRONMENT_ERROR', 'UNKNOWN'].includes(f.category))
    || !(f.severity === null || ['INFO', 'WARNING', 'ERROR', 'CRITICAL'].includes(f.severity)) || !text(f.summary, 300)
    || !(f.root_cause === null || text(f.root_cause, 300)) || !(f.tool_name === null || toolNames.includes(f.tool_name)))) return false;
  if (r !== null && (!obj(r) || !keys(r, 'status,attempts,final_result,tests_run,timestamp')
    || !['PLANNING', 'PERMISSION_REQUIRED', 'CHECKPOINTING', 'APPLYING', 'RETESTING', 'RECOVERED', 'RETRYING', 'ROLLING_BACK', 'ROLLED_BACK', 'BLOCKED', 'FAILED'].includes(r.status)
    || !number(r.attempts) || !text(r.final_result, 300) || !strings(r.tests_run) || !timestamp(r.timestamp))) return false;
  const v = data.data.verification;
  return v === null || obj(v) && keys(v, 'overall_status,report,timestamp,requirement_results,remaining_issues,truncated') && timestamp(v.timestamp)
    && ['VERIFIED', 'PARTIALLY_VERIFIED', 'NOT_VERIFIED', 'INCONCLUSIVE', 'PENDING'].includes(v.overall_status)
    && obj(v.report) && keys(v.report, 'total_requirements,verified,partially_verified,unverified,inconclusive,evidence_count,tests_executed,recovery_attempts') && Object.values(v.report).every(number)
    && typeof v.truncated === 'boolean' && strings(v.remaining_issues)
    && rows(v.requirement_results, 30, q => obj(q) && keys(q, 'requirement_id,status,evidence_used,missing_evidence,contradictions,explanation,confidence')
      && id(q.requirement_id) && ['VERIFIED', 'PARTIALLY_VERIFIED', 'NOT_VERIFIED', 'INCONCLUSIVE', 'PENDING'].includes(q.status)
      && strings(q.evidence_used, 20) && strings(q.missing_evidence) && strings(q.contradictions, 20) && text(q.explanation, 300) && ['HIGH', 'MEDIUM', 'LOW'].includes(q.confidence));
}