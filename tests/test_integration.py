from __future__ import annotations

import os
from pathlib import Path

import pytest

from print_color_preflight.ghostscript import convert_pdf, find_ghostscript
from print_color_preflight.ink import analyze_ink_coverage
from print_color_preflight.models import ConversionOptions


@pytest.mark.integration
def test_real_ghostscript_conversion(rgb_pdf: Path, tmp_path: Path) -> None:
    profile_value = os.environ.get("PRINT_COLOR_TEST_CMYK_PROFILE")
    if not profile_value:
        pytest.skip("PRINT_COLOR_TEST_CMYK_PROFILE is not configured")
    try:
        executable = find_ghostscript()
    except RuntimeError as exc:
        pytest.skip(str(exc))
    output = tmp_path / "converted.pdf"
    result = convert_pdf(
        rgb_pdf,
        output,
        ConversionOptions(Path(profile_value)),
        executable=executable,
    )
    assert result.inventory.page_count == 1
    assert result.inventory.output_intents
    coverage = analyze_ink_coverage(output, executable=executable, dpi=12)
    assert coverage.page_count == 1
    assert coverage.sampled_pixels > 0
