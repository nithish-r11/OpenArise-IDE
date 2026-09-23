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
        redacted_data = {}
        for k, v in data.items():
            if isinstance(v, str):
                redacted_data[k] = self.redact(v)
            elif isinstance(v, dict):
                redacted_data[k] = self.redact_dict(v)
            elif isinstance(v, list):
                redacted_data[k] = [self.redact(str(item)) if isinstance(item, str) else item for item in v]
            else:
                redacted_data[k] = v
        return redacted_data
