"""GeoMacro CLI — one-command pipeline from history capture to script generation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .code_generator import CodeGenerator
from .event_normalizer import EventNormalizer
from .history_parser import HistoryParser
from .history_xml_reader import discover_history_directories, load_history_items_from_xml
from .script_validator import ScriptValidator
from .template_registry import TemplateRegistry
from .variable_extractor import VariableExtractor


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="geomacro",
        description="GeoMacro: auto-generate batch ArcPy scripts from ArcGIS geoprocessing history.",
    )
    parser.add_argument("--lookback", "-l", type=int, default=24,
                        help="Look back hours for history XML (default: 24)")
    parser.add_argument("--max-files", "-m", type=int, default=30,
                        help="Max history XML files to scan (default: 30)")
    parser.add_argument("--output-dir", "-o", default="./output",
                        help="Output directory for script and report (default: ./output)")
    parser.add_argument("--include-failed", "-f", action="store_true",
                        help="Include failed geoprocessing events")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Suppress verbose output")
    args = parser.parse_args()

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if not args.quiet:
        print(">>> GeoMacro Pipeline <<<")
        print(f"  Scanning history XMLs (lookback={args.lookback}h, max={args.max_files} files)")

    dirs = discover_history_directories()
    if not args.quiet:
        print(f"  Found {len(dirs)} history directory(ies)")

    items = load_history_items_from_xml(dirs, max_files=args.max_files, lookback_hours=args.lookback)
    if not items:
        print("[GeoMacro] No history items found. Run geoprocessing tools first, then retry.")
        sys.exit(1)

    normalized = EventNormalizer().normalize_many(HistoryParser().parse_many(items))
    if not args.quiet:
        print(f"  Parsed {len(normalized)} geoprocessing events")
        failed = sum(1 for e in normalized if not e.is_success)
        if failed:
            print(f"  ({failed} failed events, use --include-failed to include)")

    if not args.include_failed:
        normalized = [e for e in normalized if e.is_success]

    registry = TemplateRegistry()
    supported = [e for e in normalized if registry.is_supported(e.tool_name, e.tool_path)]

    if not supported:
        print("[GeoMacro] No supported tools found in history. Supported tools:")
        for name in sorted(registry.DEFAULT_TOOL_MAP):
            print(f"    - {name}")
        sys.exit(1)

    if not args.quiet:
        print(f"  Whitelist match: {len(supported)}/{len(normalized)} events")
        for e in supported:
            print(f"    + {e.tool_name} -> {registry.resolve(e.tool_name, e.tool_path)}")

    extraction = VariableExtractor().extract(supported)
    script = CodeGenerator(registry).generate(supported, extraction)
    report = ScriptValidator().validate(script, extraction, events=supported)

    script_path = out_dir / "generated_script.py"
    report_path = out_dir / "validation_report.txt"

    script_path.write_text(script, encoding="utf-8")
    report_path.write_text(report.summary_text(use_emoji=False), encoding="utf-8")

    if not args.quiet:
        print(f"\n  Script saved: {script_path.resolve()}")
        print(f"  Report saved: {report_path.resolve()}")
        print(f"\n{report.summary_text(use_emoji=False)}")
        print(f"  To run: python {script_path.resolve()} --input DIR --output DIR")
    else:
        print(f"[GeoMacro] OK  errors={report.error_count}  warnings={report.warning_count}  script={script_path}")


if __name__ == "__main__":
    main()
