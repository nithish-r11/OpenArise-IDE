from typing import Dict, List, Optional
import os
from app.project.models import ProjectState
from app.blueprint.models import ProjectBlueprint
from app.traceability.models import ImplementationNode, TestNode, LinkType
from app.traceability.graph import TraceabilityGraphManager

class ImplementationMapper:
    """Maps deterministic project facts to traceability nodes and links."""
    
    def __init__(self, project_id: str):
        self.graph_manager = TraceabilityGraphManager(project_id)
        
    def build_from_state_and_blueprint(self, state: ProjectState, blueprint: ProjectBlueprint):
        # 1. Add Blueprint nodes
        for req_id in blueprint.requirements:
            self.graph_manager.add_requirement(req_id)
            
        for feature in blueprint.features:
            self.graph_manager.add_feature(feature.feature_id)
            for req_id in feature.requirement_ids:
                self.graph_manager.add_link(req_id, feature.feature_id, LinkType.REQUIREMENT_TO_FEATURE)
                
        for task in blueprint.tasks:
            self.graph_manager.add_task(task.task_id)
            if task.feature_id:
                self.graph_manager.add_link(task.feature_id, task.task_id, LinkType.FEATURE_TO_TASK)
                
        # 2. Add Project State nodes
        # Add Implementation Nodes from python modules
        impl_map = {} # path -> ImplementationNode
        test_map = {} # path -> TestNode
        
        for module in state.python_modules:
            is_test_module = os.path.basename(module.relative_path).startswith('test_') or len(module.test_functions) > 0
            if is_test_module:
                # Add test node
                node = TestNode(
                    file_path=module.relative_path,
                    test_name=module.module_name
                )
                self.graph_manager.add_test(node)
                test_map[module.relative_path] = node
            else:
                # Add implementation node
                node = ImplementationNode(
                    file_path=module.relative_path,
                    module_name=module.module_name,
                    symbol_type="module"
                )
                self.graph_manager.add_implementation(node)
                impl_map[module.relative_path] = node
                
        # 3. Infer links based on conventional paths (e.g. tests/test_foo.py -> app/foo.py)
        # Note: These are explicitly marked as is_inferred=True and evidence_backed=False
        for test_path, test_node in test_map.items():
            basename = os.path.basename(test_path)
            if basename.startswith("test_"):
                target_base = basename[5:] # remove test_
                # Look for matching implementation node
                for impl_path, impl_node in impl_map.items():
                    if os.path.basename(impl_path) == target_base:
                        self.graph_manager.add_link(
                            impl_node.implementation_id, 
                            test_node.test_id, 
                            LinkType.IMPLEMENTATION_TO_TEST,
                            is_inferred=True,
                            evidence_backed=False
                        )
                        break
                        
        return self.graph_manager.graph
