# Color workflow and interpretation

## The honest definition of “correct”

An RGB-to-CMYK result can be correct only relative to declared conditions: the source color meaning, the destination printer/paper/ink condition, a rendering objective, and a viewing or measurement method. A screen can display colors outside the destination print gamut, so some colors must change.

Print Color Preflight treats that change as a recorded decision rather than hiding it in a formula.

## Recommended workflow

1. Ask the printer which CMYK ICC profile and maximum total area coverage apply to the job.
2. Inspect the PDF. Resolve untagged RGB, unknown spot colors, unembedded fonts, and missing page geometry before conversion.
3. Review a `plan` for the chosen profile and rendering intent.
4. Convert to a new file. Never use the only copy of the artwork as the output path.
5. Run the postflight and TAC estimate.
6. Soft-proof with the same destination profile on a calibrated display when available.
7. Use a contract proof or press proof for color-critical work.
8. Validate the printer's required PDF/X flavor with its accepted preflight system.

## Rendering intents

- **Perceptual** compresses the source gamut to preserve overall visual relationships. It is the default here and is often useful for photographs.
- **Relative colorimetric** aims to preserve in-gamut colors and clips colors outside the destination gamut, adapting the paper white. It is often useful when exact in-gamut brand values matter.
- **Saturation** favors vividness over colorimetric accuracy and is commonly associated with charts or presentation graphics.
- **Absolute colorimetric** includes the destination paper color and is primarily a proofing choice, not a general conversion default.

The destination profile supplies the actual transforms. The same intent name can produce different results with different profiles.

## Black and total ink

Black preservation reduces avoidable four-color text and line art. It does not make every dark color K-only. Total area coverage is the sum of C, M, Y, and K at a location; the acceptable limit depends on the press and stock.

The `ink` command rasterizes a proof at the requested DPI and reports an estimate. RIP settings, overprints, screening, spot plates, and device-specific behavior can differ, so use the printer's separations for final approval.

## Untagged and special colors

`DeviceRGB` does not identify whether its numbers were intended as sRGB, Adobe RGB, Display P3, or another source. Detection is possible; recovery of the author's intent is not. Resolve the source space before conversion.

Spot colors may describe named inks, varnish, white ink, dielines, or other production plates. Their alternate CMYK appearance is not permission to convert them. Version 1.0.0 reports them for explicit human review.

