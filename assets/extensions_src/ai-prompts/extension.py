"""
AI Prompt Pack Extension for OpenArise IDE.
"""

def activate(context, api):
    def prompt_explain():
        code = api.get_active_editor_text()
        prompt = f"Please explain the logic of this code step-by-step and identify any edge-case vulnerabilities:\n\n```python\n{code[:2000]}\n```"
        api.send_chat_message(prompt)

    def prompt_refactor():
        code = api.get_active_editor_text()
        prompt = f"Refactor this Python code to be clean, idiomatic, and high-performance. Include explanatory comments:\n\n```python\n{code[:2000]}\n```"
        api.send_chat_message(prompt)

    def prompt_edge_cases():
        code = api.get_active_editor_text()
        prompt = f"Generate pytest unit test cases covering edge cases, invalid inputs, and error boundaries for:\n\n```python\n{code[:2000]}\n```"
        api.send_chat_message(prompt)

    api.register_command("ai.prompt_explain", "AI: Explain Active File", "AI Prompts", prompt_explain)
    api.register_command("ai.prompt_refactor", "AI: Refactor Active Code", "AI Prompts", prompt_refactor)
    api.register_command("ai.prompt_edge_cases", "AI: Generate Edge Case Tests", "AI Prompts", prompt_edge_cases)


def deactivate(context, api):
    pass

