from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Sequence

from .models import ExtractionResult, StandardEvent


@dataclass(frozen=True)
class ValidationIssue:
    level: str
    message: str

    @property
    def is_error(self) -> bool:
        return self.level == "error"

    @property
    def is_warning(self) -> bool:
        return self.level == "warning"

    @property
    def is_info(self) -> bool:
        return self.level == "info"


@dataclass
class ValidationReport:
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.is_error)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.is_warning)

    @property
    def ok(self) -> bool:
        return self.error_count == 0

    def summary_text(self, use_emoji: bool = True) -> str:
        ok_icon = "[OK]" if not use_emoji else "[OK]"
        fail_icon = "[FAIL]" if not use_emoji else "[FAIL]"
        error_icon = "[ERROR]"
        warn_icon = "[WARN]"
        info_icon = "[INFO]"

        lines = [
            "+---------------------------------------+",
            "|    GeoMacro Script Validation Report  |",
            "+---------------------------------------+",
            f"  Status: {ok_icon if self.ok else fail_icon}  ({self.error_count} errors, {self.warning_count} warnings)",
            "",
        ]
        if self.issues:
            lines.append("  -- Details --")
            for idx, issue in enumerate(self.issues, 1):
                icon = {"error": error_icon, "warning": warn_icon, "info": info_icon}.get(issue.level, "  ")
                lines.append(f"  {icon} [{issue.level.upper()}] {issue.message}")
            lines.append("")
        return "\n".join(lines)


class ScriptValidator:
    """Run comprehensive preflight checks for generated scripts."""

    def validate(
        self,
        script_text: str,
        extraction: ExtractionResult,
        events: Sequence[StandardEvent] | None = None,
    ) -> ValidationReport:
        issues: List[ValidationIssue] = []
        self._validate_syntax(script_text, issues)
        self._validate_variable_paths(extraction, issues)
        self._validate_chinese_paths(extraction, issues)
        if events is not None:
            self._validate_events(events, extraction, issues)
        return ValidationReport(issues=issues)

    def _validate_syntax(self, script_text: str, issues: List[ValidationIssue]) -> None:
        try:
            compile(script_text, "generated_geomacro.py", "exec")
        except SyntaxError as exc:
            issues.append(
                ValidationIssue(
                    level="error",
                    message=f"Syntax error at line {exc.lineno}: {exc.msg}",
                )
            )
        except Exception as exc:
            issues.append(
                ValidationIssue(
                    level="error",
                    message=f"Script compilation failed: {exc}",
                )
            )

    def _validate_variable_paths(
        self,
        extraction: ExtractionResult,
        issues: List[ValidationIssue],
    ) -> None:
        for slot in extraction.variable_slots.values():
            if not slot.kind.endswith("_path"):
                continue
            if not isinstance(slot.default_value, str):
                issues.append(
                    ValidationIssue(
                        level="warning",
                        message=f"Variable {slot.name} is a path slot but default value is not text.",
                    )
                )
                continue
            text = slot.default_value.strip()
            if not text:
                issues.append(
                    ValidationIssue(
                        level="warning",
                        message=f"Variable {slot.name} has an empty default path.",
                    )
                )
                continue
            path_obj = Path(text)
            if slot.kind == "output_path":
                if not path_obj.parent.exists():
                    issues.append(
                        ValidationIssue(
                            level="info",
                            message=f"Output variable {slot.name} has parent directory that does not exist yet: {text}",
                        )
                    )
            elif not path_obj.exists():
                issues.append(
                    ValidationIssue(
                        level="warning",
                        message=f"Input variable {slot.name} does not exist: {text}",
                    )
                )

    def _validate_chinese_paths(
        self,
        extraction: ExtractionResult,
        issues: List[ValidationIssue],
    ) -> None:
        for slot in extraction.variable_slots.values():
            if not slot.kind.endswith("_path"):
                continue
            if isinstance(slot.default_value, str) and _has_non_ascii(slot.default_value):
                issues.append(
                    ValidationIssue(
                        level="warning",
                        message=f"Variable {slot.name} contains non-ASCII characters in path. "
                        f"This may cause encoding issues in Batch scripts: {slot.default_value}",
                    )
                )

    def _validate_events(
        self,
        events: Sequence[StandardEvent],
        extraction: ExtractionResult,
        issues: List[ValidationIssue],
    ) -> None:
        for event in events:
            if not event.is_success:
                issues.append(
                    ValidationIssue(
                        level="warning",
                        message=f"Event '{event.tool_name}' (id={event.event_id[:16]}...) recorded as failed. "
                        f"Generated script may not produce expected results.",
                    )
                )

            for param in event.ordered_params:
                key = (event.event_id, param.name)
                if param.is_path and key not in extraction.variable_slots and key not in extraction.constants:
                    issues.append(
                        ValidationIssue(
                            level="warning",
                            message=f"Path parameter '{param.name}' in '{event.tool_name}' was not extracted: {param.value}",
                        )
                    )

                if param.direction == "input" and param.is_path and isinstance(param.value, str):
                    pv = param.value.strip()
                    if pv and not Path(pv).exists():
                        issues.append(
                            ValidationIssue(
                                level="warning",
                                message=f"Input path for '{event.tool_name}' does not exist on disk: {pv}",
                            )
                        )

        failed_count = sum(1 for e in events if not e.is_success)
        if failed_count:
            issues.insert(0, ValidationIssue(
                level="info",
                message=f"Found {failed_count} failed event(s). Use include_failed=True to include them.",
            ))

    def report_to_file(self, report: ValidationReport, output_path: str) -> None:
        Path(output_path).write_text(report.summary_text(), encoding="utf-8")


def _has_non_ascii(text: str) -> bool:
    return any(ord(c) > 127 for c in text)
