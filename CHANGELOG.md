# Changelog

All notable changes are documented here. This project follows Semantic Versioning.

## [1.0.0] - 2026-07-21

### Added

- PDF preflight for device and ICC-based color spaces, output intents, spot colors, transparency, overprint, font embedding, and page TrimBox coverage.
- ICC header inspection and validation for CMYK output and DeviceLink profiles.
- Reviewable conversion planning with explicit rendering, black-point, and black-preservation decisions.
- Ghostscript-backed CMYK conversion through a temporary file with postflight validation and SHA-256 recording.
- Destination-profile embedding as an output intent without an unsupported claim of PDF/X certification.
- Raster total-area-coverage estimation with configurable DPI and ink limit.
- Terminal, JSON, and self-contained HTML reports.
- Cross-platform Python packaging, automated tests, security scanning, and real Ghostscript CI coverage.

[1.0.0]: https://github.com/loganpendragonmultiverse/print-color-preflight/releases/tag/v1.0.0

