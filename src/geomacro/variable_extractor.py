from __future__ import annotations

from typing import Optional, Sequence

from .models import ExtractionResult, StandardEvent, VariableSlot


class VariableExtractor:
    """Identify variable slots from normalized tool parameters."""

    def extract(self, events: Sequence[StandardEvent]) -> ExtractionResult:
        result = ExtractionResult()
        input_counter = 0
        output_counter = 0

        for event in events:
            for param in event.ordered_params:
                key = (event.event_id, param.name)
                if self._should_parameterize(param):
                    if param.direction == "output":
                        output_counter += 1
                        slot_name = f"output_path_{output_counter}"
                        kind = "output_path"
                    else:
                        input_counter += 1
                        slot_name = f"input_path_{input_counter}"
                        kind = "input_path"

                    result.variable_slots[key] = VariableSlot(
                        name=slot_name,
                        default_value=param.value,
                        kind=kind,
                        source_event_id=event.event_id,
                        source_param_name=param.name,
                    )
                else:
                    result.constants[key] = param.value

        return result

    def first_loop_variable(self, extraction: ExtractionResult) -> Optional[VariableSlot]:
        for slot in extraction.variable_slots.values():
            if slot.kind == "input_path":
                return slot
        return None

    def _should_parameterize(self, param: object) -> bool:
        is_path = getattr(param, "is_path", False)
        value = getattr(param, "value", None)
        if not is_path:
            return False
        if not isinstance(value, str):
            return False
        return bool(value.strip())
