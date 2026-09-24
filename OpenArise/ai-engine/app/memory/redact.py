import re

class SecretRedactor:
    """Basic regex-based redactor to strip potential secrets from memory records."""
    
    # Common secret patterns (API keys, tokens, basic auth, etc)
    PATTERNS = [
        re.compile(r"(api[_-]?key[\s:=]+)(['\"]?[\w\-]+['\"]?)", re.IGNORECASE),
        re.compile(r"(token[\s:=]+)(['\"]?[\w\-]+['\"]?)", re.IGNORECASE),
        re.compile(r"(password[\s:=]+)(['\"]?[^\s'\"&]+['\"]?)", re.IGNORECASE),
        re.compile(r"(secret[\s:=]+)(['\"]?[^\s'\"&]+['\"]?)", re.IGNORECASE),
        re.compile(r"(sk-[a-zA-Z0-9]{20,})"), # OpenAI-like
        re.compile(r"(ghp_[a-zA-Z0-9]{36})")  # GitHub
    ]
    
    def redact(self, text: str) -> str:
        if not text:
            return text
            
        redacted = str(text)
        for pattern in self.PATTERNS:
            def replace_func(match):
                # If there are groups, redact the last group (the value)
                if len(match.groups()) == 2:
                    return match.group(1) + "***REDACTED***"
                return "***REDACTED***"
            redacted = pattern.sub(replace_func, redacted)
            
        return redacted
        
    def redact_dict(self, data: dict) -> dict:
        def clean(value):
            if isinstance(value, dict):
                return self.redact_dict(value)
            if isinstance(value, list):
                return [clean(item) for item in value]
            return self.redact(value) if isinstance(value, str) else value

        sensitive_keys = {"api_key", "apikey", "token", "password", "secret", "authorization", "access_token"}
        return {
            key: "***REDACTED***" if str(key).lower().replace("-", "_") in sensitive_keys else clean(value)
            for key, value in data.items()
        }
