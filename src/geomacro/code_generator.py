from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

from .models import ExtractionResult, StandardEvent
from .template_registry import TemplateRegistry

_GIS_EXTENSIONS = {
    ".shp", ".tif", ".tiff", ".img", ".json", ".geojson",
    ".gdb", ".mdb", ".csv", ".txt", ".dbf",
}


class CodeGenerator:
    """Generate linear ArcPy batch-pipeline scripts from normalized events."""

    def __init__(self, template_registry: TemplateRegistry | None = None) -> None:
        self.template_registry = template_registry or TemplateRegistry()

    def generate(self, events: Sequence[StandardEvent], extraction: ExtractionResult) -> str:
        events = sorted(events, key=lambda item: item.timestamp)
        plan = _PipelinePlan.build(events, extraction)

        lines: List[str] = self._emit_header(plan)
        lines.extend(self._emit_run_pipeline(plan, events, extraction))
        lines.extend(self._emit_main())
        lines.extend(self._emit_entrypoint())
        return "\n".join(lines)

    # ── header ────────────────────────────────────────────────

    def _emit_header(self, plan: _PipelinePlan) -> List[str]:
        lines: List[str] = [
            '"""GeoMacro generated batch pipeline."""',
            "from pathlib import Path",
            "import os",
            "import sys",
            "import arcpy",
            "",
            "arcpy.env.overwriteOutput = True",
            "",
        ]

        if plan.has_inplace:
            lines.extend([
                "def _copy_features_for_inplace(src, dst):",
                "    if Path(src).suffix.lower() == '.shp':",
                "        Path(dst).parent.mkdir(parents=True, exist_ok=True)",
                "        arcpy.management.CopyFeatures(str(src), str(dst))",
                "        return str(dst)",
                "    Path(dst).parent.mkdir(parents=True, exist_ok=True)",
                "    arcpy.management.Copy(str(src), str(dst))",
                "    return str(dst)",
                "",
            ])

        for const_name, const_value in sorted(plan.fixed_inputs.items()):
            lines.append(f"{const_name} = {repr(const_value)}")
        if plan.fixed_inputs:
            lines.append("")

        lines.append(f"OUTPUT_DIR = {repr(plan.default_output_dir)}")
        lines.append(f"INPUT_GLOB = {repr(plan.input_glob)}")
        lines.append("")
        return lines

    # ── run_pipeline ─────────────────────────────────────────

    def _emit_run_pipeline(
        self,
        plan: _PipelinePlan,
        events: Sequence[StandardEvent],
        extraction: ExtractionResult,
    ) -> List[str]:
        lines: List[str] = [
            "",
            "def run_pipeline(input_file, output_dir=None):",
            '    """Run the toolchain on a single input file."""',
            "    output_dir = Path(output_dir or OUTPUT_DIR)",
            "    output_dir.mkdir(parents=True, exist_ok=True)",
            "    stem = Path(input_file).stem",
            "    working = str(Path(input_file).resolve())",
            "",
        ]

        used_labels: Set[str] = set()

        for event in events:
            call_target = self.template_registry.resolve(event.tool_name, event.tool_path)
            step_label = self._unique_step_label(call_target, used_labels)
            used_labels.add(step_label)

            is_inplace = self._is_inplace_modifier(event)
            if is_inplace:
                staging_var = f"stg_{step_label}"
                lines.append(
                    f"    {staging_var} = str(output_dir / f'{{stem}}_{step_label}{{Path(working).suffix}}')"
                )
                lines.append(f"    working = _copy_features_for_inplace(working, {staging_var})")

            arg_lines = self._emit_step_call(event, extraction, plan, step_label, is_inplace)
            lines.extend(arg_lines)
            lines.append("")

        if plan.has_inplace:
            lines.append("    return working")
        lines.append("")
        return lines

    def _emit_step_call(
        self,
        event: StandardEvent,
        extraction: ExtractionResult,
        plan: _PipelinePlan,
        step_label: str,
        is_inplace: bool = False,
    ) -> List[str]:
        call_target = self.template_registry.resolve(event.tool_name, event.tool_path)
        tokens: List[str] = []
        prepend: List[str] = []
        is_first_path_input = True
        output_ext: Optional[str] = None
        output_var: Optional[str] = None

        for idx, param in enumerate(event.ordered_params):
            safe_name = self._safe_param_name(param.name, idx)
            uses_keyword = not safe_name.startswith("par_")
            variable = extraction.get_variable(event.event_id, param.name)

            if variable is None:
                val = repr(param.value)
                tokens.append(f"{safe_name}={val}" if uses_keyword else val)
                continue

            if variable.kind == "input_path" and is_first_path_input and param.direction != "output":
                is_first_path_input = False
                expr = "working"
                tokens.append(f"{safe_name}={expr}" if uses_keyword else expr)
                continue

            if variable.kind == "input_path":
                const_name = f"FIXED_{safe_name.upper()}"
                tokens.append(f"{safe_name}={const_name}" if uses_keyword else const_name)
                continue

            if variable.kind == "output_path":
                if is_inplace and param.direction == "output":
                    continue
                ext = Path(str(param.value)).suffix or ".shp"
                output_ext = ext
                output_var = f"out_{step_label}"
                tokens.append(f"{safe_name}={output_var}" if uses_keyword else output_var)
                continue

            val = repr(param.value)
            tokens.append(f"{safe_name}={val}" if uses_keyword else val)

        if output_var:
            ext = output_ext or ".shp"
            prepend.append(
                f"    {output_var} = str(output_dir / f'{{stem}}_{step_label}{ext}')"
            )

        prepend.append(f"    {call_target}({', '.join(tokens)})")
        return prepend

    # ── main ─────────────────────────────────────────────────

    def _emit_main(self) -> List[str]:
        return [
            "",
            "def main(input_dir=None, output_dir=None):",
            "    input_dir = Path(input_dir or '.')",
            "    if output_dir is not None:",
            "        odir = output_dir",
            "    else:",
            "        odir = OUTPUT_DIR",
            "    Path(odir).mkdir(parents=True, exist_ok=True)",
            "",
            "    candidates = sorted(input_dir.glob(INPUT_GLOB))",
            "    if not candidates:",
            "        print('[GeoMacro] No files matching ' + repr(INPUT_GLOB) + ' found in ' + str(input_dir))",
            "        return",
            "",
            "    print('[GeoMacro] Found', len(candidates), 'input file(s)')",
            "    for candidate in candidates:",
            "        print('  Processing', candidate.name, '...')",
            "        try:",
            "            result = run_pipeline(",
            "                input_file=str(candidate),",
            "                output_dir=odir,",
            "            )",
            "            label = Path(result).name if result else 'done'",
            "            print('    -> ok:', label)",
            "        except Exception as exc:",
            "            print('    ERROR:', exc, file=sys.stderr)",
            "",
        ]

    # ── entrypoint ───────────────────────────────────────────

    def _emit_entrypoint(self) -> List[str]:
        return [
            "",
            "if __name__ == '__main__':",
            "    import argparse",
            "    parser = argparse.ArgumentParser(description='GeoMacro batch pipeline')",
            "    parser.add_argument('--input', '-i', default=None, help='Input directory (default: current dir)')",
            "    parser.add_argument('--output', '-o', default=None, help='Output directory (default: ./geomacro_output)')",
            "    args = parser.parse_args()",
            "    main(input_dir=args.input, output_dir=args.output)",
            "",
        ]

    # ── helpers ──────────────────────────────────────────────

    def _unique_step_label(self, call_target: str, used: Set[str]) -> str:
        base = call_target.split(".")[-1].lower()
        candidate = base
        idx = 2
        while candidate in used:
            candidate = f"{base}{idx}"
            idx += 1
        return candidate

    def _is_inplace_modifier(self, event: StandardEvent) -> bool:
        input_vals: List[str] = []
        output_vals: List[str] = []
        for param in event.ordered_params:
            val = str(param.value or "").replace("\\", "/").lower().rstrip("/")
            if param.direction == "input" and param.is_path and val:
                input_vals.append(val)
            if param.direction == "output" and param.is_path and val:
                output_vals.append(val)
        return bool(input_vals) and bool(output_vals) and any(
            iv == ov for iv in input_vals for ov in output_vals
        )

    def _safe_param_name(self, name: str, index: int = 0) -> str:
        safe = re.sub(r"[^0-9A-Za-z_]", "", name.strip()).strip("_")
        if safe and not safe[0].isdigit():
            return safe
        return f"par_{index}"


