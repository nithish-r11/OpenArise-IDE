"""Deterministic planning; actual Node/npm execution, recovery, and gate evidence."""
import json
import pytest
from app.agent.orchestrator import AgentOrchestrator
from app.tools.base import ToolRegistry
from app.tools.fs import WriteFileTool
from app.tools.permissions import PermissionManager, RiskLevel
from app.tools.project_commands import ProjectCommandTool, ProjectBuildTool
from app.project.commands import project_commands, resolve_command
from app.models.schemas import AgentAction, AgentRequest, ToolCall, DiagnosisResult, RecoveryPlan, FailureCategory, ConfidenceLevel
from tests.test_resumable_recovery import Provider, complete

GOOD = 'module.exports=(a,b)=>a*b;\n'
BAD = 'module.exports=(a,b)=>a+b;\n'

def project(root, failing=False):
    (root/'math.cjs').write_text(GOOD)
    (root/'test.cjs').write_text('const assert=require("node:assert/strict"); assert.equal(require("./math.cjs")(3,4),12);' + (' assert.fail("immutable failure");' if failing else ''))
    (root/'build.cjs').write_text('require("node:assert/strict").equal(typeof require("./math.cjs"),"function"); console.log("ACTUAL_BUILD");')
    (root/'package.json').write_text(json.dumps({'name':'safe-command-test','scripts':{'test':'node test.cjs','build':'node build.cjs','pretest':'node -e "throw Error(\'must not run\')"'}}))

def call_for(root, action='test'):
    c=next(c for c in project_commands(str(root)) if c['action']==action)
    return {'command_id':c['id'],'revision':c['revision']}

class NodeProvider(Provider):
    def __init__(self, root, action='test'): self.root, self.action = root, action
    def generate_structured(self,prompt,schema,**kwargs):
        if schema is AgentAction:
            return AgentAction(action_type='tool_call',tool_calls=[ToolCall(tool_name='write_file',arguments={'path':'math.cjs','content':'module.exports = ;\n' if self.action == 'build' else BAD,'overwrite':True}), ToolCall(tool_name='build_project' if self.action == 'build' else 'execute_project_tests',arguments=call_for(self.root,self.action))])
        if schema is DiagnosisResult:
            return DiagnosisResult(category=FailureCategory.TEST_FAILURE,summary='Node assertion failed.',probable_root_cause='Addition instead of multiplication.',confidence=ConfidenceLevel.HIGH)
        if schema is RecoveryPlan:
            return RecoveryPlan(failure_id='test',goal='Repair implementation',diagnosis_summary='Restore product.',proposed_actions=[ToolCall(tool_name='write_file',arguments={'path':'math.cjs','content':GOOD,'overwrite':True})],expected_result='Original Node test passes',risk_level=RiskLevel.WRITE)
        raise AssertionError(schema)

def agent(root):
    registry=ToolRegistry()
    for tool in (WriteFileTool,ProjectCommandTool,ProjectBuildTool): registry.register(tool(str(root)))
    return AgentOrchestrator(NodeProvider(root),tool_registry=registry,permission_manager=PermissionManager(False),project_root=str(root))

def test_real_npm_test_runs_without_pretest_hook(tmp_path):
    project(tmp_path)
    output=ProjectCommandTool(str(tmp_path)).execute(**call_for(tmp_path))
    assert output['exit_code']==0 and output['project_snapshot']
    assert 'must not run' not in output['stdout']

def test_manifest_change_invalidates_approval_descriptor(tmp_path):
    project(tmp_path); args=call_for(tmp_path)
    (tmp_path/'package.json').write_text('{"scripts":{"test":"node changed.cjs"}}')
    with pytest.raises(ValueError,match='manifest changed'): ProjectCommandTool(str(tmp_path)).execute(**args)

@pytest.mark.parametrize('field,value',[('command_id','../cmd.exe'),('revision','bad')])
def test_rejects_unobserved_or_unreviewed_command(tmp_path,field,value):
    project(tmp_path); args=call_for(tmp_path); args[field]=value
    with pytest.raises(ValueError): ProjectCommandTool(str(tmp_path)).execute(**args)

