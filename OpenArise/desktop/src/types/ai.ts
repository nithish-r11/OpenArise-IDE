import type { BackendEvent, JsonObject } from './backend';
export interface AIRequest { requestId: string; prompt: string; context?: JsonObject; projectRef?: { id: string } }
export interface AIPending { request_id: string; tool_call_id: string; risk_level: 'READ' | 'WRITE' | 'EXECUTE'; approved: boolean; tool_name: string; resource: string | null }
export interface AITool { resolved_by?: string; tool_name: string; tool_call_id: string | null; success: boolean; executed: boolean; exit_code: number | null; timestamp: string }
export type VerificationStatus = 'VERIFIED' | 'PARTIALLY_VERIFIED' | 'NOT_VERIFIED' | 'INCONCLUSIVE' | 'PENDING';
export type DataSource = 'backend' | 'test_fixture' | 'unknown';
export type PresentationState = 'verified' | 'unverified' | 'failed' | 'blocked' | 'unavailable' | 'pending';
export interface AIRequirementResult { requirement_id: string; status: VerificationStatus; evidence_used: string[]; missing_evidence: string[]; contradictions: string[]; explanation: string; confidence: 'HIGH' | 'MEDIUM' | 'LOW' }
export interface AIVerification { overall_status: VerificationStatus; report: Record<string, number>; timestamp: string; requirement_results: AIRequirementResult[]; remaining_issues: string[]; truncated: boolean }
export interface AIEvidence { resolved_by?: string; recovery_evidence?: string; evidence_id: string; requirement_id: string; evidence_type: string; strength: string; summary: string; tool_call_id: string | null; success: boolean | null; exit_code: number | null; stale: boolean; superseded: boolean; timestamp: string }
export interface AIFailure { category: string | null; severity: 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL' | null; summary: string; root_cause: string | null; tool_name: string | null }
export interface AIRecovery { status: 'PLANNING' | 'PERMISSION_REQUIRED' | 'CHECKPOINTING' | 'APPLYING' | 'RETESTING' | 'RECOVERED' | 'RETRYING' | 'ROLLING_BACK' | 'ROLLED_BACK' | 'BLOCKED' | 'FAILED'; attempts: number; final_result: string; tests_run: string[]; timestamp: string }
export interface AIResult {
  request_id: string; status: 'success' | 'unverified' | 'failure' | 'permission_required' | 'approved' | 'denied' | 'cancelled';
  current_state: string; action_state: string; message: string; pending_action: AIPending | null;
  data: { model_response?: string; tool_results: AITool[]; verification: AIVerification | null; evidence: AIEvidence[]; requirements: { requirement_id: string; title: string }[]; failure: AIFailure | null; recovery: AIRecovery | null; truncated: boolean };
}
export interface AIHistoryItem { request: AIRequest; timestamp: string; state: string; result?: AIResult; events: BackendEvent[]; error?: string; source?: DataSource; permissionAction?: AIPending }