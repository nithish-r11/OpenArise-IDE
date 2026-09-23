import pytest
from app.tools.permissions import PermissionManager, RiskLevel, PermissionAction

def test_permission_manager_test_mode():
    manager = PermissionManager(test_mode=True)
    assert manager.check_permission("id1", RiskLevel.READ) is True
    assert manager.check_permission("id2", RiskLevel.WRITE) is True
    assert manager.check_permission("id3", RiskLevel.EXECUTE) is True

def test_permission_manager_normal_mode():
    manager = PermissionManager(test_mode=False)
    
    # Read is allowed by default
    assert manager.check_permission("id1", RiskLevel.READ) is True
    
    # Write and Execute require permission
    assert manager.check_permission("id2", RiskLevel.WRITE) is False
    assert manager.check_permission("id3", RiskLevel.EXECUTE) is False
    
    # Grant permission
    manager.grant_approval("id2")
    assert manager.check_permission("id2", RiskLevel.WRITE) is True
    assert manager.check_permission("id3", RiskLevel.EXECUTE) is False
