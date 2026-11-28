"""The tool-calling half of a fake model: it calls the tools it was told to, and records what it was offered."""


class ChoosesTool:
    """
    Mixin for fake models. `tool` is what the fake "model" calls:
    - a name: it calls that tool first and, once a result has come back, calls none (it is done);
    - a list of names (None entries allowed): one entry per decision, in order; calls none when it runs out;
    - None: it calls none.
    `tool_calls` records (prompt, payload, tools) of each decision, `tool_steps` the tool results it had seen.
    """

    tool: str | list[str | None] | None = None

    async def choose_tool(self, system_prompt, user_content, tools, steps=()):
        self.__dict__.setdefault("tool_calls", []).append((system_prompt, user_content, list(tools)))
        self.__dict__.setdefault("tool_steps", []).append(list(steps))
        if isinstance(self.tool, list):
            return self.tool.pop(0) if self.tool else None
        return self.tool if not steps else None
