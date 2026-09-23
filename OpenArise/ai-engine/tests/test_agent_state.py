import pytest
from app.agent.state import AgentState

def test_agent_states_exist():
    assert AgentState.IDLE == "IDLE"
    assert AgentState.THINKING == "THINKING"
    assert AgentState.PLANNING == "PLANNING"
    assert AgentState.EXECUTING == "EXECUTING"
    assert AgentState.OBSERVING == "OBSERVING"
    assert AgentState.FAILED == "FAILED"
    assert AgentState.RECOVERING == "RECOVERING"
    assert AgentState.VERIFYING == "VERIFYING"
    assert AgentState.COMPLETED == "COMPLETED"
