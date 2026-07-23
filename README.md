# Print Color Preflight

Print Color Preflight is a local, profile-aware PDF inspection and RGB-to-CMYK conversion tool. It identifies color spaces and print risks, requires an explicit destination CMYK ICC profile, performs conversion through Ghostscript, embeds the chosen output intent, postflights the result, and can estimate total area coverage (TAC).

The project is designed for designers, small publishers, print shops, and developers who need a repeatable conversion record instead of a profile-free RGB-to-CMYK formula.

> **Release status:** 1.0.0. PDF-first command-line release for Windows, macOS, and Linux.

## Why profiles are mandatory

CMYK values describe device ink amounts, not universal colors. A meaningful conversion needs both the source color meaning and the destination printing condition. Print Color Preflight therefore refuses to convert without a valid CMYK output or DeviceLink ICC profile.

It does not promise that an out-of-gamut screen color can be reproduced on paper. It records the selected compromise so the result can be proofed and measured.

## Features

- Inspect PDF page count, PDF version, device and ICC-based color spaces, output intents, spot colors, transparency, overprint, font embedding, and TrimBox coverage.
- Emit stable JSON for automation and a self-contained HTML review report.
- Inspect ICC headers and reject malformed or non-CMYK destination profiles.
- Preview a conversion plan before modifying a file.
- Convert through a separately installed Ghostscript executable using an explicit profile, rendering intent, black-point compensation, and black preservation policy.
- Work through a temporary output, parse the result, embed the chosen profile as the output intent, and move the file into place only after postflight succeeds.
- Rasterize CMYK separations to estimate maximum and over-limit total area coverage.
- Preserve input files by default and refuse to overwrite existing outputs without `--overwrite`.

## Three-minute start

Requirements:

- Python 3.10 or newer.
- Ghostscript for conversion and ink analysis. Inspection and planning do not require Ghostscript.
- A printer, paper, or print-standard CMYK ICC profile supplied by your printer or another authorized source.

```console
python -m pip install "print-color-preflight @ https://github.com/loganpendragonmultiverse/print-color-preflight/releases/download/v1.0.0/print_color_preflight-1.0.0-py3-none-any.whl"
print-color-preflight inspect artwork.pdf --html preflight.html
print-color-preflight plan artwork.pdf --profile printer.icc --intent perceptual
print-color-preflight convert artwork.pdf artwork-cmyk.pdf --profile printer.icc --json conversion.json
print-color-preflight ink artwork-cmyk.pdf --limit 300 --json ink.json
```

The project is not currently published on PyPI; the command above installs the verified GitHub release wheel. When running from a repository checkout, use `python -m pip install .` instead. Set `PRINT_COLOR_GHOSTSCRIPT` when Ghostscript is not on `PATH`.

## What the output means

- `inspect` reports detectable risks; it is not a substitute for a printer's full preflight system.
- `plan` shows the input findings, destination profile fingerprint, conversion choices, and decisions that need human review.
- `convert` creates a new PDF and records the exact engine, profile hash, options, output hash, and postflight.
- `ink` is a raster estimate at the requested DPI. It is useful for screening but is not a replacement for RIP separations or a press proof.

Exit code `0` means the requested operation completed. Operational or validation errors return `2`. `inspect --fail-on warning` and an ink result over the selected limit return `1`, which is useful in CI.

## Supported platforms

The Python package is platform-independent. Conversion depends on a compatible Ghostscript command (`gs`, `gswin64c.exe`, or `gswin32c.exe`). CI tests Python 3.10 and 3.14 on Windows, macOS, and Linux and exercises real Ghostscript conversion on Ubuntu.

## Privacy and security

All processing is local. The tool contains no analytics, accounts, network uploads, or profile downloads. Ghostscript is started with safer mode enabled, but PDFs and ICC profiles remain untrusted inputs; use current patched dependencies and avoid processing files from unknown sources on sensitive machines. See [SECURITY.md](SECURITY.md).

## Important limitations

- The tool does not choose a printer or paper profile for you.
- Untagged `DeviceRGB` can be detected but its intended source space cannot be recovered with certainty.
- Spot-color preservation is reported for manual review; 1.0.0 does not promise a spot-preserving process-color conversion.
- The embedded output intent documents the selected target. It does not by itself make a file PDF/X compliant. Validate required PDF/X conformance with a dedicated validator.
- Soft proofing depends on a calibrated display and controlled viewing conditions and is outside this CLI release.
- SVG and EPS are not accepted directly in 1.0.0. Export them to PDF without flattening important print semantics, then inspect the PDF.
- Physical correctness still requires a printer-approved profile and, for critical work, a contract or press proof.

## Documentation

- [Color workflow and interpretation](docs/COLOR-WORKFLOW.md)
- [CLI reference](docs/CLI.md)
- [Architecture and trust boundaries](docs/ARCHITECTURE.md)
- [Contributing](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## Maintenance

The project is maintained as a focused PDF color utility. Bug reports and narrowly scoped improvements are welcome. Broader publishing-suite features, cloud processing, bundled third-party profiles, and unsupported claims of visual equivalence are outside the current scope.

## License

Print Color Preflight is released under the MIT License. Ghostscript, printer profiles, and other external tools or data retain their own licenses and are not bundled with this project.

## More open-source projects

This project is part of the [Logan Pendragon Forge open-source collection](https://www.loganpendragonforge.com/open-source/). Browse the catalog for other released tools, source repositories, live demos, and downloads.
