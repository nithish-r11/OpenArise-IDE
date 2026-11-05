import json
import os
from pathlib import Path
from typing import Any, Dict


DEFAULT_SETTINGS: Dict[str, Any] = {
    "editor_font_family": "Consolas",
    "editor_font_size": 11,
    "tab_size": 4,
    "word_wrap": False,
    "line_numbers": True,
    "auto_save": True,
    "auto_save_interval": 30,  # seconds
    "default_terminal_shell": "PowerShell",
    "default_ollama_model": "qwen2.5-coder:7b",
    "startup_behavior": "open_last_project",  # "open_last_project" or "blank"
    "last_project_root": "",
    "theme": "OpenArise Dark",
}

VALID_THEMES = ("OpenArise Dark", "Dracula", "Monokai", "Nord", "Light")
VALID_SHELLS = ("PowerShell", "CMD")
VALID_STARTUPS = ("open_last_project", "blank")


class SettingsManager:
    """
    Manages persistent user configuration saved in ~/.openarise/settings.json.
    Includes schema validation, fallback defaults, and safe atomic updates.
    """

    def __init__(self, config_dir: Path = None):
        if config_dir is None:
            self.config_dir = Path.home() / ".openarise"
        else:
            self.config_dir = Path(config_dir)
        self.config_file = self.config_dir / "settings.json"
        self._settings: Dict[str, Any] = dict(DEFAULT_SETTINGS)
        self.load()

    def load(self) -> Dict[str, Any]:
        if self.config_file.exists():
            try:
                data = json.loads(self.config_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._settings.update(self._validate_dict(data))
            except Exception:
                # If corrupted, preserve defaults
                pass
        return dict(self._settings)

    def save(self) -> bool:
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            temp_file = self.config_dir / "settings.json.tmp"
            temp_file.write_text(json.dumps(self._settings, indent=2), encoding="utf-8")
            temp_file.replace(self.config_file)
            return True
        except Exception:
            return False

    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default if default is not None else DEFAULT_SETTINGS.get(key))

    def set(self, key: str, value: Any) -> None:
        validated = self._validate_single(key, value)
        self._settings[key] = validated
        self.save()

    def update(self, new_settings: Dict[str, Any]) -> None:
        validated = self._validate_dict(new_settings)
        self._settings.update(validated)
        self.save()

    def reset_to_defaults(self) -> None:
        self._settings = dict(DEFAULT_SETTINGS)
        self.save()

    def all_settings(self) -> Dict[str, Any]:
        return dict(self._settings)

    def _validate_single(self, key: str, value: Any) -> Any:
        if key == "editor_font_size":
            try:
                return max(8, min(36, int(value)))
            except (ValueError, TypeError):
                return DEFAULT_SETTINGS["editor_font_size"]

        if key == "tab_size":
            try:
                return max(2, min(8, int(value)))
            except (ValueError, TypeError):
                return DEFAULT_SETTINGS["tab_size"]

        if key == "auto_save_interval":
            try:
                return max(5, min(600, int(value)))
            except (ValueError, TypeError):
                return DEFAULT_SETTINGS["auto_save_interval"]

        if key == "theme":
            return value if value in VALID_THEMES else DEFAULT_SETTINGS["theme"]

        if key == "default_terminal_shell":
            return value if value in VALID_SHELLS else DEFAULT_SETTINGS["default_terminal_shell"]

        if key == "startup_behavior":
            return value if value in VALID_STARTUPS else DEFAULT_SETTINGS["startup_behavior"]

        if key in ("word_wrap", "line_numbers", "auto_save"):
            return bool(value)

        if key in ("editor_font_family", "default_ollama_model", "last_project_root"):
            return str(value)

        return value

    def _validate_dict(self, data: Dict[str, Any]) -> Dict[str, Any]:
        valid = {}
        for k, v in data.items():
            if k in DEFAULT_SETTINGS:
                valid[k] = self._validate_single(k, v)
        return valid

