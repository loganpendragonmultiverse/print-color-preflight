# CLI reference

## `inspect`

```console
print-color-preflight inspect INPUT.pdf [--password VALUE] [--json FILE] [--html FILE] [--fail-on never|warning|error]
```

Inspects without rewriting the PDF. The default exit policy fails only on operational errors. Use `--fail-on warning` in strict automated preflight.

## `profile`

```console
print-color-preflight profile PROFILE.icc [--require-cmyk-output] [--json FILE]
```

Reports the profile class, device color space, profile connection space, byte size, description when readable, and SHA-256 fingerprint.

## `plan`

```console
print-color-preflight plan INPUT.pdf --profile DESTINATION.icc [--intent INTENT]
```

Validates the input and profile and prints the proposed policy without conversion. Add `--no-black-point-compensation` or `--no-preserve-black` only when the print workflow requires those choices.

## `convert`

```console
print-color-preflight convert INPUT.pdf OUTPUT.pdf --profile DESTINATION.icc [OPTIONS]
```

Important options:

- `--intent perceptual|relative-colorimetric|saturation|absolute-colorimetric`
- `--no-black-point-compensation`
- `--no-preserve-black`
- `--ghostscript PATH`
- `--overwrite`
- `--json FILE`
- `--html FILE`

The output is created indirectly and promoted only after it parses and contains at least one page. The JSON record includes the destination profile and output SHA-256 hashes.

## `ink`

```console
print-color-preflight ink INPUT.pdf [--limit 300] [--dpi 72] [--json FILE]
```

Returns `1` when any sampled pixel exceeds the selected limit. Higher DPI increases runtime and memory use.

## `doctor`

```console
print-color-preflight doctor [--ghostscript PATH]
```

Shows the executable and version that conversion commands will use. `PRINT_COLOR_GHOSTSCRIPT` can supply the path globally.

