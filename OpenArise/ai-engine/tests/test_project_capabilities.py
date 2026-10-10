import json
from unittest.mock import patch
import pytest
from app.api.services import ProjectWorkspaceService
from app.context.project import build_project_context, bounded_project_context, MAX_CONTENT
from app.agent.orchestrator import AgentOrchestrator
from app.models.schemas import AgentMessageAction
from app.llm.base import LLMProvider
from app.verification.snapshot import project_snapshot
from app.tools.fs import WriteFileTool
from app.project.capabilities import read_project_text


def fullstack(root):
    (root / "frontend" / "src").mkdir(parents=True)
    (root / "backend").mkdir()
    (root / "frontend/package.json").write_text(json.dumps({"dependencies": {"react": "1"}, "devDependencies": {"vite": "1"}, "scripts": {"test": "node --test", "build": "node build.mjs"}}))
    (root / "frontend/src/main.tsx").write_text("export const Product = 'ObservedProduct';\n")
    (root / "frontend/tsconfig.json").write_text("{}")
    (root / "backend/main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n")
    (root / "backend/requirements.txt").write_text("fastapi\npytest\n")
    (root / "backend/test_main.py").write_text("def test_example():\n    assert True\n")


def test_fullstack_detection_uses_actual_manifests_and_imports(tmp_path):
    fullstack(tmp_path)
    data = ProjectWorkspaceService(str(tmp_path)).get_project_capabilities().data
    assert data["projectType"] == "full-stack"
    assert data["frontend"] == ["React", "Vite"]
    assert data["backend"] == ["FastAPI", "Python"]
    assert {"TypeScript", "Python"} <= set(data["languages"])
    assert "frontend/src/main.tsx" in data["entryPoints"]
    assert [(c["directory"], c["action"]) for c in data["commands"]] == [(".", "test"), ("frontend", "build"), ("frontend", "test")]
    assert all(c["approvalRequired"] for c in data["commands"] if c["kind"] == "node_script")


@pytest.mark.parametrize("framework,source", [("Flask", "from flask import Flask\n"), ("Django", "import django\n")])
def test_python_framework_detection(tmp_path, framework, source):
    (tmp_path / "app.py").write_text(source)
    data = ProjectWorkspaceService(str(tmp_path)).get_project_capabilities().data
    assert framework in data["backend"]
    assert data["projectType"] == "backend"


def test_express_and_package_manager_are_observed_not_fallback_execution(tmp_path):
    (tmp_path / "package.json").write_text(json.dumps({"dependencies": {"express": "1"}, "scripts": {"test": "node --test"}}))
    (tmp_path / "server.js").write_text("import express from 'express';")
    (tmp_path / "pnpm-lock.yaml").write_text("lockfileVersion: 9")
    data = ProjectWorkspaceService(str(tmp_path)).get_project_capabilities().data
    assert data["backend"] == ["Express", "Node.js"]
    assert data["dependencyManagers"] == ["pnpm"]
    assert not data["commands"][0]["supported"]


def test_bad_manifest_and_empty_project_are_explicit(tmp_path):
    empty = ProjectWorkspaceService(str(tmp_path)).get_project_capabilities().data
    assert empty["projectType"] == "unknown" and empty["commands"] == []
    (tmp_path / "package.json").write_text("invalid")
    bad = ProjectWorkspaceService(str(tmp_path)).get_project_capabilities().data
    assert bad["warnings"] and not bad["commands"]


def test_context_contains_real_fullstack_sources_and_excludes_secrets(tmp_path):
    fullstack(tmp_path)
    (tmp_path / ".env").write_text("password=hidden")
    (tmp_path / "backend/credentials.py").write_text("SECRET_DATA")
    (tmp_path / "backend/settings.py").write_text("password = 'PRIVATE_PASSWORD'\n")
    state = ProjectWorkspaceService(str(tmp_path)).state_manager.state
    data = build_project_context(tmp_path, state)
    wire = json.dumps(data)
    assert "ObservedProduct" in wire and "FastAPI()" in wire and "test_example" in wire
    assert "PRIVATE_PASSWORD" not in wire and "SECRET_DATA" not in wire and "hidden" not in wire
    assert len(data["structure"]) <= 80 and len(data["files"]) <= 16
    assert sum(len(f["content"]) for f in data["files"]) <= MAX_CONTENT


