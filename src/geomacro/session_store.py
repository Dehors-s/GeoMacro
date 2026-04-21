from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, List

from .models import StandardEvent


class SessionStore:
    """Persist normalized capture sessions as JSON."""

    def __init__(self, session_file: str) -> None:
        self.session_file = Path(session_file)

    def save_events(self, events: Iterable[StandardEvent]) -> None:
        payload = [self._event_to_dict(event) for event in events]
        self.session_file.parent.mkdir(parents=True, exist_ok=True)
        self.session_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load_raw_events(self) -> List[dict]:
        if not self.session_file.exists():
            return []
        content = self.session_file.read_text(encoding="utf-8")
        if not content.strip():
            return []
        data = json.loads(content)
        if isinstance(data, list):
            return data
        return []

    def _event_to_dict(self, event: StandardEvent) -> dict:
        return {
            "event_id": event.event_id,
            "tool_name": event.tool_name,
            "tool_path": event.tool_path,
            "timestamp": event.timestamp.isoformat(),
            "is_success": event.is_success,
            "ordered_params": [asdict(param) for param in event.ordered_params],
            "outputs": list(event.outputs),
            "messages": list(event.messages),
            "raw": dict(event.raw),
        }
