"""
JSON Formatter Extension for OpenArise IDE.
"""

import json


def activate(context, api):
    def format_json():
        text = api.get_active_editor_text()
        if not text:
            return
        try:
            parsed = json.loads(text)
            formatted = json.dumps(parsed, indent=2)
            api.set_active_editor_text(formatted)
        except json.JSONDecodeError as exc:
            pass

    api.register_command("json.format_document", "Format JSON Document", "Formatters", format_json, "Ctrl+Shift+I")


def deactivate(context, api):
    pass

