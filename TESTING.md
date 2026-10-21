# Testing

Install with `python -m pip install -e ".[dev]"`, then run:

```console
ruff format --check .
ruff check .
mypy src tests
pytest --cov --cov-report=term-missing
python -m build
python -m pip_audit
```

Synthetic PDFs cover inherited/shared resources, recursive Form resources,
repeated XObjects, direct resource dictionaries, resource-less Forms, self/mutual
Form cycles, RGB and spot colors, unembedded fonts, transparency,
malformed inputs, encryption and deterministic file-local references.
Source PDFs remain unchanged by inspection.

## Ghostscript integration

The required CI integration job installs Ghostscript and locates its packaged
`default_cmyk.icc`. Run `pytest -m integration -v` with Ghostscript on PATH and
`PRINT_COLOR_TEST_CMYK_PROFILE` pointing to that licensed, installed profile.
The generated RGB PDF is synthetic. The minimal synthetic ICC header in unit
tests only tests validation and is never used as a conversion profile.
Ghostscript and its profiles retain their own licenses and are not bundled.
A skipped local integration test is not evidence of conversion acceptance;
the protected integration check must pass before release.

Verify installed wheel and extracted source examples, metadata and bundled
documentation before publication. Provenance does not establish PDF/X
conformance or physical-color certification.


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

For exact tagged-artifact acceptance, set `PRINT_COLOR_TEST_ARTIFACT_DIRECTORY`
to the directory containing exactly the reviewed wheel and sdist. The full suite
then installs those two artifacts for every existing native workflow/provenance
assertion; it does not rebuild a different package from the source harness.
With that variable absent, CI's original source-build acceptance remains active.
The required native integration job also runs the actual installed wheel console.

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
