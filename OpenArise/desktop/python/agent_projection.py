"""Allowlisted desktop presentation fields; backend engines remain authoritative."""
import re
from app.memory.redact import SecretRedactor
from app.tools.fs import _is_safe_path
from app.models.schemas import FailureEvent, RecoveryResult
from intelligence_projection import READS, project_data, clean

TOOLS = {"read_file", "write_file", "execute_python", "execute_tests", "execute_project_tests", "build_project"}
COUNTS = ("total_requirements", "verified", "partially_verified", "unverified", "inconclusive",
          "evidence_count", "tests_executed", "recovery_attempts")

def identifier(value):
    return value if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value) else None

def safe_path(value, root):
    if not isinstance(value, str) or len(value) > 200 or "\\" in value or ":" in value:
        return None
    if not _is_safe_path(root, value) or any(p in ("..", ".") for p in value.split("/")):
        return None
    return SecretRedactor().redact(value)

def texts(values, limit=10):
    return [clean(v, 160) for v in values[:limit]]

def failure_data(value):
    if not isinstance(value, dict):
        return None
    try:
        f = FailureEvent.model_validate(value)
        return {"category": f.category.value, "severity": None, "summary": clean(f.summary, 300),
                "root_cause": clean(f.root_cause, 300),
                "tool_name": f.tool_name if f.tool_name in TOOLS else None}
    except ValueError:
        return None

def recovery_data(value):
    # Present the actual optional RecoveryResult returned by the engine.
    # Never read agent internals/memory or infer an outcome from recovery_finished.
    if not isinstance(value, dict):
        return None
    try:
        r = RecoveryResult.model_validate(value)
        return {"status": r.status.value, "attempts": r.attempts, "final_result": clean(r.final_result, 300),
                "tests_run": texts(r.tests_run), "timestamp": r.timestamp}
    except ValueError:
        return None

def project_response(response, method, workspace):
    result = {k: response[k] for k in ("request_id", "success", "action_state")}
    result.update(data=None, error=None, events=[])
    if not response["success"]:
        result["error"] = {"success": False, "code": response["error"]["code"],
                           "message": clean(response["error"].get("message") or "Backend could not complete this command.", 500), "details": {}}
        return result
    data = response["data"]
    if method == "shutdown":
        result["data"] = {"closed": data["closed"]}
    elif method in READS:
        result["data"] = project_data(method, data, workspace)
    else:
        events = []
        for e in response.get("events", [])[-200:]:
            if e["event_type"] in ("state_changed", "tool_started", "tool_finished", "permission_required", "permission_approved", "recovery_finished"):
                events.append({**e, "tool_call_id": identifier(e.get("tool_call_id"))})
        result["events"] = events
        pending = data.get("pending_action")
        if pending:
            call = pending["tool_call"]
            resource = safe_path(call.get("arguments", {}).get("path") or call.get("arguments", {}).get("script_path"), workspace.project_root)
            if call["tool_name"] in ("execute_project_tests", "build_project"):
                from app.project.commands import project_commands
                command = next((c for c in project_commands(workspace.project_root) if c["id"] == call.get("arguments", {}).get("command_id")), None)
                resource = safe_path(command["manifest"], workspace.project_root) if command else None
            pending = {"request_id": pending["request_id"], "tool_call_id": pending["tool_call_id"],
                       "risk_level": pending["risk_level"], "approved": pending["approved"],
                       "tool_name": call["tool_name"] if call["tool_name"] in TOOLS else "unregistered_tool",
                       "resource": resource}
            if call["tool_name"] in ("execute_project_tests", "build_project") and command and command["revision"] == call.get("arguments", {}).get("revision"):
                pending["command"] = {"label": clean(command["label"], 160), "script": clean(command["script"], 1000), "revision": command["revision"]}
        details = data.get("data") or {}
        tools = [{"tool_name": t["tool_name"] if t["tool_name"] in TOOLS else "unregistered_tool",
                  "tool_call_id": identifier(t["tool_call_id"]), "success": bool(t["success"]),
                  "exit_code": t.get("exit_code"), "timestamp": t.get("timestamp"),
                  "executed": t.get("metadata", {}).get("executed") is True}
                 for t in details.get("tool_results", [])[-100:]]
        for projected, original in zip(tools, details.get("tool_results", [])[-100:]):
            resolution = identifier(original.get("metadata", {}).get("resolved_by"))
            if resolution:
                projected["resolved_by"] = resolution
        raw_evidence = details.get("evidence", [])
        evidence = []
        for e in raw_evidence[:40]:
            facts = e.get("result") or {}
            evidence.append({"evidence_id": identifier(e["evidence_id"]), "requirement_id": identifier(e["requirement_id"]),
                             "evidence_type": e["evidence_type"], "strength": e["strength"],
                             "summary": clean(e["summary"], 300), "tool_call_id": identifier(e.get("tool_call_id")),
                             "success": facts.get("success") if type(facts.get("success")) is bool else None,
                             "exit_code": facts.get("exit_code") if type(facts.get("exit_code")) is int else None,
                             "stale": facts.get("stale") is True, "superseded": facts.get("superseded") is True,
                             "timestamp": e["timestamp"]})
            for field in ("resolved_by", "recovery_evidence"):
                if identifier(facts.get(field)):
                    evidence[-1][field] = facts[field]
        raw_requirements = details.get("requirements", [])
        requirements = [{"requirement_id": identifier(r["requirement_id"]), "title": clean(r["title"], 160)}
                        for r in raw_requirements[:30]]
        verification = details.get("verification")
        if verification:
            rows = verification.get("requirement_results", [])
            remaining = verification["report"].get("remaining_issues", [])
            verification = {"overall_status": verification["overall_status"],
                            "report": {k: verification["report"][k] for k in COUNTS},
                            "timestamp": verification["timestamp"],
                            "requirement_results": [{"requirement_id": identifier(r["requirement_id"]), "status": r["status"],
                                "evidence_used": texts(r["evidence_used"], 20), "missing_evidence": texts(r["missing_evidence"]),
                                "contradictions": texts(r["contradictions"], 20), "explanation": clean(r["explanation"], 300),
                                "confidence": r["confidence"]} for r in rows[:30]],
                            "remaining_issues": texts(remaining),
                            "truncated": len(rows) > 30 or len(remaining) > 10 or any(
                                len(r["evidence_used"]) > 20 or len(r["missing_evidence"]) > 10 or len(r["contradictions"]) > 20 for r in rows)}
        # Only the answer of a text-only action is presented. Tool arguments/prose stay withheld.
        model_response = details.get("agent_message") if details.get("action_type") == "message" and not details.get("tool_calls") else None
        message = clean(data.get("message", ""), 500)
        result["data"] = {"request_id": data["request_id"], "status": data["status"],
                          "current_state": data["current_state"], "action_state": data["action_state"],
                          "message": message, "pending_action": pending,
                          "data": {"tool_results": tools, "verification": verification, "evidence": evidence,
                                   "requirements": requirements, "failure": failure_data(details.get("error")),
                                   "recovery": recovery_data(details.get("recovery")),
                                   "truncated": len(raw_evidence) > 40 or len(raw_requirements) > 30 or len(details.get("tool_results", [])) > 100}}
        if isinstance(model_response, str) and model_response.strip():
            result["data"]["data"]["model_response"] = clean(model_response, 8000)
            result["data"]["data"]["truncated"] |= len(model_response) > 8000
    return result
