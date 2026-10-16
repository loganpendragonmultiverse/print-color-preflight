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
