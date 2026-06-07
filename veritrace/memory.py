"""Short-term conversational memory for multi-turn chat.

Public API
----------
get_history(session_id) -> list[dict]
    Return the OpenAI-format message list for the session, or [] if unknown.

add_turn(session_id, role, content) -> None
    Append a turn to the session.  Oldest turns are dropped when the window
    exceeds MAX_TURNS pairs.

clear_session(session_id) -> None
    Remove the session entirely.

Design notes
------------
- In-process only (no persistence across restarts) — sufficient for demo
  and Streamlit Cloud where each session is one process.
- Thread-safe via a simple lock.
- The history is injected into the generation prompt as prior context so the
  model can answer follow-up questions that refer to the previous turn.
"""

from __future__ import annotations

import threading
from typing import Literal

Role = Literal["user", "assistant"]
MAX_TURNS: int = 10   # per role; total window = 2 * MAX_TURNS messages


class SessionMemory:
    """Thread-safe in-process session store."""

    def __init__(self, max_turns: int = MAX_TURNS) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, list[dict]] = {}
        self._max_turns = max_turns

    def get_history(self, session_id: str) -> list[dict]:
        """Return message list for session, empty list if not found."""
        with self._lock:
            return list(self._sessions.get(session_id, []))

    def add_turn(self, session_id: str, role: Role, content: str) -> None:
        """Append a turn; trim to window if needed."""
        with self._lock:
            msgs = self._sessions.setdefault(session_id, [])
            msgs.append({"role": role, "content": content})
            max_msgs = self._max_turns * 2
            if len(msgs) > max_msgs:
                self._sessions[session_id] = msgs[-max_msgs:]

    def clear_session(self, session_id: str) -> None:
        """Remove a session."""
        with self._lock:
            self._sessions.pop(session_id, None)

    def session_count(self) -> int:
        with self._lock:
            return len(self._sessions)


# Module-level singleton used by the API
_memory = SessionMemory()


def get_history(session_id: str) -> list[dict]:
    return _memory.get_history(session_id)


def add_turn(session_id: str, role: Role, content: str) -> None:
    _memory.add_turn(session_id, role, content)


def clear_session(session_id: str) -> None:
    _memory.clear_session(session_id)
