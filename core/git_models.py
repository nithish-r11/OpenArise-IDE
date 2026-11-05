"""
Data models and representations for Git source control in OpenArise IDE.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional


class GitFileStatusType(str, Enum):
    MODIFIED = "M"
    ADDED = "A"
    DELETED = "D"
    RENAMED = "R"
    COPIED = "C"
    UNTRACKED = "?"
    IGNORED = "!"
    CONFLICT = "U"


STATUS_LABELS = {
    GitFileStatusType.MODIFIED.value: "Modified",
    GitFileStatusType.ADDED.value: "Added",
    GitFileStatusType.DELETED.value: "Deleted",
    GitFileStatusType.RENAMED.value: "Renamed",
    GitFileStatusType.COPIED.value: "Copied",
    GitFileStatusType.UNTRACKED.value: "Untracked",
    GitFileStatusType.IGNORED.value: "Ignored",
    GitFileStatusType.CONFLICT.value: "Conflict",
}

STATUS_COLORS = {
    GitFileStatusType.MODIFIED.value: "#e5c07b",  # Amber/Yellow
    GitFileStatusType.ADDED.value: "#98c379",     # Green
    GitFileStatusType.DELETED.value: "#e06c75",   # Red
    GitFileStatusType.RENAMED.value: "#61afef",   # Cyan/Blue
    GitFileStatusType.UNTRACKED.value: "#73c991", # Light Green
    GitFileStatusType.CONFLICT.value: "#e88388",  # Coral / Red
}


@dataclass
class GitFileChange:
    """Represents a single changed file in Git working tree or index."""
    path: str
    status_type: GitFileStatusType
    is_staged: bool
    old_path: Optional[str] = None

    @property
    def display_name(self) -> str:
        p = Path(self.path)
        return p.name

    @property
    def dir_name(self) -> str:
        p = Path(self.path)
        return str(p.parent) if p.parent != Path(".") else ""

    @property
    def status_label(self) -> str:
        return STATUS_LABELS.get(self.status_type.value, "Changed")

    @property
    def status_color(self) -> str:
        return STATUS_COLORS.get(self.status_type.value, "#abb2bf")


@dataclass
class GitBranch:
    """Represents a local or remote Git branch."""
    name: str
    is_current: bool = False
    tracking_remote: Optional[str] = None
    is_remote: bool = False


@dataclass
class GitCommit:
    """Represents a commit entry in Git history."""
    sha: str
    short_sha: str
    author_name: str
    author_email: str
    date_str: str
    timestamp: int
    message: str


@dataclass
class GitRepoState:
    """Complete snapshot of a repository's status."""
    is_repo: bool
    root_path: Optional[Path] = None
    current_branch: str = ""
    staged_files: List[GitFileChange] = field(default_factory=list)
    unstaged_files: List[GitFileChange] = field(default_factory=list)
    untracked_files: List[GitFileChange] = field(default_factory=list)
    conflict_files: List[GitFileChange] = field(default_factory=list)
    ahead_count: int = 0
    behind_count: int = 0

    @property
    def is_clean(self) -> bool:
        return not (self.staged_files or self.unstaged_files or self.untracked_files or self.conflict_files)

    @property
    def total_changed_count(self) -> int:
        return len(self.staged_files) + len(self.unstaged_files) + len(self.untracked_files) + len(self.conflict_files)


@dataclass
class DiffLine:
    """A line within a unified diff."""
    line_type: str  # ' ', '+', '-', '@'
    old_line_num: Optional[int]
    new_line_num: Optional[int]
    content: str


@dataclass
class DiffFile:
    """Structured diff representation for a file."""
    path: str
    old_path: Optional[str] = None
    lines: List[DiffLine] = field(default_factory=list)
    is_staged: bool = False
    raw_patch: str = ""

