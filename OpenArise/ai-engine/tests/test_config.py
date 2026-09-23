from app.config import settings

def test_config_defaults():
    assert settings.OLLAMA_HOST == "http://localhost:11434"
    assert settings.OLLAMA_MODEL == "llama3"
    assert settings.LUMINOUS_MODEL == "Luminous 1.1"
    assert settings.LOG_LEVEL == "INFO"
