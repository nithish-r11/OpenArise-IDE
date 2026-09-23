from typing import List, Optional
from app.project.models import ProjectState
from app.blueprint.models import ProjectBlueprint
from app.environment.models import (
    EnvironmentInfo, DependencyStatus, DependencyState, 
    Severity, HealthCheck, ProjectHealthReport
)

class HealthEngine:
    """Deterministic rules engine for evaluating project health."""
    
    def evaluate(self, state: ProjectState, blueprint: Optional[ProjectBlueprint], 
                 env_info: EnvironmentInfo, deps: List[DependencyStatus]) -> ProjectHealthReport:
                 
        report = ProjectHealthReport(
            project_id=state.project_info.project_id,
            environment=env_info,
            dependency_status=deps,
            health_signals=state.health_signals
        )
        
        # 1. Python Availability
        if not env_info.python_available:
            report.checks.append(HealthCheck(
                name="Python Environment",
                status="Missing",
                severity=Severity.BLOCKED,
                message="No Python interpreter available."
            ))
        else:
            report.checks.append(HealthCheck(
                name="Python Environment",
                status="Available",
                severity=Severity.INFO,
                message=f"Using Python {env_info.python_version}"
            ))
            
        # 2. Virtual Environment Readiness
        if not env_info.virtualenv_present:
            report.checks.append(HealthCheck(
                name="Virtual Environment",
                status="Absent",
                severity=Severity.WARNING,
                message="No local virtual environment (.venv/venv) detected."
            ))
        elif not env_info.virtualenv_usable:
            report.checks.append(HealthCheck(
                name="Virtual Environment",
                status="Unusable",
                severity=Severity.ERROR,
                message="Virtual environment found but Python executable is missing."
            ))
        else:
            report.checks.append(HealthCheck(
                name="Virtual Environment",
                status="Ready",
                severity=Severity.INFO,
                message=f"Local venv detected at {env_info.virtualenv_path}"
            ))
            
        # 3. Dependency declarations and missing deps
        if not state.dependencies:
            report.checks.append(HealthCheck(
                name="Dependencies",
                status="Undeclared",
                severity=Severity.INFO,
                message="No dependencies declared in project."
            ))
            
        for dep in deps:
            if dep.status == DependencyState.MISSING:
                # If blueprint dictates it, severity could be higher, but ERROR is factual
                report.checks.append(HealthCheck(
                    name=f"Dependency: {dep.name}",
                    status="Missing",
                    severity=Severity.ERROR,
                    message=dep.message or f"{dep.name} is missing from environment."
                ))
            elif dep.status == DependencyState.VERSION_MISMATCH:
                report.checks.append(HealthCheck(
                    name=f"Dependency: {dep.name}",
                    status="Version Mismatch",
                    severity=Severity.ERROR,
                    message=dep.message or "Version constraint not met."
                ))
            elif dep.status == DependencyState.INSPECTION_NOT_AVAILABLE:
                report.checks.append(HealthCheck(
                    name=f"Dependency: {dep.name}",
                    status="Uninspected",
                    severity=Severity.WARNING,
                    message="Target environment not inspected."
                ))

        # 4. Git availability
        if not env_info.git_available:
            report.checks.append(HealthCheck(
                name="Version Control",
                status="Git Unavailable",
                severity=Severity.INFO,
                message="Git executable not found in PATH."
            ))

        # 5. Empty project
        if state.health_signals.get("empty_project"):
            report.checks.append(HealthCheck(
                name="Project Content",
                status="Empty",
                severity=Severity.WARNING,
                message="No source files detected in project root."
            ))
            
        # 6. Syntax Errors
        syntax_errors = [m for m in state.python_modules if m.syntax_error]
        if syntax_errors:
            report.checks.append(HealthCheck(
                name="Syntax Errors",
                status="Detected",
                severity=Severity.ERROR,
                message=f"Syntax errors in {len(syntax_errors)} files."
            ))
            
        # 7. Tests
        if state.health_signals.get("no_tests"):
            report.checks.append(HealthCheck(
                name="Test Suite",
                status="No Tests",
                severity=Severity.WARNING,
                message="No test files detected."
            ))
            
        return report
