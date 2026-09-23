import os
import shutil
import uuid
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class CheckpointManager:
    """Manages lightweight snapshots of specific files inside the sandbox."""
    
    def __init__(self, project_root: str):
        self.project_root = os.path.abspath(project_root)
        self.checkpoints_dir = os.path.join(self.project_root, ".openarise", "checkpoints")
        self._ensure_dir()
        
    def _ensure_dir(self):
        if not os.path.exists(self.checkpoints_dir):
            os.makedirs(self.checkpoints_dir)
            
    def _is_safe_path(self, path: str) -> bool:
        abs_path = os.path.abspath(os.path.join(self.project_root, path))
        return abs_path.startswith(self.project_root)
        
    def create_checkpoint(self, files: List[str]) -> str:
        """Creates a snapshot of the specific files, returns checkpoint_id."""
        checkpoint_id = str(uuid.uuid4())
        checkpoint_path = os.path.join(self.checkpoints_dir, checkpoint_id)
        os.makedirs(checkpoint_path)
        
        for file in files:
            if not self._is_safe_path(file):
                logger.warning(f"Skipping unsafe path in checkpoint: {file}")
                continue
                
            abs_src = os.path.join(self.project_root, file)
            if os.path.exists(abs_src):
                abs_dest = os.path.join(checkpoint_path, file)
                os.makedirs(os.path.dirname(abs_dest), exist_ok=True)
                shutil.copy2(abs_src, abs_dest)
                
        return checkpoint_id
        
    def rollback_checkpoint(self, checkpoint_id: str) -> bool:
        """Restores files from a specific checkpoint."""
        checkpoint_path = os.path.join(self.checkpoints_dir, checkpoint_id)
        if not os.path.exists(checkpoint_path):
            logger.error(f"Checkpoint not found: {checkpoint_id}")
            return False
            
        try:
            for root, _, files in os.walk(checkpoint_path):
                for file in files:
                    abs_src = os.path.join(root, file)
                    rel_path = os.path.relpath(abs_src, checkpoint_path)
                    abs_dest = os.path.join(self.project_root, rel_path)
                    
                    if not self._is_safe_path(rel_path):
                        continue
                        
                    os.makedirs(os.path.dirname(abs_dest), exist_ok=True)
                    shutil.copy2(abs_src, abs_dest)
            return True
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False
