import re
from typing import List
from app.models.schemas import Requirement, VerificationStatus
from app.llm.base import LLMProvider
from app.agent.requested_steps import positive_tool_mentions, requested_steps


def requested_execution_criteria(text):
    """Retain explicit tool steps, including repetitions, without guessing tasks."""
    counts = {}
    for name, _, _ in positive_tool_mentions(text):
        counts[name] = counts.get(name, 0) + 1
    criteria = [f'required_tool_count:{name}:{count}' for name, count in counts.items()]
    if re.search(r'\b(?:demonstrate|perform|attempt|use|let)\b[^.!?\n;]{0,100}\brecovery\b', text, re.I):
        criteria.append('required_recovery')
    return criteria


class RequirementExtractor:
    """Conservatively retain user requirements without inventing acceptance criteria."""

    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider

    def extract(self, user_request: str) -> List[Requirement]:
        lines = [line.strip() for line in user_request.splitlines() if line.strip()]
        has_list = any(re.match(r"^(?:[-*] |\d+[.)] )", line) for line in lines)
        # A named ordered action sequence is one workflow with a shared identity;
        # its preamble and procedural steps are not independent product features.
        ordered_workflow = len(requested_steps(user_request)) > 1
        descriptions = [re.sub(r"^(?:[-*] |\d+[.)] )", "", line) for line in lines] if has_list and not ordered_workflow else [user_request]
        return [Requirement(
            title=text[:80], description=text, source_text=text,
            acceptance_criteria=requested_execution_criteria(text),
            status=VerificationStatus.INCONCLUSIVE,
        ) for text in descriptions if text.strip()]
