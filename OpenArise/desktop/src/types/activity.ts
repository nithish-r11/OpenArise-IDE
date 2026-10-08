export type ActivityState = 'idle' | 'submitting' | 'running' | 'waiting_for_permission' | 'failure' | 'recovering' | 'retesting' | 'verifying' | 'completed' | 'unverified' | 'denied' | 'cancelled' | 'unavailable';
export type ActivityProvenance = 'ACTUAL_STATE' | 'RECORDED_ACTIVITY' | 'UNAVAILABLE_ACTIVITY';
/** Presentation DTO. No transport, clock, inference, or synthetic event producer. */
export interface ActivityEvent {
  eventId: string; requestId: string; timestamp: string; state: ActivityState;
  title: string; detail: string; toolId?: string; toolName?: string; resource?: string;
  outcome: string; provenance: 'RECORDED_ACTIVITY';
}
export interface ActivityPresentation {
  state: ActivityState; provenance: ActivityProvenance; label: string; detail: string;
  requestId?: string; verified: boolean; events: ActivityEvent[]; dataSource?: 'backend' | 'test_fixture' | 'unknown';
}
