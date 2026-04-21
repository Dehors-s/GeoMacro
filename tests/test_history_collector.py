import os

from geomacro.history_collector import HistoryCollector


def test_history_collector_enriches_live_event_from_history_match():
    collector = HistoryCollector(
        window_size=10,
        include_failed=True,
        dedup_window_seconds=5,
        history_match_window_seconds=10,
    )

    live_events = [
        {
            "ExecuteId": "evt-063238001",
            "ToolName": "UnknownTool",
            "ToolPath": "",
            "TimestampUtc": "2026-04-21T06:32:38Z",
            "IsSuccess": None,
            "ResultSummary": "IsBeginning=False",
        }
    ]

    history_items = [
        {
            "ID": "history_buffer_1",
            "TimeStamp": "2026-04-21T06:32:39Z",
            "ToolPath": "analysis/Buffer",
            "ToolName": "Buffer",
            "Succeeded": True,
            "Parameters": [
                {"name": "in_features", "value": r"D:\\input\\roads.shp", "is_path": True},
                {
                    "name": "out_feature_class",
                    "value": r"D:\\scratch\\roads_buf.shp",
                    "direction": "output",
                    "is_path": True,
                },
            ],
            "Outputs": [r"D:\\scratch\\roads_buf.shp"],
            "Messages": ["done"],
        }
    ]

    events = collector.collect_incremental(live_events=live_events, history_items=history_items)

    assert len(events) == 1
    event = events[0]
    assert event.event_id == "history_buffer_1"
    assert event.tool_name == "Buffer"
    assert event.tool_path == "analysis/Buffer"
    assert event.is_success is True
    assert len(event.ordered_params) == 2
    assert event.outputs == [os.path.normpath(r"D:\\scratch\\roads_buf.shp")]
    assert "done" in event.messages


def test_history_collector_snapshot_only_returns_new_events():
    collector = HistoryCollector(window_size=10, include_failed=True)

    live_events = [
        {
            "ExecuteId": "evt-live-1",
            "ToolName": "UnknownTool",
            "ToolPath": "",
            "TimestampUtc": "2026-04-21T06:35:10Z",
            "IsSuccess": None,
        }
    ]

    history_items = [
        {
            "ID": "history_clip_1",
            "TimeStamp": "2026-04-21T06:35:11Z",
            "ToolPath": "analysis/Clip",
            "ToolName": "Clip",
            "Succeeded": True,
            "Parameters": [
                {"name": "in_features", "value": r"D:\\scratch\\roads_buf.shp", "is_path": True},
                {"name": "clip_features", "value": r"D:\\input\\boundary.shp", "is_path": True},
                {
                    "name": "out_feature_class",
                    "value": r"D:\\output\\roads_clip.shp",
                    "direction": "output",
                    "is_path": True,
                },
            ],
        }
    ]

    first = collector.collect_incremental(live_events=live_events, history_items=history_items)
    second = collector.collect_incremental(live_events=live_events, history_items=history_items)

    assert len(first) == 1
    assert second == []


def test_history_collector_treats_unknown_success_as_success_by_default():
    collector = HistoryCollector(window_size=10, include_failed=False)

    events = collector.collect_incremental(
        live_events=[
            {
                "ExecuteId": "evt-live-unknown-success",
                "ToolName": "UnknownTool",
                "ToolPath": "",
                "TimestampUtc": "2026-04-21T06:40:00Z",
                "IsSuccess": None,
            }
        ],
        history_items=[],
    )

    assert len(events) == 1
    assert events[0].is_success is True
