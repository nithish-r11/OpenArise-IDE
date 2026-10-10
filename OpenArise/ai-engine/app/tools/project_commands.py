"""Permission-gated project scripts. Project scripts are code, not a sandbox."""
import os
import subprocess
import tempfile
from app.tools.base import BaseTool
from app.tools.permissions import RiskLevel
from app.project.commands import project_commands, resolve_command
from app.verification.snapshot import project_snapshot


class ProjectCommandTool(BaseTool):
    risk_level = RiskLevel.EXECUTE
    action = "test"
    name = "execute_project_tests"
    description = "Run an observed npm test script after approval. Uses its exact command ID and manifest revision; no arbitrary commands."

    def __init__(self, project_root):
        self.project_root = os.path.abspath(project_root)

    def get_schema(self):
        choices = [c for c in project_commands(self.project_root) if c["kind"] == "node_script" and c["action"] == self.action and c["supported"]]
        return {"name": self.name, "description": self.description,
                "parameters": {"type": "object", "additionalProperties": False,
                               "properties": {"command_id": {"type": "string", "enum": [c["id"] for c in choices]},
                                              "revision": {"type": "string", "enum": list(dict.fromkeys(c["revision"] for c in choices))}},
                               "required": ["command_id", "revision"]},
                "observed_commands": [{k: c[k] for k in ("id", "directory", "revision", "script")} for c in choices]}

    def validate_arguments(self, command_id, revision):
        command = next((c for c in project_commands(self.project_root) if c["id"] == command_id
                        and c["kind"] == "node_script" and c["action"] == self.action), None)
        if command is None:
            raise ValueError("This test/build command is not available in the project.")
        return resolve_command(self.project_root, command, revision)

    def execute(self, command_id, revision):
        # Re-resolve immediately before launching, including manifest freshness.
        invocation = self.validate_arguments(command_id, revision)
        before = project_snapshot(self.project_root)
        # Bound memory/output; do not run a shell or inherit renderer-controlled argv.
        with tempfile.TemporaryFile() as output:
            child = subprocess.Popen([invocation["executable"], *invocation["arguments"]],
                                     cwd=invocation["directory"], stdout=output, stderr=subprocess.STDOUT,
                                     shell=False, **({"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}))
            timed_out = False
            try:
                child.wait(timeout=120)
            except subprocess.TimeoutExpired:
                timed_out = True
                if os.name == "nt":
                    subprocess.run([os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "taskkill.exe"),
                                    "/PID", str(child.pid), "/T", "/F"], capture_output=True, timeout=10)
                child.kill()
                child.wait(timeout=10)
            output.seek(0)
            text = output.read(131072).decode("utf-8", errors="replace")
            truncated = bool(output.read(1))
        return {"exit_code": -1 if timed_out else child.returncode, "stdout": text,
                "stderr": "Command timed out." if timed_out else "", "truncated": truncated,
                "command": invocation["label"], "command_id": command_id,
                "project_snapshot": before if before == project_snapshot(self.project_root) else None}


class ProjectBuildTool(ProjectCommandTool):
    action = "build"
    name = "build_project"
    description = "Run an observed npm build script after approval. A passing build is build evidence, never a passed test."
