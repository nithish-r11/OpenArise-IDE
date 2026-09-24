# Integration contract

The current implemented backend contract is documented in:

- [Person 3 integration handover](../docs/INTEGRATION_HANDOVER.md)
- [Backend process contract](../docs/BACKEND_PROCESS_CONTRACT.md)

Person 3 uses ProjectWorkspaceService, optionally through BackendService.
Existing Person 2 managers assemble observations and delegate agent execution to
Person 1's AgentOrchestrator. No transport server is provided.

Actions retain request/tool-call IDs and exact pending calls. Approval and resume
are separate operations through PermissionManager. Deny/cancel terminate pending
work without undoing earlier side effects. CompletionGate remains the final
verification authority. Outer service success is not task verification.

The earlier proposal to regenerate an action after approval is superseded.
Execution uses ordinary subprocesses with project cwd and tool path checks,
not OS-level sandboxing. Consult the current handover for precise limitations.
