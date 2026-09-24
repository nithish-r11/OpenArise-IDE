import shutil
import uuid
from pathlib import Path
from app.tools.fs import _is_safe_path


class CheckpointManager:
    """Per-file snapshots and rollback inside the project; no OS-level isolation."""

    def __init__(self, project_root: str):
        self.project_root = str(Path(project_root).resolve())
        self.checkpoints_dir = str(Path(self.project_root) / ".openarise" / "checkpoints")
        if not Path(self.checkpoints_dir).resolve().is_relative_to(Path(self.project_root)):
            raise ValueError("Checkpoint directory escapes the project root.")
        Path(self.checkpoints_dir).mkdir(parents=True, exist_ok=True)
        self._new_files = {}

    def _is_safe_path(self, path: str) -> bool:
        return _is_safe_path(self.project_root, path)

    def create_checkpoint(self, files):
        if any(not self._is_safe_path(file) for file in files):
            raise ValueError("Unsafe checkpoint file.")
        checkpoint_id = str(uuid.uuid4())
        checkpoint_path = Path(self.checkpoints_dir) / checkpoint_id
        checkpoint_path.mkdir()
        self._new_files[checkpoint_id] = []
        for file in files:
            source = Path(self.project_root) / file
            if source.is_file():
                destination = checkpoint_path / file
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            elif not source.exists():
                self._new_files[checkpoint_id].append(file)
        return checkpoint_id

    def rollback_checkpoint(self, checkpoint_id):
        try:
            if str(uuid.UUID(checkpoint_id)) != checkpoint_id:
                return False
            checkpoint_path = Path(self.checkpoints_dir) / checkpoint_id
            if not checkpoint_path.is_dir() or not checkpoint_path.resolve().is_relative_to(Path(self.checkpoints_dir).resolve()):
                return False
            for source in checkpoint_path.rglob("*"):
                if not source.is_file():
                    continue
                relative = source.relative_to(checkpoint_path)
                if not source.resolve().is_relative_to(checkpoint_path.resolve()) or not self._is_safe_path(str(relative)):
                    return False
                destination = Path(self.project_root) / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            for file in self._new_files.get(checkpoint_id, []):
                if not self._is_safe_path(file):
                    return False
                destination = Path(self.project_root) / file
                if destination.is_file():
                    destination.unlink()
            return True
        except (ValueError, OSError):
            return False
