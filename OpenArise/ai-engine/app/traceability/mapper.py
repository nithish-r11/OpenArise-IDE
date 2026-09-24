import os
import uuid
from app.traceability.models import ImplementationNode, TestNode, LinkType, TraceabilityGraph
from app.traceability.graph import TraceabilityGraphManager


class ImplementationMapper:
    """Rebuild observed nodes on the existing manager, retaining valid explicit associations."""

    def __init__(self, project_id):
        self.graph_manager = TraceabilityGraphManager(project_id)

    def _id(self, kind, path):
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{self.graph_manager.graph.project_id}:{kind}:{path}"))

    def build_from_state_and_blueprint(self, state, blueprint):
        previous = self.graph_manager.graph
        old_impls = {node.file_path: node for node in previous.implementations}
        old_tests = {node.file_path: node for node in previous.tests}
        self.graph_manager.graph = TraceabilityGraph(
            project_id=state.project_info.project_id, evidence=list(previous.evidence)
        )
        manager = self.graph_manager
        for req_id in blueprint.requirements:
            manager.add_requirement(req_id)
        for feature in blueprint.features:
            manager.add_feature(feature.feature_id)
            for req_id in feature.requirement_ids:
                manager.add_link(req_id, feature.feature_id, LinkType.REQUIREMENT_TO_FEATURE)
        for task in blueprint.tasks:
            manager.add_task(task.task_id)
            manager.add_link(task.feature_id, task.task_id, LinkType.FEATURE_TO_TASK)
        for module in sorted(state.python_modules, key=lambda item: item.relative_path):
            is_test = os.path.basename(module.relative_path).startswith("test_") or bool(module.test_functions)
            if is_test:
                node = old_tests.get(module.relative_path)
                node = node.model_copy(deep=True) if node else TestNode(
                    test_id=self._id("test", module.relative_path),
                    file_path=module.relative_path, test_name=module.module_name,
                )
                manager.add_test(node)
            else:
                node = old_impls.get(module.relative_path)
                node = node.model_copy(deep=True) if node else ImplementationNode(
                    implementation_id=self._id("implementation", module.relative_path),
                    file_path=module.relative_path, module_name=module.module_name, symbol_type="module",
                )
                manager.add_implementation(node)
        for test in manager.graph.tests:
            name = os.path.basename(test.file_path)
            if name.startswith("test_"):
                matches = [node for node in manager.graph.implementations if os.path.basename(node.file_path) == name[5:]]
                # Ambiguous filenames are not sufficient even for an inferred association.
                if len(matches) == 1:
                    manager.add_link(matches[0].implementation_id, test.test_id,
                                     LinkType.IMPLEMENTATION_TO_TEST, is_inferred=True)
        node_ids = set(manager.graph.requirements + manager.graph.features + manager.graph.tasks + manager.graph.evidence)
        node_ids.update(node.implementation_id for node in manager.graph.implementations)
        node_ids.update(node.test_id for node in manager.graph.tests)
        retained_types = {LinkType.TASK_TO_IMPLEMENTATION, LinkType.REQUIREMENT_TO_IMPLEMENTATION,
                          LinkType.TEST_TO_EVIDENCE, LinkType.REQUIREMENT_TO_EVIDENCE}
        for link in previous.links:
            if link.link_type in retained_types and link.source_id in node_ids and link.target_id in node_ids:
                manager.add_link(link.source_id, link.target_id, link.link_type, link.evidence_backed, link.is_inferred)
        return manager.graph
