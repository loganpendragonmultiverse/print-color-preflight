from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from subprocess import CompletedProcess

import pikepdf
import pytest
from PIL import Image

from print_color_preflight import ghostscript, ink
from print_color_preflight.cli import main
from print_color_preflight.models import ConversionOptions
from print_color_preflight.profiles import ProfileError, inspect_profile
from print_color_preflight.report import write_json_report


def fake_conversion(
    monkeypatch: pytest.MonkeyPatch, source: Path, tmp_path: Path, change: Callable[[], object]
) -> Path:
    executable = tmp_path / "gs-stub"
    executable.write_bytes(b"unit test stub")
    original = source.read_bytes()

    def run(command: list[str] | tuple[str, ...], **kwargs: object) -> CompletedProcess[str]:
        if "-version" in command:
            return CompletedProcess(command, 0, "Unit test Ghostscript\n", "")
        output = next(x.split("=", 1)[1] for x in command if x.startswith("-sOutputFile="))
        Path(output).write_bytes(original)
        change()
        return CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("print_color_preflight.ghostscript.subprocess.run", run)
    return executable


@pytest.mark.parametrize("overwrite", [False, True])
def test_conversion_does_not_replace_raced_new_destination(
    monkeypatch: pytest.MonkeyPatch,
    rgb_pdf: Path,
    cmyk_profile: Path,
    tmp_path: Path,
    overwrite: bool,
) -> None:
    output = tmp_path / "output.pdf"
    executable = fake_conversion(
        monkeypatch, rgb_pdf, tmp_path, lambda: output.write_bytes(b"other writer")
    )
    with pytest.raises(FileExistsError):
        ghostscript.convert_pdf(
            rgb_pdf,
            output,
            ConversionOptions(cmyk_profile),
            executable=executable,
            overwrite=overwrite,
        )
    assert output.read_bytes() == b"other writer"


def test_explicit_overwrite_preserves_concurrently_changed_destination(
    monkeypatch: pytest.MonkeyPatch, rgb_pdf: Path, cmyk_profile: Path, tmp_path: Path
) -> None:
    output = tmp_path / "output.pdf"
    output.write_bytes(b"original destination")
    executable = fake_conversion(
        monkeypatch, rgb_pdf, tmp_path, lambda: output.write_bytes(b"other writer")
    )
    with pytest.raises(ghostscript.GhostscriptError, match="Output changed"):
        ghostscript.convert_pdf(
            rgb_pdf, output, ConversionOptions(cmyk_profile), executable=executable, overwrite=True
        )
    assert output.read_bytes() == b"other writer"


@pytest.mark.parametrize("which", ["source", "profile"])
def test_changed_conversion_inputs_refuse_publication(
    monkeypatch: pytest.MonkeyPatch, rgb_pdf: Path, cmyk_profile: Path, tmp_path: Path, which: str
) -> None:
    output = tmp_path / "output.pdf"
    changed = rgb_pdf if which == "source" else cmyk_profile
    executable = fake_conversion(
        monkeypatch,
        rgb_pdf,
        tmp_path,
        lambda: changed.write_bytes(changed.read_bytes() + b"changed"),
    )
    with pytest.raises(ghostscript.GhostscriptError, match="changed"):
        ghostscript.convert_pdf(
            rgb_pdf, output, ConversionOptions(cmyk_profile), executable=executable
        )
    assert not output.exists()


def test_report_aliases_refused_before_conversion(
    rgb_pdf: Path, cmyk_profile: Path, tmp_path: Path
) -> None:
    output = tmp_path / "output.pdf"
    before = rgb_pdf.read_bytes()
    assert main(["inspect", str(rgb_pdf), "--json", str(rgb_pdf)]) == 2
    assert (
        main(
            [
                "convert",
                str(rgb_pdf),
                str(output),
                "--profile",
                str(cmyk_profile),
                "--json",
                str(output),
            ]
        )
        == 2
    )
    assert main(["inspect", str(rgb_pdf), "--json", str(output), "--html", str(output)]) == 2
    assert rgb_pdf.read_bytes() == before and not output.exists()


