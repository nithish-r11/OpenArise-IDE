"""
Python Essentials Extension for OpenArise IDE.
"""

def activate(context, api):
    def run_selection():
        text = api.get_active_editor_text()
        if text:
            # If editor has selection, execute selection in terminal
            api.execute_terminal_command('python -c "print(\'Python Essentials: executing selection\')"')

    def insert_docstring():
        docstring_stub = '    """\n    Summary of function.\n\n    Args:\n        arg1: Description.\n\n    Returns:\n        Description of return value.\n    """\n'
        api.insert_text_at_cursor(docstring_stub)

    def add_main_block():
        main_block = '\n\ndef main():\n    pass\n\n\nif __name__ == "__main__":\n    main()\n'
        api.insert_text_at_cursor(main_block)

    api.register_command("python.run_selection", "Run Selection in Terminal", "Python", run_selection, "Shift+F5")
    api.register_command("python.insert_docstring", "Insert Docstring Stub", "Python", insert_docstring)
    api.register_command("python.add_main_block", "Add if __name__ == '__main__' Block", "Python", add_main_block)


def deactivate(context, api):
    pass

