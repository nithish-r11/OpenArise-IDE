from dataclasses import dataclass
from typing import Callable, Optional, List


@dataclass
class Command:
    id: str
    title: str
    category: str
    shortcut: str = ""
    handler: Optional[Callable] = None
    description: str = ""

    @property
    def display_name(self) -> str:
        if self.category:
            return f"{self.category}: {self.title}"
        return self.title


class CommandRegistry:
    """
    Central registry for application commands in OpenArise IDE.
    Supports registration, retrieval, and live searching.
    """

    def __init__(self):
        self._commands: dict[str, Command] = {}

    def register(
        self,
        id: str,
        title: str,
        category: str = "",
        shortcut: str = "",
        handler: Optional[Callable] = None,
        description: str = "",
    ) -> Command:
        cmd = Command(
            id=id,
            title=title,
            category=category,
            shortcut=shortcut,
            handler=handler,
            description=description,
        )
        self._commands[id] = cmd
        return cmd

    def unregister(self, id: str) -> Optional[Command]:
        return self._commands.pop(id, None)

    def get(self, id: str) -> Optional[Command]:
        return self._commands.get(id)

    def has(self, id: str) -> bool:
        return id in self._commands

    def execute(self, id: str, *args, **kwargs):
        cmd = self.get(id)
        if cmd and cmd.handler:
            return cmd.handler(*args, **kwargs)
        return None

    def all_commands(self) -> List[Command]:
        return list(self._commands.values())

    def search(self, query: str) -> List[Command]:
        clean_query = query.strip().lower()
        if not clean_query:
            return sorted(self._commands.values(), key=lambda c: (c.category, c.title))

        scored: list[tuple[int, Command]] = []
        for cmd in self._commands.values():
            title_lower = cmd.title.lower()
            cat_lower = cmd.category.lower()
            full_lower = f"{cat_lower}: {title_lower}"

            # Exact prefix match on title
            if title_lower.startswith(clean_query):
                scored.append((0, cmd))
            # Prefix on full category: title
            elif full_lower.startswith(clean_query):
                scored.append((1, cmd))
            # Substring match in title
            elif clean_query in title_lower:
                scored.append((2, cmd))
            # Substring match in category
            elif clean_query in cat_lower:
                scored.append((3, cmd))
            # Substring in description or full name
            elif clean_query in full_lower or clean_query in cmd.description.lower():
                scored.append((4, cmd))

        scored.sort(key=lambda item: (item[0], item[1].category, item[1].title))
        return [cmd for _, cmd in scored]

    def clear(self):
        self._commands.clear()