def test_report_collision_and_dangling_link_preserved(tmp_path: Path) -> None:
    output = tmp_path / "report.json"
    output.write_text("keep")
    with pytest.raises(ValueError, match="already exists"):
        write_json_report({}, output)
    assert output.read_text() == "keep"
    link = tmp_path / "link.json"
    target = tmp_path / "absent"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    with pytest.raises(ValueError):
        write_json_report({}, link)
    assert link.is_symlink() and not target.exists()


def test_hardlinked_and_symlinked_conversion_outputs_preserved(
    rgb_pdf: Path, cmyk_profile: Path, tmp_path: Path
) -> None:
    output = tmp_path / "same.pdf"
    os.link(rgb_pdf, output)
    with pytest.raises(ghostscript.GhostscriptError, match="different"):
        ghostscript.convert_pdf(rgb_pdf, output, ConversionOptions(cmyk_profile), overwrite=True)
    link = tmp_path / "linked.pdf"
    try:
        link.symlink_to(tmp_path / "missing")
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    with pytest.raises(ghostscript.GhostscriptError, match="symbolic link"):
        ghostscript.convert_pdf(rgb_pdf, link, ConversionOptions(cmyk_profile), overwrite=True)
    assert link.is_symlink() and not (tmp_path / "missing").exists()


def test_profile_tag_table_bounds(cmyk_profile: Path) -> None:
    data = bytearray(cmyk_profile.read_bytes())
    data[128:132] = (1).to_bytes(4, "big")
    cmyk_profile.write_bytes(data)
    with pytest.raises(ProfileError, match="tag table"):
        inspect_profile(cmyk_profile)


@pytest.mark.parametrize("value", [True, None, "72", 1.5])
def test_ink_integer_dpi_required(rgb_pdf: Path, value: object) -> None:
    with pytest.raises(ValueError, match="DPI"):
        ink.analyze_ink_coverage(rgb_pdf, dpi=value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [True, None, "300", float("nan"), float("inf")])
def test_ink_typed_finite_tac_required(rgb_pdf: Path, value: object) -> None:
    with pytest.raises(ValueError, match="TAC"):
        ink.analyze_ink_coverage(rgb_pdf, tac_limit_percent=value)  # type: ignore[arg-type]


def test_huge_geometry_refused_before_ghostscript(
    rgb_pdf: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pikepdf.Pdf.open(rgb_pdf, allow_overwriting_input=True) as pdf:
        pdf.pages[0].obj["/MediaBox"] = pikepdf.Array([0, 0, 1_000_000, 1_000_000])
        pdf.save(rgb_pdf)

    def forbidden(*args: object) -> Path:
        raise AssertionError("must refuse before external rendering")

    monkeypatch.setattr(ink, "find_ghostscript", forbidden)
    with pytest.raises(ValueError, match="pixel safety"):
        ink.analyze_ink_coverage(rgb_pdf)


def test_rendered_pixel_budget_precedes_conversion(
    rgb_pdf: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    executable = tmp_path / "gs-stub"
    executable.write_bytes(b"unit test stub")
    monkeypatch.setattr(ink, "MAX_PAGE_PIXELS", 10)

    def run(command: list[str], **kwargs: object) -> CompletedProcess[str]:
        output = next(x.split("=", 1)[1] for x in command if x.startswith("-sOutputFile="))
        Image.new("CMYK", (5, 5)).save(output.replace("%04d", "0001"))
        return CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("print_color_preflight.ink.subprocess.run", run)
    with pytest.raises(ValueError, match="pixel safety"):
        ink.analyze_ink_coverage(rgb_pdf, dpi=1, executable=executable)


def test_explicit_missing_ghostscript_does_not_fallback(tmp_path: Path) -> None:
    with pytest.raises(ghostscript.GhostscriptError):
        ghostscript.find_ghostscript(tmp_path / "missing-gs")