def test_context_bounds_large_sources_and_handles_invalid_optional_data(tmp_path):
    for index in range(25):
        (tmp_path / f"module_{index}.py").write_text("# large\n" * 1000)
    data = build_project_context(tmp_path, ProjectWorkspaceService(str(tmp_path)).state_manager.state)
    assert data["truncated"]
    assert sum(len(f["content"]) for f in data["files"]) <= MAX_CONTENT
    assert bounded_project_context({"files": None, "structure": None, "unavailable": None})["files"] == []


def test_context_redacts_quoted_and_truncated_secret_values(tmp_path):
    (tmp_path / "settings.json").write_text('{"password":"PRIVATE_PASSWORD","nested":{"api-key":"PRIVATE_KEY"},"public":"ObservedValue"}')
    data = build_project_context(tmp_path, ProjectWorkspaceService(str(tmp_path)).state_manager.state)
    wire = json.dumps(data)
    assert "PRIVATE_PASSWORD" not in wire and "PRIVATE_KEY" not in wire
    assert "ObservedValue" in wire
    truncated = bounded_project_context({"structure": ["settings.json"], "files": [{"path": "settings.json", "content": '{"authorization":"PRIVATE' }]})
    assert "PRIVATE" not in json.dumps(truncated)


def test_context_preserves_valid_unicode_at_byte_limit_but_refuses_invalid_utf8(tmp_path):
    (tmp_path / "main.py").write_text("# café\n", encoding="utf-8")
    assert read_project_text(tmp_path, "main.py", 6) == "# caf"
    (tmp_path / "bad.py").write_bytes(b"\xffinvalid")
    assert read_project_text(tmp_path, "bad.py") is None


def test_actual_facade_prompt_overrides_forged_context_without_tools(tmp_path):
    (tmp_path / "main.py").write_text("from math_ops import multiply\nprint(multiply(3, 4))\n")
    (tmp_path / "math_ops.py").write_text("def multiply(a, b):\n    return a * b\n")
    class Capture(LLMProvider):
        def health_check(self):
            return True
        def generate(self, *args, **kwargs):
            raise AssertionError()
        def generate_structured(self, prompt, schema, **kwargs):
            self.prompt = prompt
            assert schema is AgentMessageAction
            return AgentMessageAction(action_type="message", message="Observed main.py imports math_ops.")
    provider = Capture()
    agent = AgentOrchestrator(provider, project_root=str(tmp_path))
    workspace = ProjectWorkspaceService(str(tmp_path), agent)
    response = workspace.request_agent_execution("Inspect this project; do not modify files.", {"response_mode": "text_only", "project_context": {"files": [{"path": "fake.py", "content": "FAKE_CONTEXT"}]}}).data
    assert "math_ops" in provider.prompt and "return a * b" in provider.prompt
    assert "FAKE_CONTEXT" not in provider.prompt
    assert response["data"]["tool_results"] == []
    assert response["data"]["verification"]["overall_status"] != "VERIFIED"


@pytest.mark.parametrize("filename", ["view.tsx", "view.jsx", "index.html", "site.css", "yarn.lock"])
def test_frontend_mutation_invalidates_project_snapshot(tmp_path, filename):
    file = tmp_path / filename
    file.write_text("first")
    before = project_snapshot(str(tmp_path))
    file.write_text("changed")
    assert before != project_snapshot(str(tmp_path))


def test_atomic_save_failure_preserves_original_and_cleans_temporary_file(tmp_path):
    (tmp_path / "main.py").write_text("original")
    with patch("os.replace", side_effect=OSError("controlled disk failure")), pytest.raises(OSError):
        WriteFileTool(str(tmp_path)).execute(path="main.py", content="replacement", overwrite=True)
    assert (tmp_path / "main.py").read_text() == "original"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["main.py"]


def test_exclusive_creation_does_not_replace_existing_file(tmp_path):
    (tmp_path / "new.py").write_text("keep")
    with pytest.raises(FileExistsError):
        WriteFileTool(str(tmp_path)).execute(path="new.py", content="replace")
    assert (tmp_path / "new.py").read_text() == "keep"
