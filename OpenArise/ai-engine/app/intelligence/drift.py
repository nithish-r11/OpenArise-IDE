from app.intelligence.models import DriftFinding, DriftState
from app.traceability.models import LinkType


class RequirementDriftDetector:
    """Compare explicit baselines against the production graph and observed file hashes."""

    def detect_drift(self, baseline, state, blueprint, traceability):
        def finding(status, reason, implementations=None, tasks=None):
            return DriftFinding(
                requirement_id=baseline.requirement_id, state=status, reason=reason,
                related_implementations=implementations or [], related_tasks=tasks or [],
            )

        if blueprint is None or traceability is None:
            return finding(DriftState.UNRESOLVED, "Blueprint or traceability graph missing for evaluation.")
        req_id = baseline.requirement_id
        if req_id not in blueprint.requirements:
            return finding(DriftState.CONFIRMED_STRUCTURAL_DRIFT, "Requirement was removed from blueprint.")
        graph = traceability.graph
        if req_id not in graph.requirements:
            return finding(DriftState.CONFIRMED_STRUCTURAL_DRIFT, "Requirement was removed from traceability.")
        links = {(link.source_id, link.target_id, link.link_type) for link in graph.links}
        features = {f.feature_id: f for f in blueprint.features}
        tasks = {t.task_id: t for t in blueprint.tasks}
        for feature_id in baseline.associated_feature_ids:
            feature = features.get(feature_id)
            if (feature is None or feature_id not in graph.features
                    or req_id not in feature.requirement_ids
                    or (req_id, feature_id, LinkType.REQUIREMENT_TO_FEATURE) not in links):
                return finding(DriftState.CONFIRMED_STRUCTURAL_DRIFT, f"Required feature relationship {feature_id} was removed.")
        for task_id in baseline.associated_task_ids:
            task = tasks.get(task_id)
            if task is None or task_id not in graph.tasks:
                return finding(DriftState.CONFIRMED_STRUCTURAL_DRIFT, f"Required task {task_id} was removed.", tasks=[task_id])
            expected_feature = baseline.task_feature_ids.get(task_id)
            if ((expected_feature and task.feature_id != expected_feature)
                    or (baseline.associated_feature_ids and task.feature_id not in baseline.associated_feature_ids)
                    or (task.feature_id, task_id, LinkType.FEATURE_TO_TASK) not in links):
                return finding(DriftState.CONFIRMED_STRUCTURAL_DRIFT, f"Feature/task relationship for {task_id} was removed.", tasks=[task_id])

        impls = {node.implementation_id: node for node in graph.implementations}
        files = {file.relative_path: file for file in state.files}
        changed = []
        unresolved = []
        for impl_id in baseline.implementation_ids:
            node = impls.get(impl_id)
            if node is None or node.file_path not in files:
                return finding(DriftState.CONFIRMED_STRUCTURAL_DRIFT, f"Mapped implementation {impl_id} was removed.", [impl_id])
            directly_linked = (req_id, impl_id, LinkType.REQUIREMENT_TO_IMPLEMENTATION) in links
            task_linked = any((task_id, impl_id, LinkType.TASK_TO_IMPLEMENTATION) in links
                              for task_id in baseline.associated_task_ids)
            if not directly_linked and not task_linked:
                return finding(DriftState.CONFIRMED_STRUCTURAL_DRIFT, f"Implementation relationship {impl_id} was removed.", [impl_id])
            expected = baseline.implementation_hashes.get(impl_id)
            if expected is None and len(baseline.implementation_ids) == 1:
                expected = baseline.content_hash
            actual = files[node.file_path].content_hash
            if not expected or not actual:
                unresolved.append(impl_id)
            elif expected != actual:
                changed.append(impl_id)

        for evidence_id in baseline.evidence_ids:
            if (evidence_id not in graph.evidence
                    or (req_id, evidence_id, LinkType.REQUIREMENT_TO_EVIDENCE) not in links):
                return finding(DriftState.UNRESOLVED, f"Invalid or missing evidence reference: {evidence_id}")
        if unresolved:
            return finding(DriftState.UNRESOLVED, "Related implementation hashes are unavailable.", unresolved)
        if changed:
            return finding(DriftState.POTENTIAL_DRIFT, "Related implementation content hashes changed.", changed)
        return finding(DriftState.NO_DRIFT, "No drift detected in the recorded relationships and hashes.")
