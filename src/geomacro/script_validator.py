from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from .models import ExtractionResult


@dataclass(frozen=True)
class ValidationIssue:
    level: str
    message: str


@dataclass
class ValidationReport:
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(issue.level == "error" for issue in self.issues)


class ScriptValidator:
    """Run lightweight preflight checks for generated scripts."""

    def validate(self, script_text: str, extraction: ExtractionResult) -> ValidationReport:
        issues: List[ValidationIssue] = []
        self._validate_syntax(script_text, issues)
        self._validate_variable_paths(extraction, issues)
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
                        message=(
                            f"Variable {slot.name} is a path slot but default value is not text."
                        ),
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
            if not path_obj.exists():
                issues.append(
                    ValidationIssue(
                        level="warning",
                        message=f"Path for variable {slot.name} does not exist yet: {text}",
                    )
                )
