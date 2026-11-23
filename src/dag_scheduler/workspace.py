"""Workspace: a top-level container for projects.

The v0.2 hierarchy is deliberately flat (Workspace -> Project). Workspaces
only carry metadata; scheduling data lives on the projects inside them.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Optional


@dataclass
class Workspace:
    """Metadata for a workspace.

    Attributes:
        wsid: Stable workspace identifier (unique, 8-char uuid by default).
        name: Human-readable workspace name.
        description: Free-form notes.
        created_at: Creation timestamp, filled in by the persistence layer.
    """

    wsid: str
    name: str
    description: str = ""
    created_at: Optional[datetime.datetime] = None
