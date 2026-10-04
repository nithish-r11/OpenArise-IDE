import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from agent_host import build_service, serve
from agent_projection import project_response
from app.models.schemas import AgentAction, ToolCall
from app.llm.base import LLMProvider

class OfflineProvider(LLMProvider):
    def generate(self, *args, **kwargs):
        raise AssertionError("No network")
    def generate_structured(self, prompt, schema, **kwargs):
        return AgentAction(action_type="tool_call", message="password=hidden-value", tool_calls=[
            ToolCall(tool_name="write_file", tool_call_id="tool-1",
                     arguments={"path": "result.py", "content": "password = 'sensitive-file-content'\n"})])
    def health_check(self):
        return True

class AgentHostTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.service = build_service(str(self.root), OfflineProvider())
        self.addCleanup(lambda: self.service.dispatch({"request_id": "shutdown", "method": "shutdown", "params": {}}))

    def send(self, command, method, **params):
        response = self.service.dispatch({"request_id": command, "method": method, "params": params}).model_dump(mode="json")
        return project_response(response, method, self.service.workspace)

    def test_real_orchestrator_approval_resume_and_unverified(self):
        pending = self.send("agent-1", "request_agent_execution", prompt="Write result.py")
        self.assertEqual(pending["data"]["status"], "permission_required")
        self.assertFalse((self.root / "result.py").exists())
        self.assertEqual(pending["data"]["pending_action"]["resource"], "result.py")
        approved = self.send("approve", "approve_agent_action", request_id="agent-1", tool_call_id="tool-1")
        self.assertEqual(approved["data"]["status"], "approved")
        self.assertFalse((self.root / "result.py").exists())
        final = self.send("resume", "resume_agent_execution", request_id="agent-1", tool_call_id="tool-1")
        self.assertEqual(final["data"]["status"], "unverified")
        self.assertTrue((self.root / "result.py").exists())
        self.assertNotEqual(final["data"]["data"]["verification"]["overall_status"], "VERIFIED")
        self.assertEqual(final, self.send("resume", "resume_agent_execution", request_id="agent-1", tool_call_id="tool-1"))

    def test_no_raw_tool_arguments_output_or_model_prose(self):
        pending = self.send("agent-1", "request_agent_execution", prompt="Write result.py")
        wire = json.dumps(pending)
        for secret in ("hidden-value", "sensitive-file-content", "arguments", "agent_message"):
            self.assertNotIn(secret, wire)
        self.assertTrue(pending["events"])
        self.assertTrue(all(e["request_id"] == "agent-1" for e in pending["events"]))

    def test_deny_does_not_write_and_uses_backend_state(self):
        self.send("a", "request_agent_execution", prompt="Write result.py")
        result = self.send("deny", "deny_agent_action", request_id="a", tool_call_id="tool-1")
        self.assertEqual(result["data"]["status"], "denied")
        self.assertFalse((self.root / "result.py").exists())
        self.assertFalse(result["data"]["data"]["tool_results"][0]["executed"])

    def test_cancel_revokes_pending_approval(self):
        self.send("a", "request_agent_execution", prompt="Write result.py")
        self.send("approve", "approve_agent_action", request_id="a", tool_call_id="tool-1")
        result = self.send("cancel", "cancel_agent_execution", request_id="a")
        self.assertEqual(result["data"]["status"], "cancelled")
        self.assertEqual(self.service.workspace.orchestrator.permission_manager._approvals, {})

    def test_context_is_bounded_factual_summary(self):
        (self.root / "private.env").write_text("token=hidden")
        result = self.send("context", "get_intelligence_snapshot")
        summary = result["data"]["intelligence_summary"]
        self.assertIn("requirements_count", summary)
        self.assertNotIn("files", summary)
        self.assertNotIn("hidden", json.dumps(result))

    def test_stdio_preserves_ids_and_shutdown_ack(self):
        requests = [{"request_id": "context", "method": "get_intelligence_snapshot", "params": {}},
                    {"request_id": "stop", "method": "shutdown", "params": {}}]
        destination = io.StringIO()
        serve(self.service, io.StringIO("\n".join(json.dumps(r) for r in requests) + "\n"), destination)
        responses = [json.loads(line) for line in destination.getvalue().splitlines()]
        self.assertEqual([r["request_id"] for r in responses], ["context", "stop"])
        self.assertEqual(responses[-1]["data"], {"closed": True})

    def test_shutdown_cancels_pending_and_keeps_permissions_production(self):
        self.send("a", "request_agent_execution", prompt="Write result.py")
        self.assertFalse(self.service.workspace.orchestrator.permission_manager.test_mode)
        self.send("stop", "shutdown")
        self.assertFalse((self.root / "result.py").exists())
        self.assertEqual(self.service.workspace.orchestrator.get_request("a").status, "cancelled")

    def test_boundary_error_does_not_leak_details(self):
        result = self.send("bad", "resume_agent_execution", request_id="missing", tool_call_id="secret")
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["details"], {})
        self.assertNotIn("Traceback", json.dumps(result))

    def test_projection_preserves_backend_gate_coverage_and_safe_evidence(self):
        self.send("phase7", "request_agent_execution", prompt="Write result.py")
        self.send("phase7-approve", "approve_agent_action", request_id="phase7", tool_call_id="tool-1")
        final = self.send("phase7-resume", "resume_agent_execution", request_id="phase7", tool_call_id="tool-1")
        details = final["data"]["data"]
        self.assertEqual(details["verification"]["overall_status"], "PARTIALLY_VERIFIED")
        self.assertTrue(details["verification"]["requirement_results"])
        self.assertTrue(details["verification"]["requirement_results"][0]["missing_evidence"])
        self.assertEqual(len(details["evidence"]), 1)
        self.assertEqual(details["evidence"][0]["strength"], "SUPPORTING")
        self.assertIsNone(details["failure"])
        self.assertIsNone(details["recovery"])
        for withheld in ("sensitive-file-content", "file_hash", "output", "arguments", "agent_message"):
            self.assertNotIn(withheld, json.dumps(details))

    def test_projection_failure_and_optional_recovery_are_bounded_and_redacted(self):
        from agent_projection import failure_data, recovery_data
        failure = failure_data({"summary": "password=hidden-value", "category": "UNKNOWN", "root_cause": "token=hidden-token"})
        self.assertEqual(failure["category"], "UNKNOWN")
        self.assertIsNone(failure["severity"])
        self.assertNotIn("hidden", json.dumps(failure))
        self.assertIsNone(recovery_data(None))
        recovery = recovery_data({"recovery_id": "rec-1", "failure_id": "fail-1", "status": "RECOVERED",
                                  "final_result": "password=hidden-value", "failure_signature_before": "private",
                                  "tests_run": ["Retest returned exit 0"], "actions_executed": ["private-command"],
                                  "evidence": {"output": "private-output"}})
        self.assertEqual(recovery["status"], "RECOVERED")
        for secret in ("hidden-value", "private-command", "private-output", "private"):
            self.assertNotIn(secret, json.dumps(recovery))

    def test_recovery_finished_and_attempt_count_do_not_create_recovery_success(self):
        self.send("phase7", "request_agent_execution", prompt="Write result.py")
        self.send("phase7-approve", "approve_agent_action", request_id="phase7", tool_call_id="tool-1")
        raw = self.service.dispatch({"request_id": "phase7-resume", "method": "resume_agent_execution",
                                    "params": {"request_id": "phase7", "tool_call_id": "tool-1"}}).model_dump(mode="json")
        raw["events"].append({"request_id": "phase7", "sequence": 99, "event_type": "recovery_finished",
                              "current_state": "RECOVERING", "tool_call_id": "tool-1", "timestamp": "2026-09-27T12:00:00Z"})
        raw["data"]["data"]["verification"]["report"]["recovery_attempts"] = 1
        projected = project_response(raw, "resume_agent_execution", self.service.workspace)
        self.assertIsNone(projected["data"]["data"]["recovery"])
        self.assertEqual(projected["data"]["data"]["verification"]["report"]["recovery_attempts"], 1)
        self.assertEqual(projected["data"]["status"], "unverified")

    def test_projection_marks_partial_evidence_presentation(self):
        self.send("phase7", "request_agent_execution", prompt="Write result.py")
        self.send("phase7-approve", "approve_agent_action", request_id="phase7", tool_call_id="tool-1")
        raw = self.service.dispatch({"request_id": "phase7-resume", "method": "resume_agent_execution",
                                    "params": {"request_id": "phase7", "tool_call_id": "tool-1"}}).model_dump(mode="json")
        evidence = raw["data"]["data"]["evidence"][0]
        raw["data"]["data"]["evidence"] = [{**evidence, "evidence_id": "ev-" + str(i)} for i in range(45)]
        raw["data"]["data"]["evidence"][0]["result"]["stale"] = True
        projected = project_response(raw, "resume_agent_execution", self.service.workspace)["data"]["data"]
        self.assertEqual(len(projected["evidence"]), 40)
        self.assertTrue(projected["truncated"])
        self.assertTrue(projected["evidence"][0]["stale"])