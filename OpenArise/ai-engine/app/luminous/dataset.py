import json
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class DatasetPipeline:
    """Prepares and validates JSONL data for Luminous 1.1 training."""
    
    def __init__(self, input_file: str):
        self.input_file = input_file
        
    def validate_and_filter(self, output_file: str) -> int:
        """Validates records and outputs clean dataset. Returns valid count."""
        valid_count = 0
        try:
            with open(self.input_file, 'r') as f_in, open(output_file, 'w') as f_out:
                for line in f_in:
                    try:
                        record = json.loads(line)
                        if self._is_valid(record):
                            f_out.write(json.dumps(record) + "\n")
                            valid_count += 1
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            logger.warning(f"Input dataset not found: {self.input_file}")
            
        return valid_count
        
    def _is_valid(self, record: Dict) -> bool:
        required = ["failure", "diagnosis", "recovery", "evidence", "outcome"]
        for req in required:
            if req not in record:
                return False
                
        # Validate contradictory outcomes
        if record["outcome"] == "RECOVERED" and not record["evidence"]:
            return False # Can't be recovered without evidence
            
        if "REDACTED" in json.dumps(record):
            # For strict training, we might drop redacted records entirely to prevent confusing the model,
            # or keep them if it learns generalized repair. We allow it for now.
            pass
            
        return True
