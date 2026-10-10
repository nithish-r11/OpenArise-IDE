"""Explicit plans fail closed; real execution and approval remain authoritative."""
import json
from unittest.mock import Mock, patch
import pytest
from app.agent.requested_steps import requested_steps, validate_requested_steps
from app.agent.orchestrator import AgentOrchestrator
from app.llm.ollama import OllamaProvider
from app.models.schemas import AgentAction, AgentRequest, ToolCall
from app.tools.base import ToolRegistry
from app.tools.fs import WriteFileTool
from app.tools.execution import TestExecutionTool
from app.verification.requirements import RequirementExtractor

PROMPT = 'Demonstrate controlled recovery. THREE ordered calls: execute_tests for baseline; write_file path "math_ops.py" overwrite=true content "def multiply(a, b):\\n    return a + b\\n"; execute_tests to detect the fault. Never modify tests or call execute_python.'


def test_explicit_order_and_literal_arguments():
    assert requested_steps(PROMPT) == [
        {'tool_name': 'execute_tests', 'arguments': {}},
        {'tool_name': 'write_file', 'arguments': {'path': 'math_ops.py', 'overwrite': True, 'content': 'def multiply(a, b):\n    return a + b\n'}},
        {'tool_name': 'execute_tests', 'arguments': {}},
    ]


@pytest.mark.parametrize('text', ['Inspect the project. Do not use write_file.', 'Explain execute_tests.', 'Fix the backend and frontend.'])
def test_non_action_instructions_do_not_become_tools(text):
    assert requested_steps(text) == []


def test_numbered_ordered_workflow_has_one_identity_without_losing_independent_requirements():
    reqs = RequirementExtractor(None).extract('Perform recovery with ordered calls:\n1. execute_tests for baseline.\n2. write_file path "main.py" content "print(1)" overwrite true.\n3. execute_tests after mutation.\nPreserve all tests.')
    assert len(reqs) == 1
    assert 'required_tool_count:execute_tests:2' in reqs[0].acceptance_criteria
    assert len(RequirementExtractor(None).extract('1. Build a login API\n2. Build a frontend')) == 2


def test_ollama_tuple_is_constrained_to_actual_steps_and_registered_arguments(tmp_path):
    registry = ToolRegistry()
    registry.register(WriteFileTool(str(tmp_path)))
    registry.register(TestExecutionTool(str(tmp_path)))
    provider = OllamaProvider()
    with patch.object(provider, '_generate', return_value='{"action_type":"tool_call","tool_calls":[]}') as generate:
        provider.generate_structured('request', AgentAction, json_schema=True, tool_schemas=registry.get_all_schemas(), requested_steps=requested_steps(PROMPT))
    schema = generate.call_args.args[0]['format']
    calls = schema['properties']['tool_calls']
    assert calls['minItems'] == calls['maxItems'] == 3
    assert [step['properties']['tool_name']['const'] for step in calls['items']] == ['execute_tests', 'write_file', 'execute_tests']
    args = calls['items'][1]['properties']['arguments']['properties']
    assert args['path']['const'] == 'math_ops.py'
    assert args['content']['const'] == 'def multiply(a, b):\n    return a + b\n'
    assert args['overwrite']['const'] is True
    assert 'ToolCall' not in schema['$defs']


@pytest.mark.parametrize('names', [[], ['execute_tests']*3, ['write_file', 'execute_tests', 'execute_tests'], ['execute_tests', 'write_file', 'execute_python']])
def test_wrong_generated_sequence_cannot_request_approval_or_execute(tmp_path, names):
    (tmp_path / 'math_ops.py').write_text('ORIGINAL')
    provider = Mock()
    provider.generate_structured.return_value = AgentAction(action_type='tool_call', tool_calls=[ToolCall(tool_name=name, arguments={'path': 'math_ops.py', 'content': 'changed', 'overwrite': True}) for name in names])
    registry = ToolRegistry()
    registry.register(WriteFileTool(str(tmp_path)))
    test = TestExecutionTool(str(tmp_path))
    registry.register(test)
    agent = AgentOrchestrator(provider, tool_registry=registry, project_root=str(tmp_path))
    with patch.object(test, 'execute') as execute:
        result = agent.process_request(AgentRequest(prompt=PROMPT))
    assert result.status == 'failure'
    assert result.pending_action is None and result.data['tool_results'] == []
    assert result.data['verification']['overall_status'] != 'VERIFIED'
    assert (tmp_path / 'math_ops.py').read_text() == 'ORIGINAL'
    execute.assert_not_called()


