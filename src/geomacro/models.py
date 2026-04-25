from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class ProductSource(Enum):
    DESKTOP = "arcgis_desktop"
    PRO = "arcgis_pro"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Parameter:
    name: str
    value: Any
    direction: str = "input"
    is_path: bool = False


@dataclass(frozen=True)
class StandardEvent:
    event_id: str
    tool_name: str
    tool_path: str
    timestamp: datetime
    is_success: bool
    ordered_params: List[Parameter] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)
    source: str = "unknown"


def detect_product_source(
    tool_path: str = "",
    history_source: str = "",
    tool_name: str = "",
) -> str:
    """
    Detect the ArcGIS product source from tool path, history source, etc.
    Returns one of "arcgis_desktop", "arcgis_pro", or "unknown".
    """
    clues = [tool_path.lower(), history_source.lower(), tool_name.lower()]
    combined = " ".join(clues)

    if "desktop10." in combined or "desktop\\10." in combined or "arcgis\\desktop" in combined:
        return ProductSource.DESKTOP.value
    if "arcgispro" in combined or "arcgis_pro" in combined or "\\pro\\" in combined:
        return ProductSource.PRO.value
    if "arctoolbox\\toolboxes" in combined.replace("/", "\\") and "arcgispro" not in combined:
        return ProductSource.DESKTOP.value
    return ProductSource.UNKNOWN.value


@dataclass(frozen=True)
class VariableSlot:
    name: str
    default_value: Any
    kind: str
    source_event_id: str
    source_param_name: str


@dataclass
class ExtractionResult:
    variable_slots: Dict[Tuple[str, str], VariableSlot] = field(default_factory=dict)
    constants: Dict[Tuple[str, str], Any] = field(default_factory=dict)

    def get_variable(self, event_id: str, param_name: str) -> Optional[VariableSlot]:
        return self.variable_slots.get((event_id, param_name))


@dataclass(frozen=True)
class StepNode:
    event_id: str
    tool_name: str
    depends_on: List[str] = field(default_factory=list)
