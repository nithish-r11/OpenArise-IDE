from typing import Optional, List
from app.models.schemas import FailureEvent, DiagnosisResult, RecoveryPlan, ToolCall, FailureCategory
from app.llm.base import LLMProvider
from app.tools.permissions import RiskLevel
from app.memory.manager import MemoryManager

PLANNER_SYSTEM_PROMPT = """You are an expert recovery planner.
Create a safe, minimal RecoveryPlan for the provided software failure.
Propose only concrete ToolCalls for existing tools.
Do not use unrestricted shell commands.
Prefer editing specific files or writing minimal scripts."""

class RecoveryPlanner:
    """Plans recovery actions for failures."""
    
    def __init__(self, llm_provider: LLMProvider, memory_manager: Optional[MemoryManager] = None):
        self.llm = llm_provider
        self.memory = memory_manager
        
    def plan(self, failure: FailureEvent, diagnosis: DiagnosisResult) -> Optional[RecoveryPlan]:
        """Generates a recovery plan for a diagnosed failure."""
        
        # Memory Context
        historical_context = ""
        if self.memory:
            past_memories = self.memory.search_relevant(failure)
            if past_memories:
                historical_context = "Historical Recovery Attempts:\n"
                for mem in past_memories:
                    historical_context += f"- Outcome: {mem.outcome}\n  Plan: {mem.recovery_plan}\n"
        
        # Deterministic Rules
        if diagnosis.category == FailureCategory.IMPORT_ERROR:
            # Deterministic missing dependency recovery
            # Propose writing requirements.txt and running pip install within sandbox via python execution
            # But the prompt requires "Install only into the project-managed Python environment when supported"
            # We can use python_execution tool to run pip install
            # Assuming 'execute_python' tool exists
            plan = RecoveryPlan(
                failure_id=failure.failure_id,
                goal=f"Install missing dependency for {diagnosis.probable_root_cause}",
                diagnosis_summary=diagnosis.summary,
                expected_result="Missing module is installed and import succeeds",
                risk_level=RiskLevel.EXECUTE,
                requires_permission=True
            )
            # A safe way to install in project: python -m pip install <pkg>
            # Actually, PythonExecutionTool executes a python file. We could write an install script.
            script_content = f"import subprocess\nimport sys\nsubprocess.check_call([sys.executable, '-m', 'pip', 'install', '{diagnosis.probable_root_cause}'])\n"
            plan.proposed_actions = [
                ToolCall(tool_name="write_file", arguments={"path": "install_dep.py", "content": script_content}),
                ToolCall(tool_name="execute_python", arguments={"script_path": "install_dep.py"})
            ]
            return plan
            
        if diagnosis.category == FailureCategory.TIMEOUT:
            # Maybe just try one more time if it's intermittent, but normally we might not have a fix without LLM
            pass
            
        # Fallback to LLM Planning
        prompt = f"""Create a recovery plan for this failure.
Diagnosis: {diagnosis.model_dump_json()}
Evidence: {failure.evidence}

{historical_context}
"""
        try:
            plan = self.llm.generate_structured(
                prompt=prompt,
                schema=RecoveryPlan,
                system_prompt=PLANNER_SYSTEM_PROMPT
            )
            plan = RecoveryPlan.model_validate(plan)
            plan.failure_id = failure.failure_id
            
            # Determine Risk and Permission automatically based on proposed actions
            plan.requires_permission = True
            plan.risk_level = RiskLevel.EXECUTE
            for action in plan.proposed_actions:
                if action.tool_name in ("write_file", "edit_file"):
                    plan.risk_level = max(plan.risk_level, RiskLevel.WRITE)
            return plan
        except Exception:
            return None
