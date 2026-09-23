from app.models.schemas import (
    AgentRequest, ToolCall, ToolResult, AgentAction, AgentResponse, ExecutionState, FailureEvent, VerificationResult, FailureCategory
)

def test_agent_request_schema():
    req = AgentRequest(prompt="Do something")
    assert req.prompt == "Do something"
    assert req.context_data == {}

def test_tool_call_schema():
    call = ToolCall(tool_name="read_file", arguments={"path": "main.py"})
    assert call.tool_name == "read_file"
    assert call.arguments["path"] == "main.py"

def test_failure_event_schema():
    event = FailureEvent(category=FailureCategory.SYNTAX_ERROR, summary="Invalid syntax", evidence={"file": "test.py"})
    assert event.category == FailureCategory.SYNTAX_ERROR
    assert event.summary == "Invalid syntax"
    assert event.evidence["file"] == "test.py"
