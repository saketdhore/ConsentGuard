"""Validated output schema for document-vs-brief checks."""

from __future__ import annotations

from dataclasses import dataclass, field

from engine.schemas.common import (
    DocumentSectionIdEnum,
    coerce_enum_list,
    ensure_bool,
    ensure_string_list,
)


@dataclass(slots=True)
class DocumentValidationResultSchema:
    is_valid: bool
    missing_sections: list[DocumentSectionIdEnum] = field(default_factory=list)
    missing_points: list[str] = field(default_factory=list)
    failed_constraints: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.is_valid = ensure_bool(self.is_valid, "is_valid")
        self.missing_sections = coerce_enum_list(
            self.missing_sections, DocumentSectionIdEnum, "missing_sections"
        )
        self.missing_points = ensure_string_list(self.missing_points, "missing_points")
        self.failed_constraints = ensure_string_list(
            self.failed_constraints, "failed_constraints"
        )
        self.warnings = ensure_string_list(self.warnings, "warnings")


DocumentValidationResult = DocumentValidationResultSchema


__all__ = ["DocumentValidationResult", "DocumentValidationResultSchema"]
