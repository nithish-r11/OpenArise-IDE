import pytest
import os
import tempfile
import json
from app.luminous.dataset import DatasetPipeline
from app.luminous.evaluation import EvaluationFramework
from tests.mock_llm import MockLLMProvider

def test_luminous_dataset_pipeline():
    with tempfile.TemporaryDirectory() as temp_dir:
        input_file = os.path.join(temp_dir, "input.jsonl")
        output_file = os.path.join(temp_dir, "output.jsonl")
        
        with open(input_file, "w") as f:
            # Valid record
            f.write(json.dumps({
                "failure": "f1", "diagnosis": "d1", "recovery": "r1",
                "evidence": {"test": "pass"}, "outcome": "RECOVERED"
            }) + "\n")
            
            # Missing fields
            f.write(json.dumps({
                "failure": "f2", "diagnosis": "d2"
            }) + "\n")
            
            # Contradictory record (recovered but no evidence)
            f.write(json.dumps({
                "failure": "f3", "diagnosis": "d3", "recovery": "r3",
                "evidence": {}, "outcome": "RECOVERED"
            }) + "\n")
            
        pipeline = DatasetPipeline(input_file)
        valid_count = pipeline.validate_and_filter(output_file)
        
        assert valid_count == 1
        
        with open(output_file, "r") as f:
            lines = f.readlines()
            assert len(lines) == 1
            data = json.loads(lines[0])
            assert data["failure"] == "f1"

def test_luminous_evaluation_framework():
    llm = MockLLMProvider()
    framework = EvaluationFramework(llm)
    
    test_cases = [
        {"prompt": "Error A", "expected": "Category_A"},
        {"prompt": "Error B", "expected": "Category_B"}
    ]
    
    results = framework.evaluate(test_cases)
    
    assert len(results) == 1
    assert results[0].category == "failure_classification"
    assert results[0].passed == 2
    assert results[0].score == 100.0
