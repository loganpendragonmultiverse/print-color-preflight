# Print Color Preflight Development

## Release contract

Version 1.0.0 is a PDF-first local CLI. It exists to make a conversion explicit, reviewable, and repeatable—not to invent a universal CMYK space or replace the printer's proofing process.

The initial release is complete when it can:

1. inventory meaningful PDF color and print-production risks;
2. validate a user-selected CMYK destination profile;
3. expose the conversion choices before execution;
4. execute through a separately installed Ghostscript binary without overwriting the input;
5. embed and fingerprint the selected output intent;
6. parse and report on the result before promoting it to the requested path;
7. estimate TAC for screening; and
8. pass unit, integration, packaging, static-analysis, and dependency checks.

## Deliberate boundaries

- No network upload, account, analytics, or cloud service.
- No bundled ICC profiles. Profile licensing and printer selection remain with the user.
- No claim that an embedded output intent alone establishes PDF/X conformance.
- No automatic spot-color destruction or promise that spot colors survive every Ghostscript workflow.
- No direct SVG or EPS handling in 1.0.0. PDF is the normalized input boundary.
- No claim that soft proofing is accurate on an uncalibrated display.
- No automatic “best” rendering intent. The default is perceptual, but the selected choice is visible and overridable.

## Architecture decisions

- Python provides a small cross-platform CLI and packaging surface.
- pikepdf performs lossless PDF-object inspection and output-intent embedding.
- Pillow reads ICC descriptions and CMYK proof rasters.
- Ghostscript performs the actual color-managed conversion and separation rendering. It remains a separately installed external program with its own license.
- Conversion uses a temporary directory and moves the file only after postflight. Existing destinations require explicit `--overwrite`.

## Verification commands

```console
python -m pip install -e ".[dev]"
ruff format --check .
ruff check .
mypy src tests
pytest --cov --cov-report=term-missing
python -m build
python -m pip_audit
```

The integration test runs when both Ghostscript and `PRINT_COLOR_TEST_CMYK_PROFILE` are available.

## Release record

- Current version: **1.0.0**.
- Maintainer: Logan Pendragon Multiverse.
- Repository: `https://github.com/loganpendragonmultiverse/print-color-preflight`.
- License: MIT for this project. External executables and profiles retain their own licenses.

