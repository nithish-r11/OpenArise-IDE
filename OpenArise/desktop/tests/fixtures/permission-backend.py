"""Test inference only; stdio/BackendService/permissions/file tools are production."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "python"))
from agent_host import build_service, serve
from app.models.schemas import AgentAction, ToolCall
from tests.hardening_helpers import OfflineLLM


def propose(prompt):
    request = prompt.split("User Request: ", 1)[1].split("\n\nContext Summary:", 1)[0]
    names = [name for name in ("unapproved.py", "denied.py", "allowed.py") if name in request]
    if len(names) != 1:
        raise ValueError("Fixture request must target exactly one test file")
    return AgentAction(action_type="tool_call", tool_calls=[ToolCall(
        tool_name="write_file", tool_call_id="same-write-id",
        arguments={"path": names[0], "content": "answer = 42\n"})])


service = build_service(sys.argv[1], OfflineLLM(propose))
# Reproduce a stale unscoped grant. It must not authorize any fixture request.
service.workspace.orchestrator.permission_manager.grant_approval("same-write-id")
print('{"ready":true}', flush=True)
serve(service, sys.stdin, sys.stdout)
