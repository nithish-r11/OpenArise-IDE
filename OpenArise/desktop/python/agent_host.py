"""Desktop stdio adapter around the existing BackendService. No agent implementation."""
import contextlib
import json
import logging
import os
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "ai-engine"))
from app.api.backend import BackendService
from app.api.services import ProjectWorkspaceService
from app.agent.orchestrator import AgentOrchestrator
from app.llm.ollama import OllamaProvider
from app.tools.base import ToolRegistry
from app.tools.fs import ReadFileTool, WriteFileTool
from app.tools.execution import PythonExecutionTool, TestExecutionTool
from app.tools.permissions import PermissionManager
sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent_projection import project_response
from intelligence_projection import READS

METHODS = {"get_intelligence_snapshot", "get_environment_status", "request_agent_execution",
           "get_agent_execution", "approve_agent_action", "resume_agent_execution",
           "deny_agent_action", "cancel_agent_execution", "shutdown"} | READS

def build_agent(root, provider=None):
    registry = ToolRegistry()
    for tool in (ReadFileTool, WriteFileTool, PythonExecutionTool, TestExecutionTool):
        registry.register(tool(root))
    orchestrator = AgentOrchestrator(provider or OllamaProvider(), tool_registry=registry,
                                    permission_manager=PermissionManager(test_mode=False),
                                    project_root=root)
    return orchestrator

def build_service(root, provider=None):
    # Read-only intelligence must not initialize agent memory/checkpoint stores.
    return BackendService(ProjectWorkspaceService(root, build_agent(root, provider) if provider is not None else None))

def serve(service, source, destination):
    baselines = {}
    for line in iter(lambda: source.readline(65537), ""):
        if len(line) > 65536:
            break
        request = None
        try:
            request = json.loads(line)
            if not isinstance(request, dict) or request.get("method") not in METHODS:
                raise ValueError()
            with contextlib.redirect_stdout(sys.stderr):
                if request["method"] == "request_agent_execution" and service.workspace.orchestrator is None:
                    service.workspace.orchestrator = build_agent(service.workspace.project_root)
                if request["method"] in ("request_agent_execution", "get_drift_report", "create_requirement_baseline"):
                    refreshed = service.dispatch({"request_id": str(uuid.uuid4()), "method": "refresh_workspace", "params": {}})
                    if not refreshed.success:
                        raise RuntimeError("Workspace context unavailable")
                if request["method"] == "get_drift_report":
                    target = request["params"]["baseline_dict"]
                    if set(target) != {"requirement_id"} or target["requirement_id"] not in baselines:
                        raise ValueError("Capture a baseline first")
                    request = {**request, "params": {"baseline_dict": baselines[target["requirement_id"]]}}
                response = service.dispatch(request).model_dump(mode="json")
                if request["method"] == "create_requirement_baseline" and response["success"]:
                    baselines[response["data"]["requirement_id"]] = response["data"]
                projected = project_response(response, request["method"], service.workspace)
            destination.write(json.dumps(projected, ensure_ascii=True) + "\n")
            destination.flush()
            if request["method"] == "shutdown":
                return
        except Exception:
            destination.write(json.dumps({"request_id": request.get("request_id", "invalid") if isinstance(request, dict) else "invalid",
                "success": False, "action_state": None, "data": None,
                "error": {"success": False, "code": "internal_error", "message": "Agent operation unavailable.", "details": {}}, "events": []}) + "\n")
            destination.flush()
    with contextlib.redirect_stdout(sys.stderr):
        service.dispatch({"request_id": "desktop-eof-shutdown", "method": "shutdown", "params": {}})

def main():
    # Protocol stdout is reserved; logs and third-party prints never reach React.
    logging.disable(logging.CRITICAL)
    from process_supervisor import own_windows_job
    job = own_windows_job() if os.name == 'nt' else None
    with contextlib.redirect_stdout(sys.stderr):
        service = build_service(str(Path(sys.argv[1]).resolve(strict=True)))
    print('{"ready":true}', flush=True)
    serve(service, sys.stdin, sys.stdout)

if __name__ == "__main__":
    main()
