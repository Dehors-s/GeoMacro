from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

from .models import StandardEvent


@dataclass
class UIState:
    events: List[StandardEvent] = field(default_factory=list)
    selected_event_ids: List[str] = field(default_factory=list)
    variable_overrides: Dict[Tuple[str, str], str] = field(default_factory=dict)
    script_preview: str = ""


class UIPresenter:
    """In-memory presenter state for the MVP workflow."""

    def __init__(self) -> None:
        self.state = UIState()

    def refresh_history(self, events: Sequence[StandardEvent]) -> UIState:
        self.state.events = list(events)
        self.state.selected_event_ids = [event.event_id for event in self.state.events]
        return self.state

    def select_steps(self, event_ids: Sequence[str]) -> UIState:
        available_ids = {event.event_id for event in self.state.events}
        self.state.selected_event_ids = [event_id for event_id in event_ids if event_id in available_ids]
        return self.state

    def mark_variable(self, event_id: str, param_name: str, variable_name: str) -> UIState:
        self.state.variable_overrides[(event_id, param_name)] = variable_name
        return self.state

    def set_script_preview(self, script_text: str) -> UIState:
        self.state.script_preview = script_text
        return self.state
