#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from geomacro.history_collector import HistoryCollector
from geomacro.history_xml_reader import discover_history_directories, load_history_items_from_xml
from geomacro.session_store import SessionStore


GENERIC_TOOL_NAMES = {"", "unknowntool", "gpexecuteevent"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Commit 2 helper: merge live GeoMacro events with ArcGIS history and export normalized session JSON."
    )

    parser.add_argument(
        "--event-dir",
        default=str(Path.home() / "Documents" / "GeoMacro" / "runtime" / "events"),
        help="Directory containing GeoMacro live event jsonl files.",
    )
    parser.add_argument(
        "--live-jsonl",
        default="",
        help="Optional explicit jsonl file path. If omitted, uses latest gp-events-*.jsonl in --event-dir.",
    )
    parser.add_argument(
        "--tail-live",
        type=int,
        default=300,
        help="Max number of recent live jsonl lines to read (0 means all).",
    )

    parser.add_argument(
        "--history-dir",
        action="append",
        default=[],
        help="Optional ArcGIS history XML directory (can be repeated).",
    )
    parser.add_argument(
        "--history-json",
        default="",
        help="Optional path to additional history JSON array file.",
    )
    parser.add_argument(
        "--history-files",
        type=int,
        default=30,
        help="Number of newest history XML files to scan.",
    )
    parser.add_argument(
        "--lookback-hours",
        type=int,
        default=24,
        help="Only include history XML files modified in this lookback window.",
    )

    parser.add_argument("--window-size", type=int, default=200, help="HistoryCollector window_size.")
    parser.add_argument("--dedup-window-seconds", type=int, default=5, help="Dedup time bucket size.")
    parser.add_argument(
        "--history-match-window-seconds",
        type=int,
        default=8,
        help="Max allowed timestamp delta when matching live and history events.",
    )
    parser.add_argument("--include-failed", action="store_true", help="Keep failed events in output.")

    parser.add_argument(
        "--output",
        default="",
        help="Output JSON path. Default: runtime/merged/commit2-merged-<timestamp>.json",
    )
    parser.add_argument(
        "--print-events",
        type=int,
        default=10,
        help="Print first N merged events as quick preview.",
    )
    parser.add_argument(
        "--only-named-events",
        action="store_true",
        help="Drop unresolved generic events (UnknownTool/GPExecuteEvent with no params/outputs).",
    )

    return parser.parse_args()


def load_live_events(live_jsonl: Path, tail_live: int) -> List[Dict[str, Any]]:
    if not live_jsonl.exists():
        raise FileNotFoundError(f"Live jsonl not found: {live_jsonl}")

    lines = live_jsonl.read_text(encoding="utf-8").splitlines()
    if tail_live > 0:
        lines = lines[-tail_live:]

    events: List[Dict[str, Any]] = []
    for line in lines:
        text = line.strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)

    return events


def load_history_json_file(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"History JSON file not found: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    raise ValueError("History JSON must be a list of objects.")


def resolve_live_jsonl_path(event_dir: Path, explicit_live_jsonl: str) -> Path:
    if explicit_live_jsonl:
        return Path(explicit_live_jsonl).expanduser()

    if not event_dir.exists():
        raise FileNotFoundError(f"Event directory not found: {event_dir}")

    candidates = sorted(event_dir.glob("gp-events-*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise FileNotFoundError(
            f"No live event jsonl files found in: {event_dir}. Run ArcGIS tool once with capture enabled first."
        )

    return candidates[0]


def ensure_output_path(explicit_output: str) -> Path:
    if explicit_output:
        output = Path(explicit_output).expanduser()
    else:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output = REPO_ROOT / "runtime" / "merged" / f"commit2-merged-{timestamp}.json"

    output.parent.mkdir(parents=True, exist_ok=True)
    return output


def preview_events(events: Sequence[Any], count: int) -> None:
    if count <= 0:
        return

    print("--- merged preview ---")
    for event in list(events)[:count]:
        ts = getattr(event, "timestamp", "")
        tool = getattr(event, "tool_name", "")
        event_id = getattr(event, "event_id", "")
        success = getattr(event, "is_success", "")
        print(f"{ts} | {event_id} | {tool} | success={success}")


def is_unresolved_generic_event(event: Any) -> bool:
    tool_name = str(getattr(event, "tool_name", "") or "").strip().lower()
    if tool_name not in GENERIC_TOOL_NAMES:
        return False

    tool_path = str(getattr(event, "tool_path", "") or "").strip()
    ordered_params = list(getattr(event, "ordered_params", []) or [])
    outputs = list(getattr(event, "outputs", []) or [])
    messages = list(getattr(event, "messages", []) or [])

    return not tool_path and not ordered_params and not outputs and len(messages) <= 1


def main() -> int:
    args = parse_args()

    event_dir = Path(args.event_dir).expanduser()
    live_jsonl = resolve_live_jsonl_path(event_dir, args.live_jsonl)

    live_events = load_live_events(live_jsonl, args.tail_live)

    history_dirs = discover_history_directories(args.history_dir)
    history_items = load_history_items_from_xml(
        history_dirs=history_dirs,
        max_files=args.history_files,
        lookback_hours=args.lookback_hours,
    )

    if args.history_json:
        history_items.extend(load_history_json_file(Path(args.history_json).expanduser()))

    collector = HistoryCollector(
        window_size=args.window_size,
        include_failed=args.include_failed,
        dedup_window_seconds=args.dedup_window_seconds,
        history_match_window_seconds=args.history_match_window_seconds,
    )

    merged_events = collector.collect_incremental(
        live_events=live_events,
        history_items=history_items,
    )

    unresolved_count = sum(1 for event in merged_events if is_unresolved_generic_event(event))
    resolved_count = len(merged_events) - unresolved_count

    if args.only_named_events:
        merged_events = [event for event in merged_events if not is_unresolved_generic_event(event)]

    output_path = ensure_output_path(args.output)
    SessionStore(str(output_path)).save_events(merged_events)

    print(f"Live events loaded: {len(live_events)}")
    print(f"History dirs used: {len(history_dirs)}")
    for history_dir in history_dirs:
        print(f"  - {history_dir}")
    print(f"History items loaded: {len(history_items)}")
    print(f"Merged incremental events: {len(merged_events)}")
    print(f"Resolved (named) events: {resolved_count}")
    print(f"Unresolved generic events: {unresolved_count}")
    if unresolved_count > 0:
        print(
            "Warning: unresolved generic events mean no matching history item was found "
            "within your lookback/match window."
        )
        print(
            "Tip: run the merge immediately after executing tools, or use --only-named-events "
            "to export only enriched records."
        )
    print(f"Output: {output_path}")

    preview_events(merged_events, args.print_events)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
