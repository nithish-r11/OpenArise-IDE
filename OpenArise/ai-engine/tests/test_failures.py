import pytest
from app.models.schemas import ToolResult, FailureCategory, FailureEvent, ConfidenceLevel, DiagnosisResult
from app.failures.detector import FailureDetector
from app.failures.history import FailureHistoryManager
from app.failures.analyzer import RootCauseAnalyzer
from tests.mock_llm import MockLLMProvider

def test_failure_detector_deterministic():
    detector = FailureDetector()
    
    # 1. Timeout
    res1 = ToolResult(tool_name="test_tool", tool_call_id="1", success=False, error="Execution timed out", output={"stderr": ""})
    detection1 = detector.detect(res1)
    assert detection1["category"] == FailureCategory.TIMEOUT
    assert "test_tool:TIMEOUT:" in detection1["error_signature"]
    
    # 2. ModuleNotFoundError
    res2 = ToolResult(tool_name="test_tool", tool_call_id="2", success=False, output={"stderr": "ModuleNotFoundError: No module named 'requests'"})
    detection2 = detector.detect(res2)
    assert detection2["category"] == FailureCategory.IMPORT_ERROR
    assert "requests" in detection2["error_signature"]
    
    # 3. FileNotFoundError
    res3 = ToolResult(tool_name="test_tool", tool_call_id="3", success=False, output={"stderr": "FileNotFoundError: [Errno 2] No such file or directory: 'missing.txt'"})
    detection3 = detector.detect(res3)
    assert detection3["category"] == FailureCategory.FILE_NOT_FOUND
    assert "missing.txt" in detection3["error_signature"]
    
    # 4. Permission Error
    res4 = ToolResult(tool_name="test_tool", tool_call_id="4", success=False, error="permission_required")
    detection4 = detector.detect(res4)
    assert detection4["category"] == FailureCategory.PERMISSION_ERROR

def test_failure_history_manager():
    manager = FailureHistoryManager(max_history=5, loop_threshold=3)
    
    # Add failures
    for i in range(5):
        event = FailureEvent(
            failure_id=str(i),
            tool_name="broken_tool",
            category=FailureCategory.SYNTAX_ERROR,
            summary="Syntax error",
            error_signature="broken_tool:SYNTAX_ERROR:line 1"
        )
        manager.record_failure(event)
        
    assert len(manager.list_recent()) == 5
    
    # Add one more to trigger eviction
    event6 = FailureEvent(failure_id="6", summary="test")
    manager.record_failure(event6)
    
    assert len(manager.list_recent()) == 5
    assert manager.get_failure("0") is None  # Evicted
    assert manager.get_failure("6") is not None
    
    # Test Loop Detection
    # Currently history has 4 syntax errors for broken_tool and 1 unknown for 6
    assert manager.detect_loop("broken_tool", "broken_tool:SYNTAX_ERROR:line 1") is False # not consecutive because event 6 interrupted it
    
    # If we add 3 consecutive identical ones
    for i in range(7, 10):
        manager.record_failure(FailureEvent(
            failure_id=str(i),
            tool_name="bad_tool",
            category=FailureCategory.UNKNOWN,
            summary="test",
            error_signature="sig_bad"
        ))
        
    assert manager.detect_loop("bad_tool", "sig_bad") is True

def test_root_cause_analyzer():
    llm = MockLLMProvider(healthy=True)
    analyzer = RootCauseAnalyzer(llm)
    
    # Test fast deterministic return
    event1 = FailureEvent(
        category=FailureCategory.IMPORT_ERROR,
        summary="Module not found",
        root_cause="Missing package 'requests'"
    )
    result1 = analyzer.analyze(event1)
    assert result1.confidence == ConfidenceLevel.HIGH
    assert result1.category == FailureCategory.IMPORT_ERROR
    
    # Test LLM fallback
    event2 = FailureEvent(
        category=FailureCategory.UNKNOWN,
        summary="Something went wrong",
        tool_name="magic_tool",
        evidence={"output": "segmentation fault"}
    )
    
    # Configure mock
    mock_diagnosis = DiagnosisResult(
        category=FailureCategory.UNKNOWN,
        summary="Segfault occurred",
        probable_root_cause="Memory error",
        confidence=ConfidenceLevel.LOW
    )
    llm.structured_response = mock_diagnosis
    
    result2 = analyzer.analyze(event2)
    assert result2.confidence == ConfidenceLevel.LOW
    assert result2.probable_root_cause == "Memory error"
