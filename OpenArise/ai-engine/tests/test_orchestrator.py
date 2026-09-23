import pytest
from app.agent.orchestrator import AgentOrchestrator
from app.models.schemas import AgentRequest, AgentAction, ToolCall, AgentResponse
from app.agent.state import AgentState
from tests.mock_llm import MockLLMProvider
from app.context.manager import ContextManager

def test_agent_orchestrator_success():
    # Setup mock LLM with a predefined successful action
    action = AgentAction(
        action_type="respond",
        message="Here is my response",
        tool_calls=[]
    )
    llm = MockLLMProvider(structured_response=action)
    context = ContextManager()
    
    orchestrator = AgentOrchestrator(llm_provider=llm, context_manager=context)
    
    assert orchestrator.state == AgentState.IDLE
    
    req = AgentRequest(prompt="What is the meaning of life?", context_data={"test": True})
    resp = orchestrator.process_request(req)
    
    # Assert successful flow
    assert orchestrator.state == AgentState.COMPLETED
    assert resp.status == "unverified"
    assert "verification status is: INCONCLUSIVE" in resp.message
    assert resp.data["action_type"] == "respond"
    
    # Assert state transitions were tracked
    assert orchestrator.execution_state.current_state == AgentState.COMPLETED.value
    assert len(orchestrator.execution_state.history) == 1
    
    # Assert context was updated
    assert context.user_request == "What is the meaning of life?"
    assert context.project_state.get("test") is True
    
    # Assert system prompt was included
    assert "You are an AI software engineering agent" in llm.last_system_prompt

def test_agent_orchestrator_failure():
    llm = MockLLMProvider(should_fail=True)
    orchestrator = AgentOrchestrator(llm_provider=llm)
    
    req = AgentRequest(prompt="Fail please")
    resp = orchestrator.process_request(req)
    
    assert orchestrator.state == AgentState.FAILED
    assert resp.status == "failure"
    assert "error" in resp.data
    
    # Assert failure was added to context
    assert len(orchestrator.context.previous_failures) == 1
    failure = orchestrator.context.previous_failures[0]
    assert failure["summary"] == "Orchestrator error: ValueError"
