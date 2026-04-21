from __future__ import annotations

import re
from typing import Dict, Optional


class TemplateRegistry:
    """Registry for whitelisted ArcPy tool call targets."""

    DEFAULT_TOOL_MAP = {
        "buffer": "arcpy.analysis.Buffer",
        "clip": "arcpy.analysis.Clip",
        "dissolve": "arcpy.management.Dissolve",
        "merge": "arcpy.management.Merge",
        "featureclasstoshapefile": "arcpy.conversion.FeatureClassToShapefile",
    }

    def __init__(self, custom_tool_map: Optional[Dict[str, str]] = None) -> None:
        self._tool_map: Dict[str, str] = dict(self.DEFAULT_TOOL_MAP)
        if custom_tool_map:
            for tool_name, target in custom_tool_map.items():
                self._tool_map[tool_name.strip().lower()] = target

    def is_supported(self, tool_name: str) -> bool:
        return tool_name.strip().lower() in self._tool_map

    def resolve(self, tool_name: str) -> str:
        key = tool_name.strip().lower()
        if key in self._tool_map:
            return self._tool_map[key]
        return f"arcpy.management.{self._safe_tool_name(tool_name)}"

    def _safe_tool_name(self, tool_name: str) -> str:
        cleaned = re.sub(r"[^0-9A-Za-z_]", "", tool_name)
        if not cleaned:
            return "UnknownTool"
        if cleaned[0].isdigit():
            return f"Tool{cleaned}"
        return cleaned