def test_rejects_renderer_style_executable_and_argv_overrides(tmp_path):
    project(tmp_path)
    with pytest.raises(TypeError): ProjectCommandTool(str(tmp_path)).execute(**call_for(tmp_path),executable='cmd.exe')

def test_unsupported_manager_never_falls_back_to_npm(tmp_path):
    project(tmp_path); (tmp_path/'yarn.lock').write_text('')
    c=next(c for c in project_commands(str(tmp_path)) if c['action']=='test')
    with pytest.raises(ValueError,match='not implemented'): resolve_command(str(tmp_path),c,c['revision'])

def test_permission_denial_prevents_actual_node_mutation(tmp_path):
    project(tmp_path); a=agent(tmp_path); r=a.process_request(AgentRequest(prompt='Controlled Node repair.'))
    assert r.pending_action.risk_level==RiskLevel.WRITE
    assert a.deny_action(r.request_id,r.pending_action.tool_call_id).status=='denied'
    assert (tmp_path/'math.cjs').read_text()==GOOD

def test_real_node_recovery_retests_original_command_and_verifies(tmp_path):
    project(tmp_path); a=agent(tmp_path)
    result,pending=complete(a,a.process_request(AgentRequest(prompt='Repair multiplication with original Node tests.')))
    assert [p.tool_call.tool_name for p in pending]==['write_file','execute_project_tests','write_file','execute_project_tests']
    assert result.status=='success' and result.data['verification']['overall_status']=='VERIFIED'
    assert result.data['recovery']['status']=='RECOVERED'
    tests=[e for e in result.data['evidence'] if e['evidence_type'] in ('TEST_PASS','TEST_FAIL')]
    assert tests[0]['result']['resolved_by']==tests[1]['evidence_id']
    assert tests[1]['result']['project_snapshot'] and tests[1]['result']['exit_code']==0
    assert result.data['verification']['report']['tests_executed']==2
    (tmp_path/'math.cjs').write_text(BAD)
    assert a.get_request(result.request_id).data['verification']['overall_status']!='VERIFIED'

def test_actual_node_failed_recovery_rolls_back_and_refuses_verified(tmp_path):
    project(tmp_path,True); a=agent(tmp_path)
    result,_=complete(a,a.process_request(AgentRequest(prompt='Preserve tests; try repairing multiplication.')))
    assert result.status=='failure' and result.data['recovery']['status']=='ROLLED_BACK'
    assert result.data['verification']['overall_status']=='NOT_VERIFIED'
    assert (tmp_path/'math.cjs').read_text()==BAD

def test_actual_build_is_distinct_from_test_proof(tmp_path):
    project(tmp_path); a=agent(tmp_path)
    c=ToolCall(tool_name='build_project',arguments=call_for(tmp_path,'build'))
    a.llm.generate_structured=lambda **kwargs: AgentAction(action_type='tool_call',tool_calls=[c])
    result,_=complete(a,a.process_request(AgentRequest(prompt='Build this frontend.')))
    assert result.status=='success'
    assert result.data['verification']['report']['tests_executed']==0
    assert any(e['evidence_type']=='BUILD_PASS' and e['result']['project_snapshot'] for e in result.data['evidence'])
    assert not any(e['evidence_type']=='TEST_PASS' for e in result.data['evidence'])

def test_actual_build_recovery_rebuilds_and_does_not_claim_tests_passed(tmp_path):
    project(tmp_path); a=agent(tmp_path); a.llm=NodeProvider(tmp_path,'build')
    result,pending=complete(a,a.process_request(AgentRequest(prompt='Repair this broken build, preserving tests.')))
    assert result.status=='success' and result.data['recovery']['status']=='RECOVERED'
    assert pending[-1].tool_call.tool_name=='build_project'
    assert result.data['verification']['report']['tests_executed']==0
    assert any(e['evidence_type']=='BUILD_FAIL' and e['result'].get('resolved_by') for e in result.data['evidence'])
    assert not any(e['evidence_type']=='TEST_PASS' for e in result.data['evidence'])
