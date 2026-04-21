from __future__ import annotations

import re
from typing import Dict, List, Sequence

from .models import ExtractionResult, StandardEvent
from .template_registry import TemplateRegistry


class CodeGenerator:
    """Generate linear ArcPy scripts from normalized events."""

    def __init__(self, template_registry: TemplateRegistry | None = None) -> None:
        self.template_registry = template_registry or TemplateRegistry()

    def generate(self, events: Sequence[StandardEvent], extraction: ExtractionResult) -> str:
        events = sorted(events, key=lambda item: item.timestamp)
        default_context = self._build_default_context(extraction)
        loop_slot = self._first_loop_slot(extraction)

        lines: List[str] = [
            "from pathlib import Path",
            "import arcpy",
            "",
            f"DEFAULT_CONTEXT = {repr(default_context)}",
            "",
            "def run_pipeline(context):",
            "    arcpy.env.overwriteOutput = True",
        ]

        if not events:
            lines.append("    return")
        else:
            for event in events:
                lines.append(f"    {self._build_tool_call(event, extraction)}")

        lines.extend(["", "def main(input_root: str = r'.'):"])

        if loop_slot:
            lines.extend(
                [
                    "    input_path = Path(input_root)",
                    "    for candidate in input_path.glob('*'):",
                    "        if not candidate.is_file():",
                    "            continue",
                    "        context = dict(DEFAULT_CONTEXT)",
                    f"        context['{loop_slot}'] = str(candidate)",
                    "        run_pipeline(context)",
                ]
            )
        else:
            lines.extend(["    run_pipeline(dict(DEFAULT_CONTEXT))"])

        lines.extend(["", "if __name__ == '__main__':", "    main()", ""])
        return "\n".join(lines)

    def _build_default_context(self, extraction: ExtractionResult) -> Dict[str, object]:
        context: Dict[str, object] = {}
        for slot in extraction.variable_slots.values():
            context[slot.name] = slot.default_value
        return context

    def _first_loop_slot(self, extraction: ExtractionResult) -> str:
        for slot in extraction.variable_slots.values():
            if slot.kind == "input_path":
                return slot.name
        return ""

    def _build_tool_call(self, event: StandardEvent, extraction: ExtractionResult) -> str:
        call_target = self.template_registry.resolve(event.tool_name)
        arg_tokens: List[str] = []

        for param in event.ordered_params:
            variable = extraction.get_variable(event.event_id, param.name)
            value_expr = (
                f"context[{repr(variable.name)}]" if variable is not None else repr(param.value)
            )
            safe_name = self._safe_param_name(param.name)
            arg_tokens.append(f"{safe_name}={value_expr}")

        args_text = ", ".join(arg_tokens)
        return f"{call_target}({args_text})"

    def _safe_param_name(self, name: str) -> str:
        safe = re.sub(r"[^0-9A-Za-z_]", "_", name.strip())
        if not safe:
            return "param"
        if safe[0].isdigit():
            return f"p_{safe}"
        return safe
