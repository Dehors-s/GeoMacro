from __future__ import annotations

import os
from typing import Dict, List, Sequence, Set

from .models import StandardEvent, StepNode


class DependencyAnalyzer:
    """Infer simple upstream/downstream dependencies from path parameters."""

    def build(self, events: Sequence[StandardEvent]) -> List[StepNode]:
        output_owner: Dict[str, str] = {}
        nodes: List[StepNode] = []

        for event in sorted(events, key=lambda item: item.timestamp):
            dependencies: Set[str] = set()

            for param in event.ordered_params:
                if param.direction != "input" or not param.is_path or not isinstance(param.value, str):
                    continue
                owner = output_owner.get(self._norm_path(param.value))
                if owner and owner != event.event_id:
                    dependencies.add(owner)

            for output in self._collect_outputs(event):
                output_owner[self._norm_path(output)] = event.event_id

            nodes.append(
                StepNode(
                    event_id=event.event_id,
                    tool_name=event.tool_name,
                    depends_on=sorted(dependencies),
                )
            )

        return nodes

    def _collect_outputs(self, event: StandardEvent) -> List[str]:
        outputs = list(event.outputs)
        for param in event.ordered_params:
            if param.direction == "output" and isinstance(param.value, str):
                outputs.append(param.value)
        return outputs

    def _norm_path(self, path_value: str) -> str:
        return os.path.normcase(os.path.normpath(path_value))
