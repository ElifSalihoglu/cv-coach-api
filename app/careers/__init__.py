"""
Multi-agent career coaching.

`core` holds what every domain agent shares (evidence checks, claim checks, data
minimization, the coaching pipeline). `agents/<domain>` holds only what is specific to
one field: its prompt, what it sends to the model, and its own validation gates.
"""