@pytest.mark.parametrize('changed', [
    {'content': 'def multiply(a, b):\n    return a * b\n'}, {'path': 'other.py'}, {'overwrite': False}, {'overwrite': 1},
])
def test_wrong_literal_arguments_are_rejected_before_execution(changed):
    calls = [ToolCall(tool_name=step['tool_name'], arguments=step['arguments']) for step in requested_steps(PROMPT)]
    calls[1].arguments.update(changed)
    with pytest.raises(ValueError, match='arguments'):
        validate_requested_steps(AgentAction(action_type='tool_call', tool_calls=calls), requested_steps(PROMPT))


def test_literal_newlines_do_not_break_normal_code_requests():
    step = requested_steps('Use write_file path "main.py" content "print(1)\n" overwrite true.')[0]
    assert step['arguments']['content'] == 'print(1)\n'


def test_valid_ordered_write_still_stops_for_exact_approval(tmp_path):
    (tmp_path / 'math_ops.py').write_text('ORIGINAL')
    provider = Mock()
    prompt = 'Use write_file path "math_ops.py" content "APPROVED_ONLY" overwrite true.'
    provider.generate_structured.return_value = AgentAction(action_type='tool_call', tool_calls=[ToolCall(tool_name='write_file', arguments=requested_steps(prompt)[0]['arguments'])])
    registry = ToolRegistry()
    registry.register(WriteFileTool(str(tmp_path)))
    agent = AgentOrchestrator(provider, tool_registry=registry, project_root=str(tmp_path))
    result = agent.process_request(AgentRequest(prompt=prompt))
    assert result.status == 'permission_required' and not result.pending_action.approved
    assert (tmp_path / 'math_ops.py').read_text() == 'ORIGINAL'
    denied = agent.deny_action(result.request_id, result.pending_action.tool_call_id)
    assert denied.status == 'denied' and (tmp_path / 'math_ops.py').read_text() == 'ORIGINAL'
    second = agent.process_request(AgentRequest(prompt=prompt))
    assert agent.resume_request(second.request_id, second.pending_action.tool_call_id).status == 'permission_required'
    assert (tmp_path / 'math_ops.py').read_text() == 'ORIGINAL'
    agent.approve_action(second.request_id, second.pending_action.tool_call_id)
    completed = agent.resume_request(second.request_id, second.pending_action.tool_call_id)
    assert (tmp_path / 'math_ops.py').read_text() == 'APPROVED_ONLY'
    assert len(completed.data['tool_results']) == 1
    assert completed.status == 'unverified'  # A write alone is not fresh test proof.


def test_generation_metrics_do_not_log_model_text_or_nonnumeric_values(caplog):
    response = Mock()
    response.json.return_value = {'response': 'PRIVATE_MODEL_OUTPUT', 'done': True,
        'prompt_eval_count': 100, 'eval_count': 'SECRET_TOKEN', 'prompt_eval_duration': 2000000000, 'eval_duration': -1}
    with patch('app.llm.ollama.requests.post', return_value=response), caplog.at_level('INFO'):
        assert OllamaProvider().generate('PRIVATE_SOURCE') == 'PRIVATE_MODEL_OUTPUT'
    assert '100' in caplog.text and '2000000000' in caplog.text
    assert all(value not in caplog.text for value in ('PRIVATE_SOURCE', 'PRIVATE_MODEL_OUTPUT', 'SECRET_TOKEN'))
