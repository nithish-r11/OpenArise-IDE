from app.models.schemas import RecoveryPolicy

class RecoveryPolicyManager:
    """Manages the limits and boundaries of the recovery process."""
    
    def __init__(self, policy: RecoveryPolicy = None):
        self.policy = policy or RecoveryPolicy()
        
    def can_retry_failure(self, failure_signature: str, attempts: int, repeated_count: int) -> bool:
        """Determines if a failure can be retried based on policy."""
        if attempts >= self.policy.max_attempts_per_failure:
            return False
        if repeated_count >= self.policy.max_repeated_identical:
            return False
        return True
