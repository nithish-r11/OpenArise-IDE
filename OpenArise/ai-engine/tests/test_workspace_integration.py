import hashlib
import json
from pathlib import Path

import pytest

from app.api.services import ProjectWorkspaceService
from app.api.models import ApiError, ErrorCode
from app.context.adapter import ProjectIntelligenceContextAdapter
from app.blueprint.models import FeatureItem, TaskItem
from app.traceability.models import LinkType
from app.models.schemas import AgentAction, AgentRequest, ToolCall
from app.agent.orchestrator import AgentOrchestrator
from app.tools.base import ToolRegistry
from app.tools.fs import WriteFileTool
from tests.hardening_helpers import OfflineLLM


def file_snapshot(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


@pytest.fixture
def mapped_workspace(tmp_path):
    (tmp_path / "feature.py").write_text("def answer():\n    return 42\n")
    (tmp_path / "test_feature.py").write_text("def test_answer():\n    assert True\n")
    (tmp_path / "unrelated.py").write_text("value = 1\n")
    (tmp_path / "requirements.txt").write_text("pytest\n")
    service = ProjectWorkspaceService(str(tmp_path))
    req = service.req_manager.create_requirement("Answer", "Return 42")
    blueprint = service.blueprint_manager.generate_initial_blueprint(service.state_manager.state, "Return 42")
    blueprint.features.append(FeatureItem(
        feature_id="feature", requirement_ids=[req.requirement_id], title="Answer", description="Return 42",
    ))
    blueprint.tasks.append(TaskItem(task_id="task", feature_id="feature", title="Implement", description="Return 42"))
    service.current_blueprint = blueprint
    service.refresh_workspace()
    node = next(n for n in service.traceability_graph.graph.implementations if n.file_path == "feature.py")
    service.traceability_graph.add_link("task", node.implementation_id, LinkType.TASK_TO_IMPLEMENTATION)
    baseline = service.create_requirement_baseline(req.requirement_id).data
    return service, req, node, baseline


def test_read_only_facade_assembles_all_production_components(tmp_path, monkeypatch):
    (tmp_path / "feature.py").write_text("def answer():\n    return 42\n")
    (tmp_path / "test_feature.py").write_text("def test_answer():\n    assert True\n")
    (tmp_path / "requirements.txt").write_text("pytest\n")
    before = file_snapshot(tmp_path)
    def reject_execution(*args, **kwargs):
        raise AssertionError("Read-only workspace inspection executed a subprocess")
    monkeypatch.setattr("subprocess.run", reject_execution)
    service = ProjectWorkspaceService(str(tmp_path))
    state = service.get_project_state().data
    blueprint = service.get_blueprint().data
    graph = service.get_traceability_graph().data
    environment = service.get_environment_status().data
    health = service.get_health_report().data
    snapshot = service.get_intelligence_snapshot().data
    context = ProjectIntelligenceContextAdapter(service).build_bounded_context()["intelligence_summary"]
    assert service.traceability_graph is service.traceability_mapper.graph_manager
    assert state["project_info"]["project_id"] == blueprint["project_id"] == graph["project_id"]
    assert len(graph["implementations"]) == 1 and len(graph["tests"]) == 1
    assert graph["links"][0]["is_inferred"] and not graph["links"][0]["evidence_backed"]
    assert environment == health["environment"]
    assert snapshot["project_state_summary"]["total_files"] == len(state["files"])
    assert snapshot["timeline_summary"] == service.get_timeline().data
    assert context["traceability_nodes"] == snapshot["traceability_summary"]["nodes"]
    assert context["total_files"] == 3
    assert file_snapshot(tmp_path) == before
    assert not (tmp_path / ".openarise").exists()


def test_mapper_refresh_preserves_node_ids_links_and_no_duplicates(mapped_workspace):
    service, _, node, _ = mapped_workspace
    before = service.get_traceability_graph().data
    service.refresh_workspace()
    after = service.get_traceability_graph().data
    assert [n["implementation_id"] for n in before["implementations"]] == [n["implementation_id"] for n in after["implementations"]]
    assert len(before["links"]) == len(after["links"])
    assert len({link["link_id"] for link in after["links"]}) == len(after["links"])
    assert any(link["target_id"] == node.implementation_id and link["link_type"] == "task_to_implementation" for link in after["links"])


def test_baseline_and_snapshot_include_real_requirements_and_relationships(mapped_workspace):
    service, req, node, baseline = mapped_workspace
    assert service.get_requirements().data[0]["requirement_id"] == req.requirement_id
    assert baseline["associated_feature_ids"] == ["feature"]
    assert baseline["task_feature_ids"] == {"task": "feature"}
    assert baseline["implementation_ids"] == [node.implementation_id]
    assert baseline["implementation_hashes"][node.implementation_id]
    assert service.get_drift_report(baseline).data["state"] == "NO_DRIFT"
    snapshot = service.get_intelligence_snapshot().data
    assert snapshot["requirement_summary"]["total"] == 1
    assert snapshot["drift_summary"][0]["state"] == "NO_DRIFT"
    assert snapshot["timeline_summary"][-1]["event_type"] == "DRIFT_DETECTED"


def test_changed_related_implementation_produces_potential_drift(mapped_workspace):
    service, _, node, baseline = mapped_workspace
    (Path(service.project_root) / "feature.py").write_text("def answer():\n    return 7\n")
    service.refresh_workspace()
    result = service.get_drift_report(baseline).data
    assert result["state"] == "POTENTIAL_DRIFT"
    assert result["related_implementations"] == [node.implementation_id]


def test_unrelated_modification_does_not_invalidate_requirement(mapped_workspace):
    service, _, _, baseline = mapped_workspace
    (Path(service.project_root) / "unrelated.py").write_text("value = 99\n")
    service.refresh_workspace()
    assert service.get_drift_report(baseline).data["state"] == "NO_DRIFT"


def test_removed_implementation_is_structural_drift(mapped_workspace):
    service, _, _, baseline = mapped_workspace
    (Path(service.project_root) / "feature.py").unlink()
    service.refresh_workspace()
    assert service.get_drift_report(baseline).data["state"] == "CONFIRMED_STRUCTURAL_DRIFT"


@pytest.mark.parametrize("relationship", ["requirement_feature", "feature_task", "task_implementation"])
def test_removed_graph_relationship_is_structural_drift(mapped_workspace, relationship):
    service, _, _, baseline = mapped_workspace
    kind = {
        "requirement_feature": LinkType.REQUIREMENT_TO_FEATURE,
        "feature_task": LinkType.FEATURE_TO_TASK,
        "task_implementation": LinkType.TASK_TO_IMPLEMENTATION,
    }[relationship]
    graph = service.traceability_graph.graph
    graph.links = [link for link in graph.links if link.link_type != kind]
    assert service.get_drift_report(baseline).data["state"] == "CONFIRMED_STRUCTURAL_DRIFT"


def test_task_moved_to_another_feature_is_structural_drift(mapped_workspace):
    service, req, _, baseline = mapped_workspace
    service.current_blueprint.features.append(FeatureItem(
        feature_id="other-feature", requirement_ids=[req.requirement_id], title="Other", description="Other",
    ))
    service.current_blueprint.tasks[0].feature_id = "other-feature"
    service.refresh_workspace()
    assert service.get_drift_report(baseline).data["state"] == "CONFIRMED_STRUCTURAL_DRIFT"


@pytest.mark.parametrize("bad_reference", ["absent", "wrong_requirement"])
def test_missing_or_invalid_evidence_reference_is_unresolved(mapped_workspace, bad_reference):
    service, _, _, baseline = mapped_workspace
    baseline["evidence_ids"] = ["evidence-id"]
    if bad_reference == "wrong_requirement":
        service.traceability_graph.add_evidence_ref("evidence-id")
        service.traceability_graph.add_requirement("other")
        service.traceability_graph.add_link("other", "evidence-id", LinkType.REQUIREMENT_TO_EVIDENCE)
    assert service.get_drift_report(baseline).data["state"] == "UNRESOLVED"


def test_missing_hash_is_unresolved_not_false_no_drift(mapped_workspace):
    service, _, _, baseline = mapped_workspace
    baseline["implementation_hashes"] = {}
    assert service.get_drift_report(baseline).data["state"] == "UNRESOLVED"


def test_agent_intelligence_reaches_actual_prompt_without_caller_override(tmp_path):
    (tmp_path / "feature.py").write_text("answer = 42\n")
    llm = OfflineLLM(AgentAction(action_type="respond"))
    agent = AgentOrchestrator(llm, project_root=str(tmp_path))
    service = ProjectWorkspaceService(str(tmp_path), agent)
    service.request_agent_execution(
        "Inspect the project",
        context_data={"intelligence_summary": {"total_files": 999, "token": "private-value"},
                      "files": ["whole-repo"], "password": "private-value"},
    )
    summary = json.loads(llm.last_prompt.split("Context Summary:\n")[1].split("\n\nRequirements:")[0])
    assert summary["intelligence_summary"]["total_files"] == 1
    assert "private-value" not in llm.last_prompt
    assert "whole-repo" not in llm.last_prompt


def test_direct_agent_context_is_bounded_and_unknown_fields_excluded(tmp_path):
    llm = OfflineLLM(AgentAction(action_type="respond"))
    agent = AgentOrchestrator(llm, project_root=str(tmp_path))
    agent.process_request(AgentRequest(prompt="Inspect", context_data={
        "intelligence_summary": {"project_name": "api_key=abcdef", "total_files": 2,
                                 "requirements_count": {"token": "private"},
                                 "files": "x" * 100000, "token": "private"},
    }))
    summary = json.loads(llm.last_prompt.split("Context Summary:\n")[1].split("\n\nRequirements:")[0])
    assert summary["intelligence_summary"]["total_files"] == 2
    assert "abcdef" not in llm.last_prompt
    assert "private" not in llm.last_prompt
    assert len(json.dumps(summary["intelligence_summary"])) < 500


def test_agent_requirements_evidence_mapping_and_baseline_are_wired(tmp_path):
    registry = ToolRegistry()
    registry.register(WriteFileTool(str(tmp_path)))
    llm = OfflineLLM(AgentAction(action_type="tool_call", tool_calls=[
        ToolCall(tool_call_id="write", tool_name="write_file", arguments={"path": "feature.py", "content": "value = 1\n"})
    ]))
    agent = AgentOrchestrator(llm, tool_registry=registry, project_root=str(tmp_path))
    service = ProjectWorkspaceService(str(tmp_path), agent)
    pending = service.request_agent_execution("Create feature.py", request_id="wired").data
    req_id = pending["data"]["requirements"][0]["requirement_id"]
    assert service.get_requirements().data[0]["requirement_id"] == req_id
    assert req_id in service.get_blueprint().data["requirements"]
    service.approve_agent_action("wired", "write")
    response = service.resume_agent_execution("wired", "write").data
    graph = service.get_traceability_graph().data
    assert graph["requirements"] == [req_id]
    assert len(graph["implementations"]) == 1
    assert graph["evidence"] == [e["evidence_id"] for e in response["data"]["evidence"]]
    baseline = service.create_requirement_baseline(req_id).data
    assert len(baseline["implementation_ids"]) == 1
    assert service.get_drift_report(baseline).data["state"] == "NO_DRIFT"
    assert service.get_evidence("wired").data == response["data"]["evidence"]
    assert service.request_agent_execution("Create feature.py", request_id="wired").data == response
    assert llm.action_requests == 1


def test_workspace_rejects_mismatched_agent_root(tmp_path):
    other = tmp_path / "other"
    other.mkdir()
    agent = AgentOrchestrator(OfflineLLM(AgentAction(action_type="respond")), project_root=str(other))
    with pytest.raises(ApiError) as error:
        ProjectWorkspaceService(str(tmp_path), agent)
    assert error.value.code == ErrorCode.INVALID_PROJECT_ROOT


def test_sensitive_python_file_is_not_parsed(tmp_path):
    (tmp_path / "credentials.py").write_text("import private_secret_dependency\nclass SecretSymbol: pass\n")
    (tmp_path / "safe.py").write_text("value = 1\n")
    service = ProjectWorkspaceService(str(tmp_path))
    state = service.get_project_state().data
    assert [m["relative_path"] for m in state["python_modules"]] == ["safe.py"]
    assert "private_secret_dependency" not in json.dumps(state)


def test_multiple_implementation_hashes_are_compared_individually(mapped_workspace):
    service, req, _, _ = mapped_workspace
    extra = next(node for node in service.traceability_graph.graph.implementations if node.file_path == "unrelated.py")
    service.traceability_graph.add_link("task", extra.implementation_id, LinkType.TASK_TO_IMPLEMENTATION)
    baseline = service.create_requirement_baseline(req.requirement_id).data
    assert len(baseline["implementation_hashes"]) == 2
    assert service.get_drift_report(baseline).data["state"] == "NO_DRIFT"
    (Path(service.project_root) / "unrelated.py").write_text("value = 100\n")
    service.refresh_workspace()
    result = service.get_drift_report(baseline).data
    assert result["state"] == "POTENTIAL_DRIFT"
    assert result["related_implementations"] == [extra.implementation_id]
