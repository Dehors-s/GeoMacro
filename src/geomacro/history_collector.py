from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from .event_normalizer import EventNormalizer
from .history_parser import HistoryParser
from .models import StandardEvent


class HistoryCollector:
    """Collect and deduplicate incremental geoprocessing events."""

    def __init__(
        self,
        window_size: int = 50,
        include_failed: bool = False,
        dedup_window_seconds: int = 3,
        history_match_window_seconds: int = 8,
    ) -> None:
        self.window_size = window_size
        self.include_failed = include_failed
        self.dedup_window_seconds = dedup_window_seconds
        self.history_match_window_seconds = history_match_window_seconds
        self._known_event_ids: Set[str] = set()
        self._parser = HistoryParser()
        self._normalizer = EventNormalizer()

    def collect_incremental(
        self,
        live_events: Optional[Sequence[Dict[str, Any]]] = None,
        history_items: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> List[StandardEvent]:
        live_events = list(live_events or [])
        history_items = list(history_items or [])

        parsed_history_raw = self._parser.parse_many(history_items)

        normalized_live = self._normalizer.normalize_many(live_events)
        normalized_history = self._normalizer.normalize_many(parsed_history_raw)

        merged = self._merge_live_with_history(normalized_live, normalized_history)
        filtered = [event for event in merged if self.include_failed or event.is_success]
        deduped = self._deduplicate(filtered)
        deduped.sort(key=lambda event: self._to_epoch_seconds(event.timestamp))

        if self.window_size > 0:
            deduped = deduped[-self.window_size :]

        incremental = [event for event in deduped if event.event_id not in self._known_event_ids]
        for event in deduped:
            self._known_event_ids.add(event.event_id)

        return incremental

    def reset_snapshot(self) -> None:
        self._known_event_ids.clear()

    def _merge_live_with_history(
        self,
        live_events: Sequence[StandardEvent],
        history_events: Sequence[StandardEvent],
    ) -> List[StandardEvent]:
        if not live_events:
            return list(history_events)
        if not history_events:
            return list(live_events)

        used_history: Set[int] = set()
        merged_live: List[StandardEvent] = []

        for live_event in live_events:
            match_index = self._find_best_history_match(live_event, history_events, used_history)
            if match_index is None:
                merged_live.append(live_event)
                continue

            used_history.add(match_index)
            merged_live.append(self._merge_event_pair(live_event, history_events[match_index]))

        merged_all = list(merged_live)
        for index, history_event in enumerate(history_events):
            if index not in used_history:
                merged_all.append(history_event)

        return merged_all

    def _find_best_history_match(
        self,
        live_event: StandardEvent,
        history_events: Sequence[StandardEvent],
        used_history: Set[int],
    ) -> Optional[int]:
        live_epoch = self._to_epoch_seconds(live_event.timestamp)
        best_index: Optional[int] = None
        best_delta = float("inf")

        for index, history_event in enumerate(history_events):
            if index in used_history:
                continue
            if not self._is_tool_compatible(live_event, history_event):
                continue

            delta = abs(live_epoch - self._to_epoch_seconds(history_event.timestamp))
            if delta > self.history_match_window_seconds:
                continue

            if delta < best_delta:
                best_delta = delta
                best_index = index

        return best_index

    def _is_tool_compatible(self, live_event: StandardEvent, history_event: StandardEvent) -> bool:
        live_tool_path = self._normalize_match_text(live_event.tool_path)
        history_tool_path = self._normalize_match_text(history_event.tool_path)

        if live_tool_path and history_tool_path and live_tool_path != history_tool_path:
            return False

        live_tool_name = self._normalize_match_text(live_event.tool_name)
        history_tool_name = self._normalize_match_text(history_event.tool_name)
        if (
            live_tool_name
            and history_tool_name
            and not self._is_generic_tool_name(live_event.tool_name)
            and not self._is_generic_tool_name(history_event.tool_name)
            and live_tool_name != history_tool_name
        ):
            return False

        return True

    def _merge_event_pair(self, live_event: StandardEvent, history_event: StandardEvent) -> StandardEvent:
        event_id = live_event.event_id
        if self._is_generated_event_id(event_id) and history_event.event_id:
            event_id = history_event.event_id

        tool_path = live_event.tool_path or history_event.tool_path

        if self._is_generic_tool_name(live_event.tool_name) and history_event.tool_name:
            tool_name = history_event.tool_name
        else:
            tool_name = live_event.tool_name or history_event.tool_name

        if not tool_name:
            tool_name = "UnknownTool"

        is_success = live_event.is_success
        if self._success_value_missing(live_event.raw):
            is_success = history_event.is_success

        ordered_params = list(live_event.ordered_params) or list(history_event.ordered_params)
        outputs = self._merge_unique_strings(list(live_event.outputs), list(history_event.outputs))
        messages = self._merge_unique_strings(list(live_event.messages), list(history_event.messages))

        merged_raw = dict(live_event.raw)
        if history_event.raw:
            merged_raw["history"] = dict(history_event.raw)

        return StandardEvent(
            event_id=event_id,
            tool_name=tool_name,
            tool_path=tool_path,
            timestamp=live_event.timestamp,
            is_success=is_success,
            ordered_params=ordered_params,
            outputs=outputs,
            messages=messages,
            raw=merged_raw,
        )

    def _deduplicate(self, events: Sequence[StandardEvent]) -> List[StandardEvent]:
        seen_ids: Dict[str, int] = {}
        seen_fallback_keys: Dict[Tuple[str, int, Tuple[str, ...], Tuple[str, ...]], int] = {}
        deduped: List[StandardEvent] = []

        for event in events:
            existing_id_index = seen_ids.get(event.event_id)
            if existing_id_index is not None:
                deduped[existing_id_index] = self._choose_better_event(
                    deduped[existing_id_index],
                    event,
                )
                continue

            fallback_key = self._build_fallback_key(event)
            existing_key_index = seen_fallback_keys.get(fallback_key)
            if existing_key_index is not None:
                deduped[existing_key_index] = self._choose_better_event(
                    deduped[existing_key_index],
                    event,
                )
                seen_ids[event.event_id] = existing_key_index
                continue

            deduped.append(event)
            new_index = len(deduped) - 1
            seen_ids[event.event_id] = new_index
            seen_fallback_keys[fallback_key] = new_index

        return deduped

    def _build_fallback_key(self, event: StandardEvent) -> Tuple[str, int, Tuple[str, ...], Tuple[str, ...]]:
        time_bucket = int(self._to_epoch_seconds(event.timestamp) // max(1, self.dedup_window_seconds))
        tool_identity = self._normalize_match_text(event.tool_path or event.tool_name)
        param_signature = tuple(f"{param.name}={param.value}" for param in event.ordered_params)
        output_signature = tuple(str(output) for output in event.outputs)
        return tool_identity, time_bucket, param_signature, output_signature

    def _choose_better_event(self, current: StandardEvent, candidate: StandardEvent) -> StandardEvent:
        current_score = self._event_score(current)
        candidate_score = self._event_score(candidate)
        if candidate_score > current_score:
            return candidate
        if candidate_score == current_score:
            if self._to_epoch_seconds(candidate.timestamp) >= self._to_epoch_seconds(current.timestamp):
                return candidate
        return current

    def _event_score(self, event: StandardEvent) -> int:
        score = 0
        if event.tool_path:
            score += 4
        if not self._is_generic_tool_name(event.tool_name):
            score += 3
        score += min(len(event.ordered_params), 10) * 2
        score += min(len(event.outputs), 10)
        score += min(len(event.messages), 5)
        if isinstance(event.raw.get("history"), dict):
            score += 2
        return score

    def _merge_unique_strings(self, left: Sequence[str], right: Sequence[str]) -> List[str]:
        merged: List[str] = []
        seen: Set[str] = set()

        for value in [*left, *right]:
            text = str(value)
            if text in seen:
                continue
            seen.add(text)
            merged.append(text)

        return merged

    def _success_value_missing(self, raw_payload: Dict[str, Any]) -> bool:
        for key in ("IsSuccess", "is_success", "Succeeded", "succeeded"):
            if key in raw_payload:
                value = raw_payload.get(key)
                if value is None:
                    return True
                if isinstance(value, str) and value.strip().lower() in {"", "unknown", "none", "null"}:
                    return True
                return False
        return False

    def _is_generated_event_id(self, event_id: str) -> bool:
        normalized = event_id.strip().lower()
        return normalized.startswith("evt_") or normalized.startswith("evt-")

    def _is_generic_tool_name(self, tool_name: str) -> bool:
        normalized = self._normalize_match_text(tool_name)
        return normalized in {"", "unknowntool", "gpexecuteevent"}

    def _normalize_match_text(self, value: str) -> str:
        text = (value or "").strip()
        if not text:
            return ""
        if "/" in text or "\\" in text or ":" in text:
            return os.path.normcase(os.path.normpath(text))
        return text.lower()

    def _to_epoch_seconds(self, value: Any) -> float:
        try:
            return float(value.timestamp())
        except Exception:
            return 0.0
