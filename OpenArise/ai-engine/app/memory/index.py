from typing import List
from app.models.schemas import FailureMemoryRecord
from app.memory.store import SQLiteMemoryStore

class MemoryIndex:
    """Abstraction for semantic search (e.g. FAISS). Defaults to deterministic SQLite fallback."""
    
    def __init__(self, store: SQLiteMemoryStore):
        self.store = store
        
    def add(self, record: FailureMemoryRecord):
        """Add to semantic index if available. (No-op in MVP as store handles it)."""
        pass
        
    def search(self, project_id: str, signature: str, category: str, summary: str, limit: int = 5) -> List[FailureMemoryRecord]:
        """
        Retrieves similar memories.
        MVP uses deterministic signature matching via SQLite.
        """
        # Exact signature match is highly relevant
        return self.store.find_by_signature(project_id, signature, limit)