class _PipelinePlan:
    """Blueprint: loop variable, fixed inputs, output strategy."""

    def __init__(
        self,
        fixed_inputs: Dict[str, object] | None = None,
        default_output_dir: str = "./geomacro_output",
        input_glob: str = "*.shp",
        has_inplace: bool = False,
    ) -> None:
        self.fixed_inputs: Dict[str, object] = fixed_inputs or {}
        self.default_output_dir = default_output_dir
        self.input_glob = input_glob
        self.has_inplace = has_inplace

    @classmethod
    def build(cls, events: Sequence[StandardEvent], extraction: ExtractionResult) -> _PipelinePlan:
        first_input_value = ""
        first_input_idx = -1
        has_inplace = False
        fixed_inputs: Dict[str, object] = {}

        for event in events:
            for idx, param in enumerate(event.ordered_params):
                variable = extraction.get_variable(event.event_id, param.name)
                if variable is None or variable.kind != "input_path":
                    continue
                val = str(param.value)
                if not first_input_value:
                    first_input_value = val
                    first_input_idx = idx
                    continue
                if val == first_input_value:
                    continue
                safe = _pipeline_safe_name(param.name, idx)
                const_name = f"FIXED_{safe.upper()}"
                fixed_inputs.setdefault(const_name, variable.default_value)

            if not cls._detect_inplace(event):
                continue
            has_inplace = True

        ext = Path(first_input_value).suffix if first_input_value else ""
        input_glob = f"*{ext}" if ext.lower() in _GIS_EXTENSIONS else "*.shp"

        return cls(
            fixed_inputs=fixed_inputs,
            input_glob=input_glob,
            has_inplace=has_inplace,
        )

    @staticmethod
    def _detect_inplace(event: StandardEvent) -> bool:
        input_vals: List[str] = []
        output_vals: List[str] = []
        for param in event.ordered_params:
            val = str(param.value or "").replace("\\", "/").lower().rstrip("/")
            if param.direction == "input" and param.is_path and val:
                input_vals.append(val)
            if param.direction == "output" and param.is_path and val:
                output_vals.append(val)
        return bool(input_vals) and bool(output_vals) and any(
            iv == ov for iv in input_vals for ov in output_vals
        )


def _pipeline_safe_name(name: str, index: int) -> str:
    safe = re.sub(r"[^0-9A-Za-z_]", "", name.strip()).strip("_")
    if safe and not safe[0].isdigit():
        return safe
    return f"par_{index}"
