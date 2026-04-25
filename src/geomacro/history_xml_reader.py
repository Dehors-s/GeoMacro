from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence
import xml.etree.ElementTree as ET

from .models import detect_product_source


_PATH_PARAM_TYPES = {
    "dataset",
    "layer",
    "deworkspace",
    "workspace",
    "file",
    "folder",
    "feature class",
    "featureclass",
    "raster dataset",
    "table",
}

_NON_PATH_PARAM_TYPES = {
    "scalar",
    "string",
    "boolean",
    "long",
    "double",
    "field",
    "sql expression",
    "units",
}


def discover_history_directories(explicit_dirs: Optional[Sequence[str]] = None) -> List[Path]:
    candidates: List[Path] = []

    for explicit in explicit_dirs or []:
        path = Path(explicit).expanduser()
        if path.exists():
            candidates.append(path)

    appdata = os.environ.get("APPDATA", "")
    if appdata:
        appdata_root = Path(appdata)
        candidates.append(appdata_root / "ESRI" / "ArcGISPro" / "ArcToolbox" / "History")

        esri_root = appdata_root / "ESRI"
        if esri_root.exists():
            for desktop_dir in sorted(esri_root.glob("Desktop*")):
                candidates.append(desktop_dir / "ArcToolbox" / "History")

    deduped: List[Path] = []
    seen = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.exists() and resolved.is_dir():
            deduped.append(resolved)

    return deduped


def load_history_items_from_xml(
    history_dirs: Sequence[Path],
    max_files: int = 30,
    lookback_hours: int = 24,
) -> List[Dict[str, Any]]:
    xml_files = _collect_recent_xml_files(
        history_dirs=history_dirs,
        max_files=max_files,
        lookback_hours=lookback_hours,
    )

    items: List[Dict[str, Any]] = []
    for xml_path in xml_files:
        try:
            items.extend(_parse_history_xml_file(xml_path))
        except Exception:
            continue

    return items


def _collect_recent_xml_files(
    history_dirs: Sequence[Path],
    max_files: int,
    lookback_hours: int,
) -> List[Path]:
    candidates: List[Path] = []

    cutoff = datetime.utcnow() - timedelta(hours=max(0, lookback_hours))
    for history_dir in history_dirs:
        for path in history_dir.glob("*.xml"):
            try:
                modified = datetime.utcfromtimestamp(path.stat().st_mtime)
            except OSError:
                continue
            if lookback_hours > 0 and modified < cutoff:
                continue
            candidates.append(path)

    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    if max_files > 0:
        return candidates[:max_files]
    return candidates


def _parse_history_xml_file(xml_path: Path) -> List[Dict[str, Any]]:
    raw = _recover_truncated_xml(xml_path)
    if raw is None:
        try:
            raw = xml_path.read_bytes()
        except OSError:
            return []

    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return []

    result_views = root.findall("./ResultView")
    items: List[Dict[str, Any]] = []
    for index, result_view in enumerate(result_views):
        item = _parse_result_view(result_view, xml_path, index)
        if item is not None:
            items.append(item)

    return items


def _recover_truncated_xml(xml_path: Path) -> Optional[bytes]:
    """Recover truncated XML by appending missing close tags."""
    try:
        raw = xml_path.read_bytes()
    except OSError:
        return None
    if not raw:
        return None

    text = raw.decode("utf-8", errors="replace")

    import re as _re
    open_rv = len(_re.findall(r"<ResultView[>\s]", text))
    close_rv = text.count("</ResultView>")

    for _ in range(open_rv - close_rv):
        text += "\n</ResultView>\n"
    if text.count("<ResultViews") > text.count("</ResultViews"):
        text += "\n</ResultViews>\n"

    return text.encode("utf-8")


