import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "python"))
from agent_host import build_service, serve
from agent_projection import project_response
from intelligence_projection import clean

class IntelligenceHostTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "app.py").write_text("def hello():\n    return 'private-source-marker'\n")
        (self.root / "requirements.txt").write_text("pytest\n")
        self.service = build_service(str(self.root))
        self.addCleanup(lambda: self.service.dispatch({"request_id": "stop", "method": "shutdown", "params": {}}))

    def send(self, method, params=None):
        response = self.service.dispatch({"request_id": method, "method": method, "params": params or {}}).model_dump(mode="json")
        self.assertTrue(response["success"], response)
        return project_response(response, method, self.service.workspace)

    def test_every_read_and_refresh_preserves_project_bytes_and_creates_no_agent(self):
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with patch("agent_host.build_agent", side_effect=AssertionError("No agent needed for reads")):
            for method in ("refresh_workspace", "get_project_information", "get_project_state", "get_requirements",
                           "get_blueprint", "get_traceability_graph", "get_environment_status", "get_health_report",
                           "get_intelligence_snapshot", "get_timeline"):
                result = self.send(method)
                self.assertIsNotNone(result["data"])
                self.assertNotIn("private-source-marker", json.dumps(result))
        self.assertIsNone(self.service.workspace.orchestrator)
        self.assertEqual(before, {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        self.assertFalse((self.root / ".openarise").exists())

    def test_baseline_is_host_retained_and_compared_by_existing_backend(self):
        req = self.service.workspace.req_manager.create_requirement("Greeting", "A local greeting")
        self.service.workspace.current_blueprint.requirements.append(req.requirement_id)
        commands = [
            {"request_id": "capture", "method": "create_requirement_baseline", "params": {"requirement_id": req.requirement_id}},
            {"request_id": "refresh", "method": "refresh_workspace", "params": {}},
            {"request_id": "compare", "method": "get_drift_report", "params": {"baseline_dict": {"requirement_id": req.requirement_id}}},
            {"request_id": "stop", "method": "shutdown", "params": {}},
        ]
        destination = io.StringIO()
        serve(self.service, io.StringIO("\n".join(map(json.dumps, commands)) + "\n"), destination)
        responses = list(map(json.loads, destination.getvalue().splitlines()))
        self.assertTrue(all(r["success"] for r in responses), responses)
        self.assertEqual(responses[0]["data"], {"requirement_id": req.requirement_id, "captured": True})
        self.assertEqual(responses[2]["data"]["state"], "NO_DRIFT")
        self.assertNotIn("implementation_hashes", destination.getvalue())

    def test_missing_or_forged_baseline_fails_closed(self):
        for baseline in ({"requirement_id": "missing"}, {"requirement_id": "missing", "implementation_hashes": {}}):
            destination = io.StringIO()
            command = {"request_id": "compare", "method": "get_drift_report", "params": {"baseline_dict": baseline}}
            serve(self.service, io.StringIO(json.dumps(command) + "\n"), destination)
            result = json.loads(destination.getvalue())
            self.assertFalse(result["success"])
            self.assertEqual(result["error"]["details"], {})

    def test_projection_strips_secrets_urls_diagnostics_and_source_fields(self):
        req = self.service.workspace.req_manager.create_requirement("Greeting", "password=very-private https://example.test/token")
        req.source_text = "private-source-marker"
        wire = json.dumps(self.send("get_requirements"))
        for value in ("very-private", "example.test", "private-source-marker"):
            self.assertNotIn(value, wire)
        self.assertEqual(clean("Traceback (most recent call last)\nprivate"), "[Internal diagnostic withheld]")
        self.assertEqual(len(clean("x" * 5000)), 800)

    def test_requirements_bound_records_and_preserve_lifecycle_verification(self):
        for i in range(105):
            self.service.workspace.req_manager.create_requirement("Requirement " + str(i), "Description " + str(i))
        data = self.send("get_requirements")["data"]
        self.assertEqual(data["total"], 105)
        self.assertEqual(len(data["items"]), 100)
        self.assertTrue(data["truncated"])
        self.assertEqual(data["items"][0]["lifecycle_status"], "pending")
        self.assertEqual(data["items"][0]["status"], "PENDING")
