"""Observed command descriptors constrain real inference and remain fail-closed."""
import json
from unittest.mock import Mock, patch
import pytest
from app.agent.orchestrator import AgentOrchestrator
from app.llm.ollama import OllamaProvider
from app.models.schemas import AgentAction, AgentRequest, ToolCall, RecoveryPlan
from app.recovery.planner import PLANNER_SYSTEM_PROMPT
from app.tools.project_commands import ProjectCommandTool
from app.tools.base import ToolRegistry
from app.tools.fs import WriteFileTool
from tests.test_project_commands import project, call_for, GOOD


@pytest.mark.parametrize('schema', [AgentAction, RecoveryPlan])
def test_ollama_format_constrains_registered_command_arguments(tmp_path, schema):
    project(tmp_path)
    tool = ProjectCommandTool(str(tmp_path))
    provider = OllamaProvider()
    generated = {'action_type': 'message', 'message': 'No execution', 'tool_calls': []} if schema is AgentAction else {
        'failure_id': 'f', 'goal': 'Repair implementation', 'diagnosis_summary': 'Failed check',
        'expected_result': 'Original check passes', 'proposed_actions': [], 'risk_level': 'READ'}
    with patch.object(provider, '_generate', return_value=json.dumps(generated)) as generate:
        provider.generate_structured('test', schema, json_schema=True, tool_schemas=[tool.get_schema()])
    payload = generate.call_args.args[0]
    variant = payload['format']['$defs']['ToolCall']['anyOf'][0]
    assert variant['properties']['tool_name']['const'] == 'execute_project_tests'
    assert variant['properties']['arguments'] == tool.get_schema()['parameters']
    assert variant['properties']['arguments']['properties']['command_id']['enum'] == [call_for(tmp_path)['command_id']]
    assert 'arguments' in variant['required']
    assert payload['stream'] is False


@pytest.mark.parametrize('invalid', [
    {'command_id': 'guessed'}, {'revision': 'stale'}, {'executable': 'cmd.exe'}, {'revision': None},
])
def test_invalid_generated_command_rejects_entire_batch_before_write(tmp_path, invalid):
    project(tmp_path)
    args = {**call_for(tmp_path), **invalid}
    registry = ToolRegistry()
    registry.register(WriteFileTool(str(tmp_path)))
    command = ProjectCommandTool(str(tmp_path))
    registry.register(command)
    provider = Mock()
    provider.generate_structured.return_value = AgentAction(action_type='tool_call', tool_calls=[
        ToolCall(tool_name='write_file', arguments={'path': 'probe.py', 'content': 'print(1)'}),
        ToolCall(tool_name='execute_project_tests', arguments=args),
    ])
    agent = AgentOrchestrator(provider, tool_registry=registry, project_root=str(tmp_path))
    with patch('app.tools.project_commands.subprocess.Popen') as launch:
        result = agent.process_request(AgentRequest(prompt='Run observed tests.'))
    assert result.status == 'failure' and result.pending_action is None
    assert result.data['tool_results'] == []
    assert result.data['verification']['overall_status'] != 'VERIFIED'
    assert not (tmp_path / 'probe.py').exists()
    assert (tmp_path / 'math.cjs').read_text() == GOOD
    launch.assert_not_called()


def test_valid_command_still_requires_explicit_permission(tmp_path):
    project(tmp_path)
    registry = ToolRegistry()
    registry.register(ProjectCommandTool(str(tmp_path)))
    provider = Mock()
    provider.generate_structured.return_value = AgentAction(action_type='tool_call', tool_calls=[
        ToolCall(tool_name='execute_project_tests', arguments=call_for(tmp_path))])
    agent = AgentOrchestrator(provider, tool_registry=registry, project_root=str(tmp_path))
    with patch('app.tools.project_commands.subprocess.Popen') as launch:
        result = agent.process_request(AgentRequest(prompt='Run tests.'))
    assert result.status == 'permission_required'
    assert not result.pending_action.approved
    launch.assert_not_called()


def test_recovery_prompt_preserves_original_node_check():
    assert 'ORIGINAL failed test/build command' in PLANNER_SYSTEM_PROMPT
    assert 'never pytest' in PLANNER_SYSTEM_PROMPT
    assert 'mandatory pytest retest' not in PLANNER_SYSTEM_PROMPT


def test_write_generation_requires_explicit_overwrite_without_changing_safe_tool_default(tmp_path):
    tool = WriteFileTool(str(tmp_path))
    original = tool.get_schema()
    provider = OllamaProvider()
    with patch.object(provider, '_generate', return_value='{"action_type":"message","message":"No execution","tool_calls":[]}') as generate:
        provider.generate_structured('test', AgentAction, json_schema=True, tool_schemas=[original], minimum_tool_calls=3)
    payload = generate.call_args.args[0]
    arguments = payload['format']['$defs']['ToolCall']['anyOf'][0]['properties']['arguments']
    assert 'overwrite' in arguments['required']
    assert 'default' not in arguments['properties']['overwrite']
    assert payload['format']['properties']['tool_calls']['minItems'] == 3
    assert original == tool.get_schema()
    assert original['parameters']['properties']['overwrite']['default'] is False
    (tmp_path / 'existing.py').write_text('preserved')
    with pytest.raises(FileExistsError):
        tool.execute(path='existing.py', content='not approved to overwrite')
    assert (tmp_path / 'existing.py').read_text() == 'preserved'
