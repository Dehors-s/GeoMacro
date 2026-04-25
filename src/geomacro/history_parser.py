from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Sequence
from uuid import uuid4

from .models import detect_product_source


class HistoryParser:
    """Parse ArcGIS history-like objects into raw event dictionaries."""

    def parse_history_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        event_id = str(
            self._pick_first(item, ["ID", "id", "event_id", "ExecuteId", "ExecuteID"], default="") or ""
        ).strip()
        if not event_id:
            event_id = str(uuid4())

        timestamp = (
            self._pick_first(item, ["TimeStamp", "TimestampUtc", "timestamp", "Timestamp"])
            or datetime.utcnow().isoformat()
        )
        tool_path = str(
            self._pick_first(item, ["ToolPath", "tool_path", "Path", "path", "toolPath"], default="") or ""
        )
        tool_name = str(
            self._pick_first(item, ["ToolName", "tool_name", "name", "Name"], default="")
            or tool_path.replace("\\", "/").split("/")[-1]
            or "UnknownTool"
        )
        params = self._extract_params(item)
        outputs = self._extract_outputs(item, params)
        messages = self._as_str_list(self._pick_first(item, ["Messages", "messages"], default=[]))
        result_summary = self._pick_first(item, ["ResultSummary", "result_summary"], default="")
        if isinstance(result_summary, str) and result_summary.strip():
            messages.append(result_summary.strip())

        success_value = self._pick_first(item, ["Succeeded", "is_success", "IsSuccess"], default=True)
        is_success = self._coerce_success(success_value)

        return {
            "event_id": event_id,
            "timestamp": timestamp,
            "tool_path": tool_path,
            "tool_name": tool_name,
            "ordered_params": params,
            "outputs": outputs,
            "messages": messages,
            "is_success": is_success,
            "source": self._pick_first(item, ["source", "Source", "product_source"], default="") or "",
            "raw": dict(item),
        }

    def parse_many(self, items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [self.parse_history_item(item) for item in items]

    def _extract_params(self, item: Dict[str, Any]) -> List[Dict[str, Any]]:
        raw_params = (
            self._pick_first(item, ["Parameters", "parameters", "ordered_params"], default=[])
            or []
        )

        if isinstance(raw_params, dict):
            raw_params = [{"name": key, "value": value} for key, value in raw_params.items()]

        params: List[Dict[str, Any]] = []
        for idx, raw in enumerate(raw_params, start=1):
            if isinstance(raw, dict):
                name = str(raw.get("name") or raw.get("param") or f"param_{idx}")
                value = raw.get("value")
                direction = str(raw.get("direction") or ("output" if raw.get("is_output") else "input")).lower()
                is_path = bool(raw.get("is_path", False))
            elif isinstance(raw, (list, tuple)) and len(raw) >= 2:
                name = str(raw[0] or f"param_{idx}")
                value = raw[1]
                direction = "input"
                is_path = False
            else:
                name = f"param_{idx}"
                value = raw
                direction = "input"
                is_path = False

            params.append(
                {
                    "name": name,
                    "value": value,
                    "direction": direction,
                    "is_path": is_path,
                }
            )

        return params

    def _extract_outputs(self, item: Dict[str, Any], params: List[Dict[str, Any]]) -> List[str]:
        outputs = self._as_str_list(self._pick_first(item, ["Outputs", "outputs"], default=[]))
        for param in params:
            if param.get("direction") == "output" and isinstance(param.get("value"), str):
                outputs.append(param["value"])

        gp_result = self._pick_first(item, ["GPResult", "gp_result"])
        if isinstance(gp_result, dict):
            return_value = gp_result.get("return_value") or gp_result.get("ReturnValue")
            if isinstance(return_value, str) and return_value:
                outputs.append(return_value)

        deduped: List[str] = []
        seen = set()
        for value in outputs:
            if value not in seen:
                seen.add(value)
                deduped.append(value)
        return deduped

    def _as_str_list(self, values: Any) -> List[str]:
        if isinstance(values, str):
            return [values]
        if isinstance(values, list):
            return [str(value) for value in values]
        if isinstance(values, tuple):
            return [str(value) for value in values]
        return []

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

    def _pick_first(self, payload: Dict[str, Any], keys: Sequence[str], default: Any = None) -> Any:
        for key in keys:
            if key in payload:
                return payload[key]
        return default
