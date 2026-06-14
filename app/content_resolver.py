from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config import project_path
from app.constants import (
    CONTENT_EXTENSIONS,
    CONTENT_KIND_IMAGE,
    CONTENT_KIND_MISSING,
    CONTENT_KIND_VIDEO,
    IMAGE_EXTENSIONS,
    SCENARIO_AFTER,
    SCENARIO_BEFORE,
    SCENARIO_IDLE,
    SCENARIO_VIDEO,
    VALID_YY_PATTERN,
    VIDEO_EXTENSIONS,
)


@dataclass(frozen=True)
class ResolvedContent:
    scenario: str
    year: int | None
    expected_name: str
    path: Path | None
    exists: bool
    kind: str
    error: str | None = None

    @property
    def file_name(self) -> str:
        if self.path is not None:
            return self.path.name
        return self.expected_name


@dataclass
class ContentCheckResult:
    content_dir: Path
    missing: list[str] = field(default_factory=list)
    empty: list[str] = field(default_factory=list)
    unreadable: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.missing and not self.empty and not self.unreadable

    @property
    def summary(self) -> str:
        if self.ok:
            return "ok"
        parts: list[str] = []
        if self.missing:
            parts.append(f"missing={len(self.missing)}")
        if self.empty:
            parts.append(f"empty={len(self.empty)}")
        if self.unreadable:
            parts.append(f"unreadable={len(self.unreadable)}")
        return ", ".join(parts)


class ContentResolver:
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.content_config = config["content"]
        self.content_dir = project_path(self.content_config.get("path", "./content"))
        self.valid_years_from = int(self.content_config.get("validYearsFrom", 2016))
        self.valid_years_to = int(self.content_config.get("validYearsTo", 2026))
        self.year_prefix = str(config["input"].get("yearPrefix", "20"))
        self.year_file_pattern = str(self.content_config.get("yearFilePattern", "{year}.mp4"))

    def check_content(self) -> ContentCheckResult:
        result = ContentCheckResult(content_dir=self.content_dir)
        if not self.content_dir.exists():
            result.missing.append(str(self.content_dir))
            return result

        for year in range(self.valid_years_from, self.valid_years_to + 1):
            file_name = self.year_file_pattern.format(year=year)
            path = self.content_dir / file_name
            self._check_required_file(path, file_name, result)

        for configured_name in (
            str(self.content_config.get("idle", "idle.mp4")),
            str(self.content_config.get("beforeRange", "before_2016.mp4")),
            str(self.content_config.get("afterRange", "after_2026.mp4")),
        ):
            best_file = self._find_best_file(configured_name)
            if best_file is not None:
                self._check_required_file(best_file, best_file.name, result)
                continue

            stem = Path(configured_name).stem
            candidates = [self.content_dir / f"{stem}{extension}" for extension in CONTENT_EXTENSIONS]
            existing = [path for path in candidates if path.exists()]
            if existing:
                result.empty.extend(path.name for path in existing if path.stat().st_size == 0)
            else:
                result.missing.append(f"{stem}(.mp4/.png/.jpg/.jpeg)")
        return result

    def resolve_yy(self, value: str) -> ResolvedContent:
        value = value.strip()
        if not re.fullmatch(VALID_YY_PATTERN, value):
            return self._missing(SCENARIO_VIDEO, None, value, f"Invalid YY value: {value!r}")

        year = int(f"{self.year_prefix}{value}")
        if year < self.valid_years_from:
            return self.resolve_named(SCENARIO_BEFORE, year)
        if year > self.valid_years_to:
            return self.resolve_named(SCENARIO_AFTER, year)

        expected_name = self.year_file_pattern.format(year=year)
        path = self.content_dir / expected_name
        if path.exists() and path.stat().st_size > 0:
            return ResolvedContent(SCENARIO_VIDEO, year, expected_name, path, True, CONTENT_KIND_VIDEO)
        return self._missing(SCENARIO_VIDEO, year, expected_name, f"Content file not found or empty: {expected_name}")

    def resolve_named(self, scenario: str, year: int | None = None) -> ResolvedContent:
        if scenario == SCENARIO_IDLE:
            configured_name = str(self.content_config.get("idle", "idle.mp4"))
        elif scenario == SCENARIO_BEFORE:
            configured_name = str(self.content_config.get("beforeRange", "before_2016.mp4"))
        elif scenario == SCENARIO_AFTER:
            configured_name = str(self.content_config.get("afterRange", "after_2026.mp4"))
        else:
            return self._missing(scenario, year, scenario, f"Unknown content scenario: {scenario}")

        path = self._find_best_file(configured_name)
        if path and path.exists() and path.stat().st_size > 0:
            return ResolvedContent(scenario, year, configured_name, path, True, self._kind_for_path(path))

        expected = self.content_dir / configured_name
        return self._missing(scenario, year, configured_name, f"Content file not found or empty: {expected.name}")

    def _find_best_file(self, configured_name: str) -> Path | None:
        configured = self.content_dir / configured_name
        if configured.exists() and configured.stat().st_size > 0:
            return configured

        stem = configured.stem
        for extension in CONTENT_EXTENSIONS:
            candidate = self.content_dir / f"{stem}{extension}"
            if candidate.exists() and candidate.stat().st_size > 0:
                return candidate
        return None

    @staticmethod
    def _kind_for_path(path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix in VIDEO_EXTENSIONS:
            return CONTENT_KIND_VIDEO
        if suffix in IMAGE_EXTENSIONS:
            return CONTENT_KIND_IMAGE
        return CONTENT_KIND_MISSING

    @staticmethod
    def _missing(scenario: str, year: int | None, expected_name: str, error: str) -> ResolvedContent:
        return ResolvedContent(scenario, year, expected_name, None, False, CONTENT_KIND_MISSING, error)

    @staticmethod
    def _check_required_file(path: Path, display_name: str, result: ContentCheckResult) -> None:
        if not path.exists():
            result.missing.append(display_name)
            return
        if path.stat().st_size == 0:
            result.empty.append(display_name)
            return
        try:
            with path.open("rb") as file:
                file.read(1)
        except OSError:
            result.unreadable.append(display_name)
