"""Constraints for explicit user tool instructions, never an execution shortcut."""
import json
import re

TOOLS = ('write_file', 'read_file', 'execute_python', 'execute_tests', 'execute_project_tests', 'build_project')
TOOL_PATTERN = r'\b(?:' + '|'.join(TOOLS) + r')\b'


def _quoted_literal(value):
    try:
        return json.loads(value, strict=False)
    except json.JSONDecodeError:
        return None  # Non-JSON prose remains model planned; never execute it here.


def positive_tool_mentions(text):
    for clause in re.finditer(r'[^.;!?\n]+', text):
        positive = re.split(r'\b(?:do not|never|no)\b', clause.group(), maxsplit=1, flags=re.I)[0]
        if re.match(r'\s*(?:explain|describe|inspect|what|how|show)\b', positive, re.I):
            continue
        for match in re.finditer(TOOL_PATTERN, positive):
            yield match.group(), clause.start() + match.start(), clause.start() + match.end()


def requested_steps(text):
    """Recognize named ordered calls, or a single explicitly named tool.

    General natural-language tasks remain model planned. Only literal path,
    content and overwrite values are constrained; no actions or results are
    synthesized, and every write/execution still requires its own approval.
    """
    mentions = list(positive_tool_mentions(text))
    ordered = re.search(r'\bordered\s+(?:tool\s+)?(?:calls|entries)', text, re.I)
    if ordered:
        mentions = [mention for mention in mentions if mention[1] > ordered.end()]
    elif len(mentions) != 1:
        return []
    steps = []
    for index, (name, start, end) in enumerate(mentions):
        segment = text[end:mentions[index + 1][1] if index + 1 < len(mentions) else len(text)]
        arguments = {}
        if name == 'write_file':
            path = re.match(r'\s+(?:with\s+)?(?:path\s*[:=]?\s*)?("(?:\\.|[^"\\])*"|[\w./-]+)', segment)
            if path:
                value = path.group(1)
                value = _quoted_literal(value) if value.startswith('"') else value.rstrip('.,;')
                if isinstance(value, str) and ('.' in value or '/' in value):
                    arguments['path'] = value
            content = re.search(r'\bcontent\s*[:=]?\s*("(?:\\.|[^"\\])*")', segment)
            if content:
                value = _quoted_literal(content.group(1))
                if isinstance(value, str):
                    arguments['content'] = value
            overwrite = re.search(r'\boverwrite\s*[:=]?\s*(true|false)\b', segment, re.I)
            if overwrite:
                arguments['overwrite'] = overwrite.group(1).lower() == 'true'
        steps.append({'tool_name': name, 'arguments': arguments})
    return steps


def validate_requested_steps(action, steps):
    if not steps:
        return
    if action.action_type != 'tool_call' or [call.tool_name for call in action.tool_calls] != [step['tool_name'] for step in steps]:
        raise ValueError('Generated plan omitted or reordered explicitly requested tool steps.')
    for call, step in zip(action.tool_calls, steps):
        if any(type(call.arguments.get(key)) is not type(value) or call.arguments.get(key) != value
               for key, value in step['arguments'].items()):
            raise ValueError('Generated plan changed explicitly requested tool arguments.')
