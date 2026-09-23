import os
import tempfile
import sys
from app.environment.detector import EnvironmentDetector
from app.environment.models import InspectionScope

def test_environment_detector():
    with tempfile.TemporaryDirectory() as temp_dir:
        detector = EnvironmentDetector()
        info = detector.detect(temp_dir)
        
        assert info.python_available
        assert info.python_executable == sys.executable
        assert not info.virtualenv_present
        assert info.inspection_scope == InspectionScope.CURRENT_ENVIRONMENT
        
def test_environment_detector_with_venv():
    with tempfile.TemporaryDirectory() as temp_dir:
        venv_dir = os.path.join(temp_dir, ".venv")
        os.makedirs(venv_dir)
        
        detector = EnvironmentDetector()
        info = detector.detect(temp_dir)
        
        assert info.virtualenv_present
        assert info.virtualenv_path == venv_dir
        
        # Depending on whether sys.executable is inside temp_dir (it shouldn't be), 
        # it should mark it as PROJECT_VIRTUALENV_DETECTED_BUT_NOT_INSPECTED
        assert info.inspection_scope == InspectionScope.PROJECT_VIRTUALENV_DETECTED_BUT_NOT_INSPECTED
