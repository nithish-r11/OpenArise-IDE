import pytest
import os
import tempfile
import json
from app.models.schemas import FailureEvent, FailureCategory, DiagnosisResult, ConfidenceLevel, RecoveryResult, RecoveryState
from app.memory.redact import SecretRedactor
from app.memory.store import SQLiteMemoryStore
from app.memory.manager import MemoryManager
from app.memory.export import MemoryExporter

@pytest.fixture
def memory_manager():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield MemoryManager(temp_dir)

def test_secret_redactor():
    redactor = SecretRedactor()
    
    # API Keys
    assert "sk-" not in redactor.redact("My key is sk-1234567890abcdef12345678")
    assert "api_key" in redactor.redact("api_key = 'sk-something'")
    assert "REDACTED" in redactor.redact("api_key = 'sk-something'")
    
    # Dict redaction
    data = {"evidence": "password: my_secret_pass!"}
    redacted = redactor.redact_dict(data)
    assert "my_secret_pass" not in redacted["evidence"]
    assert "REDACTED" in redacted["evidence"]

def test_sqlite_memory_store(memory_manager):
    # 1. Record Failure
    failure = FailureEvent(
        failure_id="f1",
        category=FailureCategory.IMPORT_ERROR,
        summary="Module not found: password: 'secret'",
        error_signature="execute_python:IMPORT_ERROR:fastapi"
    )
    
    record = memory_manager.record_failure(failure)
    
    # Verify Redaction worked on save
    saved = memory_manager.get_memory(record.memory_id)
    assert "secret" not in saved.summary
    assert "REDACTED" in saved.summary
    
    # 2. Update Diagnosis
    diagnosis = DiagnosisResult(
        category=FailureCategory.IMPORT_ERROR,
        summary="Missing fastapi",
        probable_root_cause="fastapi",
        confidence=ConfidenceLevel.HIGH
    )
    memory_manager.update_with_diagnosis(record.memory_id, diagnosis)
    
    saved = memory_manager.get_memory(record.memory_id)
    assert saved.root_cause == "fastapi"
    assert saved.diagnosis_confidence == ConfidenceLevel.HIGH
    
    # 3. Update Recovery
    result = RecoveryResult(
        recovery_id="r1",
        failure_id="f1",
        status=RecoveryState.RECOVERED,
        actions_executed=["write_file", "execute_python"],
        final_result="Success",
        failure_signature_before="execute_python:IMPORT_ERROR:fastapi",
        evidence={"exit_code": 0}
    )
    memory_manager.update_with_recovery(record.memory_id, result)
    
    saved = memory_manager.get_memory(record.memory_id)
    assert saved.outcome == RecoveryState.RECOVERED
    assert saved.attempt_count == 1
    assert "execute_python" in saved.recovery_actions
    assert saved.test_evidence["exit_code"] == 0
    
    # 4. Search Relevant
    results = memory_manager.search_relevant(failure)
    assert len(results) == 1
    assert results[0].memory_id == record.memory_id
    
    # 5. Project Isolation
    with tempfile.TemporaryDirectory() as temp_dir2:
        manager2 = MemoryManager(temp_dir2)
        # Assuming temp_dir2 basename is different project_id
        results2 = manager2.search_relevant(failure)
        assert len(results2) == 0

def test_memory_export(memory_manager):
    failure = FailureEvent(
        failure_id="f2",
        category=FailureCategory.SYNTAX_ERROR,
        summary="SyntaxError: invalid syntax",
        error_signature="sig2"
    )
    record = memory_manager.record_failure(failure)
    
    result = RecoveryResult(
        recovery_id="r2",
        failure_id="f2",
        status=RecoveryState.FAILED,
        final_result="Failed",
        failure_signature_before="sig2"
    )
    memory_manager.update_with_recovery(record.memory_id, result)
    
    # Export
    export_path = os.path.join(memory_manager.store.db_dir, "export.jsonl")
    exporter = MemoryExporter(memory_manager)
    exporter.export_jsonl(export_path)
    
    assert os.path.exists(export_path)
    with open(export_path, "r") as f:
        lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["outcome"] == RecoveryState.FAILED.value
        assert data["failure"] == "sig2"

def test_memory_statistics(memory_manager):
    stats = memory_manager.get_statistics()
    assert stats["total_failures"] == 0
    
    failure = FailureEvent(
        failure_id="f3",
        summary="test"
    )
    record = memory_manager.record_failure(failure)
    
    result = RecoveryResult(
        recovery_id="r3",
        failure_id="f3",
        status=RecoveryState.RECOVERED,
        final_result="Success",
        failure_signature_before="test"
    )
    memory_manager.update_with_recovery(record.memory_id, result)
    
    stats = memory_manager.get_statistics()
    assert stats["total_failures"] == 1
    assert stats["successful_recoveries"] == 1
