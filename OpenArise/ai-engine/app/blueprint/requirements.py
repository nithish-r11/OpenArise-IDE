from typing import Dict, List, Optional
from app.models.schemas import Requirement, RequirementLifecycleStatus
import re

class RequirementManager:
    """Manages the lifecycle and normalization of Requirement objects."""
    
    def __init__(self):
        self._requirements: Dict[str, Requirement] = {}
        
    def _normalize_text(self, text: str) -> str:
        """Deterministically normalize text for duplicate detection."""
        if not text:
            return ""
        # Lowercase, remove non-alphanumeric, strip whitespace
        normalized = re.sub(r'[^a-z0-9]', '', text.lower().strip())
        return normalized

    def _is_duplicate(self, title: str, description: str) -> bool:
        """Check if a requirement with same normalized title or description exists."""
        norm_title = self._normalize_text(title)
        norm_desc = self._normalize_text(description)
        
        for req in self._requirements.values():
            if norm_title and self._normalize_text(req.title) == norm_title:
                return True
            if norm_desc and self._normalize_text(req.description) == norm_desc:
                return True
        return False

    def create_requirement(self, title: str, description: str, priority: str = "HIGH",
                           source_text: Optional[str] = None, 
                           acceptance_criteria: Optional[List[str]] = None) -> Optional[Requirement]:
        """Create a new requirement, returning None if it is a duplicate."""
        if self._is_duplicate(title, description):
            return None
            
        req = Requirement(
            title=title,
            description=description,
            priority=priority,
            source_text=source_text,
            acceptance_criteria=acceptance_criteria or []
        )
        self._requirements[req.requirement_id] = req
        return req

    def get_requirement(self, requirement_id: str) -> Optional[Requirement]:
        return self._requirements.get(requirement_id)

    def list_requirements(self) -> List[Requirement]:
        return list(self._requirements.values())

    def update_requirement(self, requirement_id: str, title: Optional[str] = None, 
                           description: Optional[str] = None, 
                           acceptance_criteria: Optional[List[str]] = None) -> Optional[Requirement]:
        req = self.get_requirement(requirement_id)
        if not req:
            return None
            
        if title is not None:
            req.title = title
        if description is not None:
            req.description = description
        if acceptance_criteria is not None:
            req.acceptance_criteria = acceptance_criteria
            
        return req

    def mark_status(self, requirement_id: str, status: RequirementLifecycleStatus) -> bool:
        req = self.get_requirement(requirement_id)
        if not req:
            return False
        req.lifecycle_status = status
        return True

    def associate_feature(self, requirement_id: str, feature_id: str) -> bool:
        req = self.get_requirement(requirement_id)
        if not req:
            return False
        if feature_id not in req.implementation_references:
            req.implementation_references.append(feature_id)
        return True
