# Contributing

Contributions are welcome through pull requests. Open an issue first for behavior changes that affect PDF semantics, Ghostscript policy, or public claims.

## Development setup

```console
python -m venv .venv
python -m pip install -e ".[dev]"
ruff format --check .
ruff check .
mypy src tests
pytest --cov
python -m build
```

Real conversion tests additionally require Ghostscript and a licensed-for-your-use CMYK profile supplied through `PRINT_COLOR_TEST_CMYK_PROFILE`.

Pull requests must explain the print problem and chosen tradeoff, include focused tests, update user-facing documentation when behavior changes, and avoid committing copyrighted or redistribution-restricted profiles and sample artwork.

The maintainer reviews contributions for correctness, security, scope, licensing, print semantics, test evidence, and maintainability. Passing automation does not guarantee acceptance or automatic merging.

