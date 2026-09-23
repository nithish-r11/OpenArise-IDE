import pytest
from unittest.mock import patch, MagicMock
import requests
from app.llm.ollama import OllamaProvider
from pydantic import BaseModel, Field

class SampleSchema(BaseModel):
    name: str
    age: int = Field(default=0)

@patch("requests.post")
def test_ollama_generate_success(mock_post):
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "Hello World"}
    mock_post.return_value = mock_response
    
    provider = OllamaProvider(host="http://localhost:11434", model="test-model")
    result = provider.generate("Say hello", system_prompt="Be polite")
    
    assert result == "Hello World"
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert kwargs["json"]["model"] == "test-model"
    assert kwargs["json"]["prompt"] == "Say hello"
    assert kwargs["json"]["system"] == "Be polite"

@patch("requests.post")
def test_ollama_generate_structured_success(mock_post):
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": '{"name": "Alice", "age": 30}'}
    mock_post.return_value = mock_response
    
    provider = OllamaProvider()
    result = provider.generate_structured("Who are you?", SampleSchema)
    
    assert isinstance(result, SampleSchema)
    assert result.name == "Alice"
    assert result.age == 30
    
    args, kwargs = mock_post.call_args
    assert kwargs["json"]["format"] == "json"
    assert "You must respond ONLY in valid JSON matching this schema" in kwargs["json"]["system"]

@patch("requests.post")
def test_ollama_generate_structured_invalid_json(mock_post):
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": 'not valid json'}
    mock_post.return_value = mock_response
    
    provider = OllamaProvider()
    with pytest.raises(ValueError, match="invalid JSON"):
        provider.generate_structured("test", SampleSchema)

@patch("requests.post")
def test_ollama_unavailable(mock_post):
    mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")
    
    provider = OllamaProvider()
    with pytest.raises(RuntimeError, match="LLM Provider error"):
        provider.generate("test")

@patch("requests.get")
def test_ollama_health_check_success(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {"models": [{"name": "llama3:latest"}, {"name": "other-model"}]}
    mock_get.return_value = mock_response
    
    provider = OllamaProvider(model="llama3")
    assert provider.health_check() is True

@patch("requests.get")
def test_ollama_health_check_model_missing(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {"models": [{"name": "other-model"}]}
    mock_get.return_value = mock_response
    
    provider = OllamaProvider(model="llama3")
    assert provider.health_check() is False

@patch("requests.get")
def test_ollama_health_check_unavailable(mock_get):
    mock_get.side_effect = requests.exceptions.Timeout("Timed out")
    
    provider = OllamaProvider()
    assert provider.health_check() is False
