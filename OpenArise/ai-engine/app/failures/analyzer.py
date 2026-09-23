from typing import Dict, Any, Optional
from app.llm.base import LLMProvider
from app.models.schemas import FailureEvent, DiagnosisResult, ConfidenceLevel, FailureCategory

SYSTEM_PROMPT = """You are an expert software engineering diagnostician.
Analyze the provided failure evidence and output a structured diagnosis.
Be deterministic and concise.
If the evidence is ambiguous or incomplete, set confidence to LOW.
Do not pretend certainty when you are guessing."""

class RootCauseAnalyzer:
    """Diagnoses failures combining deterministic evidence and LLM assistance."""
    
    def __init__(self, llm_provider: LLMProvider):
        self.llm = llm_provider
        
    def analyze(self, failure: FailureEvent) -> DiagnosisResult:
        """
        Performs root cause analysis on a FailureEvent.
        First tries deterministic, then falls back to LLM if ambiguous.
        """
        # If deterministic detection already confidently classified it, use it.
        # But if it's UNKNOWN or we need deeper root cause, ask LLM.
        
        if failure.category not in (FailureCategory.UNKNOWN, FailureCategory.RUNTIME_ERROR) and failure.root_cause:
            # We already have a strong deterministic diagnosis
            return DiagnosisResult(
                category=failure.category,
                summary=failure.summary,
                probable_root_cause=failure.root_cause,
                affected_tool=failure.tool_name,
                affected_file=failure.affected_file,
                suggested_next_investigation="Fix the identified error.",
                confidence=ConfidenceLevel.HIGH
            )
            
        # Fallback to LLM for deep diagnosis
        prompt = f"""Analyze the following failure:
Tool: {failure.tool_name}
Category: {failure.category}
Summary: {failure.summary}
Evidence:
{failure.evidence}

Provide a structured diagnosis."""

        try:
            diagnosis: DiagnosisResult = self.llm.generate_structured(
                prompt=prompt,
                schema=DiagnosisResult,
                system_prompt=SYSTEM_PROMPT
            )
            return diagnosis
        except Exception as e:
            # If LLM fails, return safe fallback
            return DiagnosisResult(
                category=failure.category,
                summary=failure.summary,
                probable_root_cause=f"Analysis failed: {str(e)}",
                affected_tool=failure.tool_name,
                affected_file=failure.affected_file,
                suggested_next_investigation="Investigate manually.",
                confidence=ConfidenceLevel.LOW
            )
