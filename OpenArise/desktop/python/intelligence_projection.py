"""Read-only presentation projection. All inference and validation stay in the backend."""
import re
from app.context.adapter import ProjectIntelligenceContextAdapter
from app.memory.redact import SecretRedactor
from app.traceability.validator import TraceabilityValidator

READS = {"get_project_information", "get_project_state", "get_requirements", "get_blueprint",
         "get_traceability_graph", "get_environment_status", "get_health_report",
         "get_intelligence_snapshot", "get_timeline", "get_drift_report", "refresh_workspace",
         "create_requirement_baseline"}
def clean(value, limit=800):
    if value is None:
        return None
    text = SecretRedactor().redact(str(value))
    text = re.sub(r"https?://[^\s]+", "[URL withheld]", text)
    text = re.sub(r"(?i)bearer\s+\S+", "Bearer [withheld]", text)
    if "Traceback (most recent call last)" in text:
        return "[Internal diagnostic withheld]"
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)[:limit]
def fields(row, names):
    return {name: clean(row.get(name)) if isinstance(row.get(name), str) else row.get(name) for name in names.split()}
def strings(values):
    return [clean(v, 160) for v in values[:100]]
def environment(data):
    return fields(data, "python_available python_executable python_version virtualenv_present virtualenv_path virtualenv_usable platform git_available inspection_scope")
def drift(data):
    return {**fields(data, "requirement_id state reason"),
            "related_implementations": strings(data["related_implementations"]), "related_tasks": strings(data["related_tasks"])}
def timeline(data):
    return [{**fields(e, "event_id timestamp event_type title description"),
             **{k: strings(e[k]) for k in ("related_requirement_ids", "related_feature_ids", "related_task_ids")}}
            for e in data[-100:]]
def project_data(method, data, workspace):
    if method == "get_project_information":
        return fields(data, "project_id root_path name created_at")
    if method == "get_project_state":
        return {"project_info": fields(data["project_info"], "project_id root_path name created_at"),
                "scan_timestamp": data["scan_timestamp"], "git_available": data["git_available"],
                "counts": {"files": len(data["files"]), "python_modules": len(data["python_modules"]), "test_files": len(data["tests"])},
                "files": [fields(f, "relative_path file_type size is_test is_source is_config") for f in data["files"][:100]],
                "frameworks": strings(data["frameworks"]),
                "dependencies": [fields(d, "name version_specifier source_file") for d in data["dependencies"][:100]],
                "truncated": len(data["files"]) > 100 or len(data["dependencies"]) > 100}
    if method == "get_requirements":
        return {"items": [{**fields(r, "requirement_id title description lifecycle_status status"),
                           "acceptance_criteria": [clean(c, 160) for c in r["acceptance_criteria"][:8]],
                           "implementation_references": strings(r["implementation_references"]),
                           "evidence_references": strings(r["evidence_references"])} for r in data[:100]],
                "total": len(data), "truncated": len(data) > 100}
    if method == "get_blueprint":
        return {**fields(data, "project_id project_name description generated_at"),
                "requirements": strings(data["requirements"]),
                "features": [{**fields(f, "feature_id title description status"), "requirement_ids": strings(f["requirement_ids"])} for f in data["features"][:100]],
                "tasks": [{**fields(t, "task_id feature_id title description status"), "dependencies": strings(t["dependencies"])} for t in data["tasks"][:100]],
                "truncated": any(len(data[k]) > 100 for k in ("requirements", "features", "tasks"))}
    if method == "get_traceability_graph":
        valid, issues = TraceabilityValidator().validate(workspace.traceability_graph.graph)
        return {"project_id": data["project_id"],
                **{k: strings(data[k]) for k in ("requirements", "features", "tasks", "evidence")},
                "implementations": [{**fields(n, "implementation_id file_path module_name symbol_name symbol_type feature_id"),
                                     "requirement_ids": strings(n["requirement_ids"]), "evidence_ids": strings(n["evidence_ids"])} for n in data["implementations"][:100]],
                "tests": [{**fields(n, "test_id file_path test_name"), "requirement_ids": strings(n["requirement_ids"]), "evidence_ids": strings(n["evidence_ids"])} for n in data["tests"][:100]],
                "links": [fields(n, "link_id source_id target_id link_type created_at evidence_backed is_inferred") for n in data["links"][:100]],
                "validation": {"valid": valid, "issues": [clean(v) for v in issues[:100]]},
                "truncated": any(len(data[k]) > 100 for k in ("requirements", "features", "tasks", "evidence", "implementations", "tests", "links"))}
    if method == "get_environment_status":
        return environment(data)
    if method == "get_health_report":
        return {"project_id": data["project_id"], "generated_at": data["generated_at"], "environment": environment(data["environment"]),
                "checks": [fields(c, "check_id name status severity message evidence") for c in data["checks"][:100]],
                "dependency_status": [fields(d, "name version_specifier declared installed installed_version status source_file action message") for d in data["dependency_status"][:100]],
                "truncated": len(data["checks"]) > 100 or len(data["dependency_status"]) > 100}
    if method in ("get_intelligence_snapshot", "refresh_workspace"):
        from app.context.project import build_project_context
        context = build_project_context(workspace.project_root, workspace.state_manager.state)
        return {**fields(data, "project_id project_name scan_timestamp"),
                **{k: data[k] for k in ("project_state_summary", "blueprint_summary", "traceability_summary", "environment_summary", "health_summary", "requirement_summary")},
                "drift_summary": [drift(d) for d in data["drift_summary"][:100]],
                "context_coverage": {"sampled_files": len(context["files"]), "characters": sum(len(f["content"]) for f in context["files"]),
                                     "structure_entries": len(context["structure"]), "truncated": context["truncated"], "unavailable_files": len(context["unavailable"])},
                **ProjectIntelligenceContextAdapter(workspace).build_bounded_context()}
    if method == "get_timeline":
        return {"items": timeline(data), "total": len(data), "truncated": len(data) > 100}
    if method == "get_drift_report":
        return drift(data)
    if method == "create_requirement_baseline":
        return {"requirement_id": data["requirement_id"], "captured": True}
    raise ValueError("Unsupported projection")