def _parse_result_view(result_view: ET.Element, xml_path: Path, index: int) -> Optional[Dict[str, Any]]:
    tool_name = (result_view.attrib.get("Tool") or "").strip() or "UnknownTool"
    tool_path = _node_text(result_view.find("./ToolSource"))
    command_line = _node_text(result_view.find("./CommandLine"))

    start_time_text = _node_text(result_view.find("./StartTime"))
    timestamp = _parse_start_time(start_time_text)

    end_time_text = _node_text(result_view.find("./EndTime"))

    layer_lookup = _parse_layer_info(result_view)
    parameters = []
    parameters.extend(
        _parse_parameter_nodes(
            result_view.findall("./Parameters/Inputs/Parameter"),
            direction="input",
            layer_lookup=layer_lookup,
        )
    )
    parameters.extend(
        _parse_parameter_nodes(
            result_view.findall("./Parameters/Outputs/Parameter"),
            direction="output",
            layer_lookup=layer_lookup,
        )
    )

    outputs = [
        str(param["value"])
        for param in parameters
        if param.get("direction") == "output" and isinstance(param.get("value"), str)
    ]

    messages: List[str] = []
    if command_line:
        messages.append(command_line)
    if end_time_text:
        messages.append(end_time_text)

    message_nodes = result_view.findall("./Messages/Message")
    for msg_node in message_nodes:
        msg_text = _node_text(msg_node)
        if msg_text:
            messages.append(msg_text)

    event_id = _build_history_event_id(xml_path, index, tool_path, timestamp, command_line)

    return {
        "ID": event_id,
        "TimeStamp": timestamp,
        "ToolPath": tool_path,
        "ToolName": tool_name,
        "Succeeded": _parse_success_from_end_text(end_time_text, messages),
        "Parameters": parameters,
        "Outputs": outputs,
        "Messages": messages,
        "HistorySource": str(xml_path),
        "source": detect_product_source(
            tool_path=tool_path,
            history_source=str(xml_path),
            tool_name=tool_name,
        ),
    }


def _parse_layer_info(result_view: ET.Element) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for layer_node in result_view.findall("./Parameters/LayerInfo/Layer"):
        name = (layer_node.attrib.get("Name") or "").strip()
        value = _node_text(layer_node)
        if name and value:
            mapping[name] = value
    return mapping


def _parse_parameter_nodes(
    nodes: Iterable[ET.Element],
    direction: str,
    layer_lookup: Dict[str, str],
) -> List[Dict[str, Any]]:
    params: List[Dict[str, Any]] = []

    for idx, node in enumerate(nodes, start=1):
        label = (node.attrib.get("Label") or "").strip() or f"param_{idx}"
        param_type = (node.attrib.get("Type") or "").strip()

        value = _node_text(node)
        if value in layer_lookup:
            value = layer_lookup[value]

        is_path = _is_probable_path_param(value, param_type)

        params.append(
            {
                "name": label,
                "value": value,
                "direction": direction,
                "is_path": is_path,
            }
        )

    return params


def _is_probable_path_param(value: str, param_type: str) -> bool:
    normalized_type = param_type.strip().lower()
    if normalized_type in _PATH_PARAM_TYPES:
        return True
    if normalized_type in _NON_PATH_PARAM_TYPES:
        return False

    text = value.strip()
    if not text:
        return False

    if ":\\" in text or text.startswith("\\\\") or text.startswith("//"):
        return True

    lowered = text.lower()
    if lowered.endswith((".shp", ".gdb", ".tif", ".img", ".json", ".csv", ".txt")):
        return True

    if "/" in text or "\\" in text:
        return True

    return False


def _parse_start_time(text: str) -> str:
    value = text.strip()
    if not value:
        return datetime.utcnow().isoformat()

    formats = [
        "%a %b %d %H:%M:%S %Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y年%m月%d日 %H:%M:%S",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.isoformat()
        except ValueError:
            continue

    return value


def _parse_success_from_end_text(text: str, messages: Optional[List[str]] = None) -> bool:
    lowered = text.lower()
    if any(token in lowered for token in ("失败", "error", "failed", "错误")):
        return False
    if any(token in lowered for token in ("成功", "succeeded", "complete", "completed")):
        return True

    if messages:
        all_text = " ".join(msg.lower() for msg in messages)
        if any(token in all_text for token in ("失败", "error", "failed", "错误")):
            return False
        if any(token in all_text for token in ("成功", "succeeded", "complete", "completed")):
            return True

    return True


def _build_history_event_id(
    xml_path: Path,
    index: int,
    tool_path: str,
    timestamp: str,
    command_line: str,
) -> str:
    signature = "|".join([str(xml_path), str(index), tool_path, timestamp, command_line])
    digest = hashlib.sha1(signature.encode("utf-8")).hexdigest()[:20]
    return f"hist_{digest}"


def _node_text(node: Optional[ET.Element]) -> str:
    if node is None:
        return ""
    return (node.text or "").strip()
