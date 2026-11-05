"""
Data models and Change Journal for OpenArise AI Agent Mode.
Provides structured types for agent state, multi-step plans, tool calls,
file change tracking, safe backups, and transaction rollback.
"""

from __future__ import annotations
import shutil
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class AgentTaskState(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    AWAITING_PLAN_APPROVAL = "awaiting_plan_approval"
    EXECUTING = "executing"
    AWAITING_TOOL_APPROVAL = "awaiting_tool_approval"
    AWAITING_DIFF_APPROVAL = "awaiting_diff_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class AgentPlanStep:
    step_number: int
    description: str
    status: str = StepStatus.PENDING.value
    details: str = ""

    def to_dict(self) -> dict:
        return {
            "step_number": self.step_number,
            "description": self.description,
            "status": self.status,
            "details": self.details,
        }


@dataclass
class AgentPlan:
    task_description: str
    steps: list[AgentPlanStep] = field(default_factory=list)
    is_approved: bool = False

    def to_dict(self) -> dict:
        return {
            "task_description": self.task_description,
            "steps": [s.to_dict() for s in self.steps],
            "is_approved": self.is_approved,
        }


@dataclass
class AgentToolCall:
    id: str
    name: str
    args: dict = field(default_factory=dict)
    requires_approval: bool = False
    approved: bool = False
    result: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "args": self.args,
            "requires_approval": self.requires_approval,
            "approved": self.approved,
            "result": self.result,
            "error": self.error,
        }


class FileChangeType(str, Enum):
    CREATE = "create"
    MODIFY = "modify"
    RENAME = "rename"
    DELETE = "delete"


class FileChangeStatus(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"


@dataclass
class FileChangeRecord:
    rel_path: str
    change_type: str = FileChangeType.MODIFY.value
    old_content: Optional[str] = None
    new_content: Optional[str] = None
    backup_path: Optional[Path] = None
    status: str = FileChangeStatus.PROPOSED.value
    error: str = ""

    @property
    def additions_count(self) -> int:
        old_lines = (self.old_content or "").splitlines()
        new_lines = (self.new_content or "").splitlines()
        return max(0, len(new_lines) - len(old_lines)) if len(new_lines) > len(old_lines) else sum(1 for line in new_lines if line not in old_lines)

    @property
    def deletions_count(self) -> int:
        old_lines = (self.old_content or "").splitlines()
        new_lines = (self.new_content or "").splitlines()
        return sum(1 for line in old_lines if line not in new_lines)


class AgentJournal:
    """
    Manages pre-modification file backups, transactional file application,
    and complete rollback for an agent task.
    """

    def __init__(self, project_root: Path, task_id: Optional[str] = None):
        self.project_root = Path(project_root).resolve()
        self.task_id = task_id or f"task_{int(time.time() * 1000)}"
        self.backup_dir = self.project_root / ".openarise_backups" / self.task_id
        self.records: list[FileChangeRecord] = []

    def _resolve(self, rel_path: str) -> Path:
        target = (self.project_root / rel_path).resolve()
        try:
            target.relative_to(self.project_root)
        except ValueError:
            raise ValueError(f"Path traversal detected: '{rel_path}' is outside project root.")
        return target

    def record_change(
        self,
        rel_path: str,
        change_type: str,
        new_content: Optional[str] = None,
        old_content: Optional[str] = None,
    ) -> FileChangeRecord:
        """
        Prepares a change record and creates a backup of the original file if it exists.
        Does NOT apply the change to the actual project file yet.
        """
        target = self._resolve(rel_path)
        backup_path: Optional[Path] = None

        if old_content is None and target.exists() and target.is_file():
            try:
                old_content = target.read_text(encoding="utf-8", errors="replace")
            except Exception:
                old_content = ""

        # Create a disk backup for existing files
        if target.exists() and target.is_file():
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            backup_target = self.backup_dir / rel_path
            backup_target.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(target, backup_target)
                backup_path = backup_target
            except Exception:
                pass

        for existing in self.records:
            if existing.rel_path == rel_path and existing.status == FileChangeStatus.PROPOSED.value:
                existing.new_content = new_content
                existing.change_type = change_type
                return existing

        record = FileChangeRecord(
            rel_path=rel_path,
            change_type=change_type,
            old_content=old_content,
            new_content=new_content,
            backup_path=backup_path,
            status=FileChangeStatus.PROPOSED.value,
        )
        self.records.append(record)
        return record

    def apply_record(self, record: FileChangeRecord) -> bool:
        """Applies an approved change record to disk."""
        target = self._resolve(record.rel_path)
        try:
            if record.change_type in (FileChangeType.CREATE.value, FileChangeType.MODIFY.value):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(record.new_content or "", encoding="utf-8")
                record.status = FileChangeStatus.APPLIED.value
                return True
            elif record.change_type == FileChangeType.DELETE.value:
                if target.exists():
                    target.unlink()
                record.status = FileChangeStatus.APPLIED.value
                return True
        except Exception as exc:
            record.error = str(exc)
            return False
        return False

    def apply_accepted(self) -> tuple[int, list[str]]:
        """Applies all records that have status ACCEPTED."""
        applied_count = 0
        applied_files = []
        for rec in self.records:
            if rec.status == FileChangeStatus.ACCEPTED.value:
                if self.apply_record(rec):
                    applied_count += 1
                    applied_files.append(rec.rel_path)
        return applied_count, applied_files

    def rollback(self) -> tuple[int, list[str]]:
        """
        Reverses all APPLIED changes from this task:
        - For CREATE: deletes the created file.
        - For MODIFY: restores the backup or old content.
        - For DELETE: restores the deleted file.
        """
        rolled_back_count = 0
        rolled_back_files = []

        # Roll back in reverse chronological order
        for rec in reversed(self.records):
            if rec.status != FileChangeStatus.APPLIED.value:
                continue

            target = self._resolve(rec.rel_path)
            try:
                if rec.change_type == FileChangeType.CREATE.value:
                    if target.exists() and target.is_file():
                        target.unlink()
                    rec.status = FileChangeStatus.ROLLED_BACK.value
                    rolled_back_count += 1
                    rolled_back_files.append(rec.rel_path)

                elif rec.change_type == FileChangeType.MODIFY.value:
                    if rec.backup_path and rec.backup_path.exists():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(rec.backup_path, target)
                    elif rec.old_content is not None:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_text(rec.old_content, encoding="utf-8")
                    rec.status = FileChangeStatus.ROLLED_BACK.value
                    rolled_back_count += 1
                    rolled_back_files.append(rec.rel_path)

                elif rec.change_type == FileChangeType.DELETE.value:
                    if rec.backup_path and rec.backup_path.exists():
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(rec.backup_path, target)
                    elif rec.old_content is not None:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_text(rec.old_content, encoding="utf-8")
                    rec.status = FileChangeStatus.ROLLED_BACK.value
                    rolled_back_count += 1
                    rolled_back_files.append(rec.rel_path)
            except Exception as exc:
                rec.error = f"Rollback error: {exc}"

        # Clean up backup folder if empty or safe
        if self.backup_dir.exists():
            try:
                shutil.rmtree(self.backup_dir, ignore_errors=True)
            except Exception:
                pass

        return rolled_back_count, rolled_back_files

