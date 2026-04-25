from __future__ import annotations

import os
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
        "calculatefield": "arcpy.management.CalculateField",
        "addfield": "arcpy.management.AddField",
        "select": "arcpy.analysis.Select",
        "rastercalculator": "arcpy.sa.RasterCalculator",
        "extractbyattributes": "arcpy.sa.ExtractByAttributes",
        "zonalstatisticsastable": "arcpy.sa.ZonalStatisticsAsTable",
        "repairgeometry": "arcpy.management.RepairGeometry",
        "project": "arcpy.management.Project",
    }

    def __init__(self, custom_tool_map: Optional[Dict[str, str]] = None) -> None:
        self._tool_map: Dict[str, str] = dict(self.DEFAULT_TOOL_MAP)
        if custom_tool_map:
            for tool_name, target in custom_tool_map.items():
                self._tool_map[tool_name.strip().lower()] = target

    def resolve(self, tool_name: str, tool_path: str = "") -> str:
        lookup_key = self._extract_internal_name(tool_name, tool_path)
        if lookup_key in self._tool_map:
            return self._tool_map[lookup_key]
        return f"arcpy.management.{self._safe_tool_name(tool_name)}"

    def is_supported(self, tool_name: str, tool_path: str = "") -> bool:
        lookup_key = self._extract_internal_name(tool_name, tool_path)
        return lookup_key in self._tool_map

    def _extract_internal_name(self, tool_name: str, tool_path: str = "") -> str:
        key = tool_name.strip().lower()
        if key in self._tool_map:
            return key

        if tool_path:
            normalized = tool_path.replace("\\", "/")
            segments = [s for s in normalized.split("/") if s and s != "arcgis" and not s.endswith(".tbx")]
            for segment in reversed(segments):
                clean = re.sub(r"[^0-9A-Za-z_]", "", segment)
                clean_lower = clean.lower()
                if clean_lower in self._tool_map:
                    return clean_lower

        return key

    def _safe_tool_name(self, tool_name: str) -> str:
        cleaned = re.sub(r"[^0-9A-Za-z_]", "", tool_name)
        if not cleaned:
            return "UnknownTool"
        if cleaned[0].isdigit():
            return f"Tool{cleaned}"
        return cleaned
