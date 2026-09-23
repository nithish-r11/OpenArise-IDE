import sqlite3
import os
import json
import logging
from typing import List, Optional, Dict, Any
from contextlib import closing
from app.models.schemas import FailureMemoryRecord
from app.memory.redact import SecretRedactor

logger = logging.getLogger(__name__)

class SQLiteMemoryStore:
    """SQLite implementation for persistent failure memory."""
    
    def __init__(self, project_root: str):
        self.project_root = os.path.abspath(project_root)
        self.db_dir = os.path.join(self.project_root, ".openarise", "memory")
        self.db_path = os.path.join(self.db_dir, "memory.sqlite")
        self.redactor = SecretRedactor()
        self._ensure_db()
        
    def _ensure_db(self):
        os.makedirs(self.db_dir, exist_ok=True)
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS failures (
                    memory_id TEXT PRIMARY KEY,
                    project_id TEXT,
                    session_id TEXT,
                    failure_id TEXT,
                    failure_signature TEXT,
                    tool_name TEXT,
                    category TEXT,
                    summary TEXT,
                    root_cause TEXT,
                    diagnosis_confidence TEXT,
                    affected_file TEXT,
                    recovery_plan TEXT,
                    recovery_actions TEXT,
                    test_evidence TEXT,
                    outcome TEXT,
                    rollback_performed INTEGER,
                    attempt_count INTEGER,
                    created_at TEXT,
                    updated_at TEXT,
                    tags TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sig ON failures(failure_signature)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_proj ON failures(project_id)")
            conn.commit()
            
    def _to_json(self, data: Any) -> str:
        return json.dumps(data) if data is not None else "{}"
        
    def _from_json(self, text: str) -> Any:
        try:
            return json.loads(text)
        except:
            return {}
            
    def save(self, record: FailureMemoryRecord):
        """Insert or update a memory record."""
        # Redact secrets before saving
        summary = self.redactor.redact(record.summary)
        root_cause = self.redactor.redact(record.root_cause) if record.root_cause else None
        
        # We don't redact the entire recovery_plan arbitrarily, but we redact evidence
        test_evidence = self.redactor.redact_dict(record.test_evidence)
        
        with closing(sqlite3.connect(self.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO failures (
                    memory_id, project_id, session_id, failure_id, failure_signature, tool_name,
                    category, summary, root_cause, diagnosis_confidence, affected_file,
                    recovery_plan, recovery_actions, test_evidence, outcome, rollback_performed,
                    attempt_count, created_at, updated_at, tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(memory_id) DO UPDATE SET
                    root_cause=excluded.root_cause,
                    diagnosis_confidence=excluded.diagnosis_confidence,
                    recovery_plan=excluded.recovery_plan,
                    recovery_actions=excluded.recovery_actions,
                    test_evidence=excluded.test_evidence,
                    outcome=excluded.outcome,
                    rollback_performed=excluded.rollback_performed,
                    attempt_count=excluded.attempt_count,
                    updated_at=excluded.updated_at
            """, (
                record.memory_id, record.project_id, record.session_id, record.failure_id,
                record.failure_signature, record.tool_name, record.category.value, summary,
                root_cause, record.diagnosis_confidence.value, record.affected_file,
                self._to_json(record.recovery_plan), self._to_json(record.recovery_actions),
                self._to_json(test_evidence), record.outcome.value if record.outcome else None,
                1 if record.rollback_performed else 0, record.attempt_count,
                record.created_at, record.updated_at, self._to_json(record.tags)
            ))
            conn.commit()
            
    def get(self, memory_id: str) -> Optional[FailureMemoryRecord]:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM failures WHERE memory_id = ?", (memory_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_record(row)
            
    def find_by_signature(self, project_id: str, signature: str, limit: int = 5) -> List[FailureMemoryRecord]:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM failures 
                WHERE project_id = ? AND failure_signature = ?
                ORDER BY updated_at DESC LIMIT ?
            """, (project_id, signature, limit))
            return [self._row_to_record(row) for row in cursor.fetchall()]

    def list_recent(self, project_id: str, limit: int = 10) -> List[FailureMemoryRecord]:
        with closing(sqlite3.connect(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM failures 
                WHERE project_id = ?
                ORDER BY updated_at DESC LIMIT ?
            """, (project_id, limit))
            return [self._row_to_record(row) for row in cursor.fetchall()]

    def _row_to_record(self, row: sqlite3.Row) -> FailureMemoryRecord:
        data = dict(row)
        data['recovery_plan'] = self._from_json(data['recovery_plan'])
        data['recovery_actions'] = self._from_json(data['recovery_actions'])
        data['test_evidence'] = self._from_json(data['test_evidence'])
        data['tags'] = self._from_json(data['tags'])
        data['rollback_performed'] = bool(data['rollback_performed'])
        return FailureMemoryRecord(**data)
