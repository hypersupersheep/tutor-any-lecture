"""The result of one quality check, shared by every checker."""

from __future__ import annotations

from dataclasses import dataclass

# The detail of a check that cannot read the note's script or language: always a WARN.
NOT_APPLIED = "not applied for this language"


@dataclass
class CheckResult:
    name: str
    status: str  # "PASS", "WARN" or "FAIL"
    details: list[str]
