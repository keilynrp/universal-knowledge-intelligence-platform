"""Format-neutral section payload (unify-report-format-coverage, phase 1).

A section's data is collected once into a `SectionData` of these blocks; each
per-format renderer turns the blocks into HTML, Excel or PPTX. Four primitives
cover every existing section (verified against the current HTML output):

  * StatGrid — labelled KPI cards.
  * Table    — columns + rows, optionally with one column drawn as a bar.
  * Narrative — a heading and paragraphs of prose.
  * Meter    — a single labelled percentage bar.

All types are frozen: a payload is data, not a mutable buffer, so a renderer
cannot alter what a later renderer sees.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union


@dataclass(frozen=True)
class StatItem:
    label: str
    value: str
    sub: str | None = None


@dataclass(frozen=True)
class StatGrid:
    items: tuple[StatItem, ...]


@dataclass(frozen=True)
class Table:
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    # Index of a column to draw as a proportional bar (e.g. a share %). Optional.
    bar_column: int | None = None

    def __post_init__(self) -> None:
        width = len(self.columns)
        for row in self.rows:
            if len(row) != width:
                raise ValueError(
                    f"row {row!r} has {len(row)} cells, expected {width}"
                )
        if self.bar_column is not None and not (0 <= self.bar_column < width):
            raise ValueError(
                f"bar_column {self.bar_column} out of range for {width} columns"
            )


@dataclass(frozen=True)
class Narrative:
    heading: str
    paragraphs: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.heading.strip():
            raise ValueError("Narrative requires a non-empty heading")


@dataclass(frozen=True)
class Meter:
    label: str
    pct: float

    def __post_init__(self) -> None:
        if not (0 <= self.pct <= 100):
            raise ValueError(f"Meter pct {self.pct} out of range [0, 100]")


Block = Union[StatGrid, Table, Narrative, Meter]


@dataclass(frozen=True)
class SectionData:
    key: str
    title: str
    blocks: tuple[Block, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("SectionData requires a non-empty key")
        if not self.title.strip():
            raise ValueError("SectionData requires a non-empty title")
