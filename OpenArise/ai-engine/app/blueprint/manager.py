from typing import Dict, List, Optional, Tuple
from app.project.models import ProjectState
from app.blueprint.models import ProjectBlueprint, FeatureItem, TaskItem
from app.blueprint.requirements import RequirementManager
from app.models.schemas import Requirement

class BlueprintManager:
    """Manages creation and validation of Project Blueprints."""
    
    def __init__(self, requirement_manager: RequirementManager):
        self.req_manager = requirement_manager
        
    def generate_initial_blueprint(self, project_state: ProjectState, user_request: str) -> ProjectBlueprint:
        """Deterministically generates an initial blueprint based on state and request."""
        # Note: True AI generation is deferred. This establishes structure.
        
        req_ids = [req.requirement_id for req in self.req_manager.list_requirements()]
        
        description = f"Generated blueprint for project {project_state.project_info.name}."
        if project_state.health_signals.get("no_tests"):
            description += " Project lacks tests."
            
        blueprint = ProjectBlueprint(
            project_id=project_state.project_info.project_id,
            project_name=project_state.project_info.name,
            description=description,
            requirements=req_ids,
            source_request=user_request
        )
        return blueprint

    def validate_traceability(self, blueprint: ProjectBlueprint) -> Tuple[bool, List[str]]:
        """Validates the blueprint traceability rules."""
        errors = []
        
        # 1. Missing requirement references
        known_reqs = set(blueprint.requirements)
        for feature in blueprint.features:
            if not feature.requirement_ids:
                errors.append(f"Feature {feature.feature_id} has no requirement references.")
            for req_id in feature.requirement_ids:
                if req_id not in known_reqs:
                    errors.append(f"Feature {feature.feature_id} references unknown requirement {req_id}.")
                    
        # 2. Missing feature references / Orphaned tasks
        known_features = {f.feature_id for f in blueprint.features}
        for task in blueprint.tasks:
            if not task.feature_id:
                errors.append(f"Task {task.task_id} has no feature reference.")
            elif task.feature_id not in known_features:
                errors.append(f"Task {task.task_id} references unknown feature {task.feature_id}.")
                
        # 3. Duplicate IDs
        all_ids = set()
        for item_list in (blueprint.requirements, [f.feature_id for f in blueprint.features], [t.task_id for t in blueprint.tasks]):
            for item_id in item_list:
                if item_id in all_ids:
                    errors.append(f"Duplicate ID detected: {item_id}")
                all_ids.add(item_id)
                
        # 4. Circular task dependencies
        task_dict = {t.task_id: t for t in blueprint.tasks}
        
        def has_cycle(current_id: str, visited: set, stack: set) -> bool:
            visited.add(current_id)
            stack.add(current_id)
            
            task = task_dict.get(current_id)
            if task:
                for dep in task.dependencies:
                    if dep not in visited:
                        if has_cycle(dep, visited, stack):
                            return True
                    elif dep in stack:
                        return True
            
            stack.remove(current_id)
            return False
            
        visited_tasks = set()
        for task_id in task_dict:
            if task_id not in visited_tasks:
                if has_cycle(task_id, visited_tasks, set()):
                    errors.append(f"Circular dependency detected involving task {task_id}.")
                    
        return len(errors) == 0, errors
