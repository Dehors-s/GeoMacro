from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, Iterable, List, Sequence

from .models import Parameter, StandardEvent


class EventNormalizer:
    """Normalize raw history/event payloads into StandardEvent objects."""

    def normalize_many(self, raw_events: Iterable[Dict[str, Any]]) -> List[StandardEvent]:
        return [self.normalize_event(raw_event) for raw_event in raw_events]

    def normalize_event(self, raw_event: Dict[str, Any]) -> StandardEvent:
        timestamp = self._coerce_datetime(
            self._pick_first(raw_event, ["timestamp", "TimestampUtc", "TimeStamp", "Timestamp"])
        )

        tool_path = str(
            self._pick_first(raw_event, ["tool_path", "ToolPath", "path", "Path", "toolPath"], default="")
            or ""
        )
        tool_name = str(
            self._pick_first(raw_event, ["tool_name", "ToolName", "name", "Name"], default="") or ""
        )
        if (not tool_name or self._is_generic_tool_name(tool_name)) and tool_path:
            tool_name = self._derive_tool_name(tool_path)
        if not tool_name:
            tool_name = "UnknownTool"

        event_id = str(
            self._pick_first(
                raw_event,
                ["event_id", "ExecuteId", "ExecuteID", "ID", "id"],
                default="",
            )
            or ""
        ).strip()
        if not event_id:
            event_id = f"evt_{int(timestamp.timestamp() * 1000)}_{tool_name}"

        ordered_params_raw = self._pick_first(
            raw_event,
            ["ordered_params", "Parameters", "parameters"],
            default=[],
        ) or []
        ordered_params = [
            self._normalize_param(index, raw_param)
            for index, raw_param in enumerate(ordered_params_raw, start=1)
        ]

        outputs = []
        for raw_output in self._to_list(
            self._pick_first(raw_event, ["outputs", "Outputs"], default=[])
        ):
            if isinstance(raw_output, str):
                outputs.append(self._normalize_path(raw_output))

        messages = [
            str(msg)
            for msg in self._to_list(self._pick_first(raw_event, ["messages", "Messages"], default=[]))
        ]
        result_summary = self._pick_first(raw_event, ["result_summary", "ResultSummary"], default="")
        if isinstance(result_summary, str) and result_summary.strip():
            messages.append(result_summary.strip())

        success_value = self._pick_first(
            raw_event,
            ["is_success", "IsSuccess", "Succeeded", "succeeded"],
            default=True,
        )
        is_success = self._coerce_success(success_value)

        return StandardEvent(
            event_id=event_id,
            tool_name=tool_name,
            tool_path=tool_path,
            timestamp=timestamp,
            is_success=is_success,
            ordered_params=ordered_params,
            outputs=outputs,
            messages=messages,
            raw=dict(raw_event.get("raw") or raw_event),
        )

    def _normalize_param(self, index: int, raw_param: Any) -> Parameter:
        if isinstance(raw_param, Parameter):
            return raw_param

        if isinstance(raw_param, dict):
            name = str(raw_param.get("name") or f"param_{index}")
            value = raw_param.get("value")
            direction = str(raw_param.get("direction") or "input").lower()
            is_path = bool(raw_param.get("is_path", False))
        elif isinstance(raw_param, (list, tuple)) and len(raw_param) >= 2:
            name = str(raw_param[0] or f"param_{index}")
            value = raw_param[1]
            direction = "input"
            is_path = False
        else:
            name = f"param_{index}"
            value = raw_param
            direction = "input"
            is_path = False

        if isinstance(value, str) and self._is_probable_path(value):
            is_path = True
            value = self._normalize_path(value)

        if direction == "output" and isinstance(value, str):
            is_path = True
            value = self._normalize_path(value)

        return Parameter(name=name, value=value, direction=direction, is_path=is_path)

    def _coerce_datetime(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value)
        if isinstance(value, str) and value.strip():
            text = value.strip().replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(text)
            except ValueError:
                pass
        return datetime.utcnow()

    def _coerce_success(self, value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"", "unknown", "none", "null"}:
                return True
            if lowered in {"true", "1", "yes", "y", "success", "succeeded"}:
                return True
            if lowered in {"false", "0", "no", "n", "failed", "fail"}:
                return False
        return bool(value)

    def _derive_tool_name(self, tool_path: str) -> str:
        if not tool_path:
            return ""
        return tool_path.replace("\\", "/").split("/")[-1]

    def _is_generic_tool_name(self, tool_name: str) -> bool:
        normalized = tool_name.strip().lower()
        return normalized in {"", "unknowntool", "gpexecuteevent"}

    def _pick_first(self, payload: Dict[str, Any], keys: Sequence[str], default: Any = None) -> Any:
        for key in keys:
            if key in payload:
                return payload[key]
        return default

    def _to_list(self, value: Any) -> List[Any]:
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        if value is None:
            return []
        return [value]

    def _normalize_path(self, value: str) -> str:
        expanded = os.path.expandvars(value.strip().strip('"'))
        return os.path.normpath(expanded)

    def _is_probable_path(self, value: str) -> bool:
        text = value.strip()
        if not text:
            return False
        if ":\\" in text or text.startswith("\\"):
            return True
        if "/" in text or "\\" in text:
            return True
        lowered = text.lower()
        return lowered.endswith((".shp", ".gdb", ".tif", ".img", ".json", ".csv", ".txt"))
