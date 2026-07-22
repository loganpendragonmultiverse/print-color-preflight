from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

__version__ = "1.0.0"


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class RenderingIntent(str, Enum):
    PERCEPTUAL = "perceptual"
    RELATIVE = "relative-colorimetric"
    SATURATION = "saturation"
    ABSOLUTE = "absolute-colorimetric"

    @property
    def ghostscript_value(self) -> int:
        return {
            RenderingIntent.PERCEPTUAL: 0,
            RenderingIntent.RELATIVE: 1,
            RenderingIntent.SATURATION: 2,
            RenderingIntent.ABSOLUTE: 3,
        }[self]


@dataclass(frozen=True)
class Finding:
    code: str
    severity: Severity
    message: str
    page: int | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["severity"] = self.severity.value
        return value


@dataclass
class PdfInventory:
    path: Path
    page_count: int
    pdf_version: str
    encrypted: bool
    color_spaces: set[str] = field(default_factory=set)
    spot_colors: set[str] = field(default_factory=set)
    output_intents: list[str] = field(default_factory=list)
    font_count: int = 0
    unembedded_fonts: set[str] = field(default_factory=set)
    pages_without_trimbox: list[int] = field(default_factory=list)
    has_transparency: bool = False
    has_overprint: bool = False
    findings: list[Finding] = field(default_factory=list)

    @property
    def highest_severity(self) -> Severity:
        severities = {finding.severity for finding in self.findings}
        if Severity.ERROR in severities:
            return Severity.ERROR
        if Severity.WARNING in severities:
            return Severity.WARNING
        return Severity.INFO

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "tool_version": __version__,
            "path": str(self.path),
            "page_count": self.page_count,
            "pdf_version": self.pdf_version,
            "encrypted": self.encrypted,
            "color_spaces": sorted(self.color_spaces),
            "spot_colors": sorted(self.spot_colors),
            "output_intents": self.output_intents,
            "font_count": self.font_count,
            "unembedded_fonts": sorted(self.unembedded_fonts),
            "pages_without_trimbox": self.pages_without_trimbox,
            "has_transparency": self.has_transparency,
            "has_overprint": self.has_overprint,
            "status": self.highest_severity.value,
            "findings": [finding.to_dict() for finding in self.findings],
        }


@dataclass(frozen=True)
class ProfileInfo:
    path: Path
    description: str
    device_class: str
    color_space: str
    connection_space: str
    size_bytes: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["path"] = str(self.path)
        return data


@dataclass(frozen=True)
class ConversionOptions:
    destination_profile: Path
    intent: RenderingIntent = RenderingIntent.PERCEPTUAL
    black_point_compensation: bool = True
    preserve_black: bool = True
    compatibility_level: str = "1.6"


@dataclass(frozen=True)
class ConversionResult:
    input_path: Path
    output_path: Path
    profile: ProfileInfo
    options: ConversionOptions
    ghostscript_version: str
    command: tuple[str, ...]
    output_sha256: str
    inventory: PdfInventory

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "tool_version": __version__,
            "input_path": str(self.input_path),
            "output_path": str(self.output_path),
            "profile": self.profile.to_dict(),
            "options": {
                "destination_profile": str(self.options.destination_profile),
                "intent": self.options.intent.value,
                "black_point_compensation": self.options.black_point_compensation,
                "preserve_black": self.options.preserve_black,
                "compatibility_level": self.options.compatibility_level,
            },
            "ghostscript_version": self.ghostscript_version,
            "command": list(self.command),
            "output_sha256": self.output_sha256,
            "postflight": self.inventory.to_dict(),
        }


@dataclass(frozen=True)
class InkCoverageResult:
    page_count: int
    sampled_pixels: int
    maximum_tac_percent: float
    pixels_over_limit: int
    percent_over_limit: float
    tac_limit_percent: float
    dpi: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
