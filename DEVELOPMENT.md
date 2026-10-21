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

- Current version: **2.0.0**.
- Maintainer: Logan Pendragon Multiverse.
- Repository: `https://github.com/loganpendragonmultiverse/print-color-preflight`.
- License: MIT for this project. External executables and profiles retain their own licenses.


## Finding provenance

Keep aggregate finding codes and severity compatible. Attach stable page,
object and resource-path evidence; traverse shared resources per page using
path-local cycle guards. Object references are file-local, not persistent IDs.
Static resource association must not be presented as proof of rendered use.
No PDF/X or physical-color certification is introduced.


## Version 2.0 safety and compatibility

Python 3.11+ and Pillow 13 are required; Python 3.10 support is removed. CI keeps
all six Linux/Windows/macOS combinations, now Python 3.11 and 3.14, the 85% branch
coverage threshold, dependency audit, CodeQL and real Ghostscript integration.
Only the three required Python 3.10 test names migrate to Python 3.11; other
branch protections and application bindings remain unchanged.

Conversion stages on the output filesystem, fingerprints input/profile bytes,
parses postflight before publication, and publishes new files exclusively.
`--overwrite` applies only to an existing regular destination that remains
unchanged during conversion. Links, source/profile aliases and observed raced
writers are refused. Reports must be new distinct files, including when conversion
uses `--overwrite`. Ordinary collision protection is not a hostile-filesystem sandbox.

ICC inspection validates the header and tag-table bounds, with a 16 MiB limit.
A header-only plan does not establish a usable color transform; the actual selected
profile is exercised by Ghostscript conversion and must still be licensed and
appropriate for the printer. No ICC profile is bundled. Native acceptance uses
installed Ghostscript and its separately licensed default CMYK profile, not the
synthetic header fixtures used by unit tests.

TAC screening rejects invalid/boolean controls and predicts raster pixel budgets
before invoking Ghostscript. Decoded proof rasters are checked again before color
conversion. Limits are 40 million pixels per page and 200 million per document;
lower DPI or split a larger proof. Pixel traversal avoids a document-sized tuple
or list. TAC remains a sampled screening estimate, not press or PDF/X certification.

Installed-package tests use isolated pip targets and an existing interpreter so
read-only/noexec temporary filesystems need no executable-policy change. Full
source assertions, real Ghostscript behavior and installed import provenance remain
required. Native CI also invokes the generated console entrypoint directly.

Pillow 13 has a conditional upstream Arrow-export advisory with no fixed release
listed in this assessment. This application does not export Arrow; the final
source-specific applicability assessment is independently reviewed. A successful
dependency audit is not a blanket zero-known-vulnerabilities claim.

## Current external runtime qualification

Use a current upstream or vendor-maintained patched Ghostscript build. Version
2.0.0 Linux qualification exercises upstream 10.08.0 from a verified official
source build; the historical host 9.54 run establishes functional behavior only.
The external engine and ICC profiles are not bundled. See [Ghostscript runtime
qualification](docs/GHOSTSCRIPT.md) for exact scope, provenance and licensing.

## Release artifact closure

The tag workflow pins maintained action commits, checks the stable tag against
the package version before building, runs the full quality and dependency-audit
checks, validates wheel/sdist metadata and writes SHA256SUMS over those exact
two payloads. Normal PR/main native matrix and independent installed-artifact
review remain required before a public release. It does not publish a GitHub
release automatically.
