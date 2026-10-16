from __future__ import annotations

import json
import os
import subprocess
import sys
import venv
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


@pytest.mark.integration
def test_installed_release_packages_with_licensed_profile(
    rgb_pdf: Path,
    tmp_path: Path,
) -> None:
    """Exercise README workflows from both built distributions with the installed profile."""
    profile_value = os.environ.get("PRINT_COLOR_TEST_CMYK_PROFILE")
    if not profile_value:
        pytest.skip("PRINT_COLOR_TEST_CMYK_PROFILE is not configured")
    find_ghostscript()
    root = Path(__file__).resolve().parents[1]
    artifacts = tmp_path / "artifacts"
    subprocess.run(
        [sys.executable, "-m", "build", "--outdir", str(artifacts), str(root)],
        check=True,
        capture_output=True,
        text=True,
    )
    for index, artifact in enumerate(sorted(artifacts.iterdir())):
        environment = tmp_path / f"installed-{index}"
        venv.EnvBuilder(with_pip=True, system_site_packages=True).create(environment)
        python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run(
            [str(python), "-m", "pip", "install", "--no-deps", "--ignore-installed", str(artifact)],
            check=True,
            capture_output=True,
            text=True,
        )
        location = subprocess.run(
            [
                str(python),
                "-c",
                "import print_color_preflight; print(print_color_preflight.__file__)",
            ],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert Path(location).is_relative_to(environment)
        prefix = [str(python), "-m", "print_color_preflight"]
        version = subprocess.run(
            [*prefix, "--version"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        assert "1.1.0" in version
        inspection = tmp_path / f"inspection-{index}.json"
        converted = tmp_path / f"converted-{index}.pdf"
        conversion = tmp_path / f"conversion-{index}.json"
        ink = tmp_path / f"ink-{index}.json"
        commands = [
            [
                "inspect",
                str(rgb_pdf),
                "--html",
                str(tmp_path / f"review-{index}.html"),
                "--json",
                str(inspection),
            ],
            ["plan", str(rgb_pdf), "--profile", profile_value, "--intent", "perceptual"],
            [
                "convert",
                str(rgb_pdf),
                str(converted),
                "--profile",
                profile_value,
                "--json",
                str(conversion),
            ],
            ["ink", str(converted), "--limit", "300", "--json", str(ink)],
        ]
        for args in commands:
            subprocess.run(
                [*prefix, *args],
                cwd=tmp_path,
                check=True,
                capture_output=True,
                text=True,
            )
        data = json.loads(inspection.read_text())
        finding = next(row for row in data["findings"] if row["code"] == "untagged-rgb")
        assert finding["details"]["references"][0]["page"] == 1
        assert json.loads(conversion.read_text())["postflight"]["output_intents"]
        assert json.loads(ink.read_text())["page_count"] == 1
