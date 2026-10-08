"""Mocked host/projection failure coverage; not evidence of live model behavior."""
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
from app.models.schemas import AgentAction
from app.llm.base import LLMProvider
from app.llm.ollama import OllamaProvider
from app.api.models import ApiError, ErrorCode

class TextProvider(LLMProvider):
    def generate(self, *args, **kwargs):
        raise AssertionError("Unexpected text path")
    def generate_structured(self, prompt, schema, **kwargs):
        return AgentAction(action_type="message", message="def multiply(a, b):\n    return a * b\n# password=private-value")
    def health_check(self):
        return True

class OllamaHostTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/"main.py").write_text("def add(a, b):\n    return a + b\n")

    def test_text_only_answer_is_bounded_redacted_and_unverified(self):
        service = build_service(str(self.root), TextProvider())
        self.addCleanup(lambda: service.dispatch({"request_id":"stop","method":"shutdown","params":{}}))
        raw = service.dispatch({"request_id":"answer","method":"request_agent_execution","params":{"prompt":"Create a multiply snippet."}}).model_dump(mode="json")
        result = project_response(raw, "request_agent_execution", service.workspace)
        self.assertEqual(result["data"]["status"],"unverified")
        self.assertIn("return a * b",result["data"]["data"]["model_response"])
        self.assertNotIn("private-value",json.dumps(result))
        self.assertEqual(result["data"]["data"]["tool_results"],[])
        raw["data"]["data"]["agent_message"] = "x"*9000
        projected = project_response(raw,"request_agent_execution",service.workspace)
        self.assertEqual(len(projected["data"]["data"]["model_response"]),8000)
        self.assertTrue(projected["data"]["data"]["truncated"])

    def test_context_and_ollama_availability_do_not_initialize_agent_memory(self):
        provider = OllamaProvider(model="qwen2.5-coder:7b")
        with patch("agent_host.build_provider",return_value=provider), patch.object(provider,"availability",return_value={"status":"ready","message":"Configured model is installed."}):
            service = build_service(str(self.root))
            destination=io.StringIO()
            serve(service,io.StringIO(json.dumps({"request_id":"context","method":"get_intelligence_snapshot","params":{}})+"\n"+json.dumps({"request_id":"stop","method":"shutdown","params":{}})+"\n"),destination)
        context=json.loads(destination.getvalue().splitlines()[0])
        self.assertEqual(context["data"]["intelligence_summary"]["total_files"],1)
        self.assertEqual(context["data"]["ollama"]["model"],"qwen2.5-coder:7b")
        self.assertEqual(context["data"]["ollama"]["status"],"ready")
        self.assertFalse((self.root/".openarise").exists())

    def test_context_failure_is_distinct_and_contains_no_traceback(self):
        service=build_service(str(self.root),TextProvider())
        original=service.dispatch
        def dispatch(request):
            if request["method"]=="refresh_workspace":
                from app.api.backend import BackendResponse
                from app.api.models import ErrorResponse
                return BackendResponse(request_id=request["request_id"],success=False,error=ErrorResponse(code=ErrorCode.PROJECT_STATE_UNAVAILABLE,message="private context diagnostic"))
            return original(request)
        destination=io.StringIO()
        with patch.object(service,"dispatch",side_effect=dispatch):
            serve(service,io.StringIO(json.dumps({"request_id":"bad-context","method":"request_agent_execution","params":{"prompt":"Explain"}})+"\n"),destination)
        result=json.loads(destination.getvalue().splitlines()[0])
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"],"project_state_unavailable")
        self.assertIn("Project context could not load",result["error"]["message"])
        self.assertNotIn("private",json.dumps(result))
        self.assertNotIn("Traceback",json.dumps(result))
