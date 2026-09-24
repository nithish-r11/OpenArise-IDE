import re
from typing import List
from app.models.schemas import Requirement, VerificationStatus
from app.llm.base import LLMProvider


class RequirementExtractor:
    """Conservatively retain user requirements without inventing acceptance criteria."""

    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider

    def extract(self, user_request: str) -> List[Requirement]:
        lines = [line.strip() for line in user_request.splitlines() if line.strip()]
        has_list = any(re.match(r"^(?:[-*] |\d+[.)] )", line) for line in lines)
        descriptions = [re.sub(r"^(?:[-*] |\d+[.)] )", "", line) for line in lines] if has_list else [user_request]
        return [Requirement(
            title=text[:80], description=text, source_text=text,
            status=VerificationStatus.INCONCLUSIVE,
        ) for text in descriptions if text.strip()]
