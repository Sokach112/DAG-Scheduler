"""Worker: a named member of a project's team roster."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Worker:
    """A schedulable team member.

    Attributes:
        wid: Stable worker identifier. Task capabilities reference this id,
            so renaming a worker does not break existing assignments.
        name: Human-readable name shown in the UI.
    """

    wid: str
    name: str
