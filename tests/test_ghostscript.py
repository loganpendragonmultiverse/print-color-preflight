from pathlib import Path
from subprocess import CompletedProcess

import pytest

from print_color_preflight.ghostscript import (
    GhostscriptError,
    build_conversion_command,
    convert_pdf,
    find_ghostscript,
    ghostscript_version,
)
from print_color_preflight.models import ConversionOptions, RenderingIntent


def test_builds_explicit_safe_conversion_command(cmyk_profile: Path, tmp_path: Path) -> None:
    options = ConversionOptions(
        destination_profile=cmyk_profile,
        intent=RenderingIntent.RELATIVE,
        black_point_compensation=False,
        preserve_black=True,
    )
    command = build_conversion_command(
        Path("C:/tools/gs.exe"), Path("input.pdf"), tmp_path / "output.pdf", options
    )
    assert "-dSAFER" in command
    assert "-sColorConversionStrategy=CMYK" in command
    assert "-dRenderIntent=1" in command
    assert "-dBlackPtComp=0" in command
    assert "-dPreserveBlack=true" in command
    assert command[-1] == "input.pdf"


def test_refuses_to_overwrite(rgb_pdf: Path, cmyk_profile: Path, tmp_path: Path) -> None:
    output = tmp_path / "existing.pdf"
    output.write_bytes(b"keep me")
    with pytest.raises(GhostscriptError, match="already exists"):
        convert_pdf(rgb_pdf, output, ConversionOptions(cmyk_profile))
    assert output.read_bytes() == b"keep me"


def test_refuses_same_input_and_output(rgb_pdf: Path, cmyk_profile: Path) -> None:
    with pytest.raises(GhostscriptError, match="must be different"):
        convert_pdf(rgb_pdf, rgb_pdf, ConversionOptions(cmyk_profile))


def test_finds_configured_ghostscript(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    executable = tmp_path / "gs.exe"
    executable.write_bytes(b"")
    monkeypatch.setenv("PRINT_COLOR_GHOSTSCRIPT", str(executable))
    assert find_ghostscript() == executable.resolve()


def test_reports_missing_ghostscript(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("PRINT_COLOR_GHOSTSCRIPT", raising=False)
    monkeypatch.setattr("print_color_preflight.ghostscript.shutil.which", lambda _: None)
    with pytest.raises(GhostscriptError, match="was not found"):
        find_ghostscript()


def test_reads_ghostscript_version(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    executable = tmp_path / "gs.exe"
    executable.write_bytes(b"")
    monkeypatch.setattr(
        "print_color_preflight.ghostscript.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(args, 0, "GPL Ghostscript 10.0\n", ""),
    )
    assert ghostscript_version(executable) == "GPL Ghostscript 10.0"


def test_rejects_failed_version_check(monkeypatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    executable = tmp_path / "gs.exe"
    executable.write_bytes(b"")
    monkeypatch.setattr(
        "print_color_preflight.ghostscript.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(args, 1, "", "broken"),
    )
    with pytest.raises(GhostscriptError, match="broken"):
        ghostscript_version(executable)


def test_converts_then_postflights_before_promotion(
    monkeypatch: pytest.MonkeyPatch, rgb_pdf: Path, cmyk_profile: Path, tmp_path: Path
) -> None:
    executable = tmp_path / "gs.exe"
    executable.write_bytes(b"")
    output = tmp_path / "converted.pdf"

    def fake_run(command: list[str] | tuple[str, ...], **kwargs: object) -> CompletedProcess[str]:
        if "-version" in command:
            return CompletedProcess(command, 0, "GPL Ghostscript test\n", "")
        argument = next(item for item in command if item.startswith("-sOutputFile="))
        Path(argument.split("=", 1)[1]).write_bytes(rgb_pdf.read_bytes())
        return CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("print_color_preflight.ghostscript.subprocess.run", fake_run)
    result = convert_pdf(
        rgb_pdf,
        output,
        ConversionOptions(cmyk_profile),
        executable=executable,
    )
    assert output.is_file()
    assert result.inventory.output_intents
    assert result.output_sha256


def test_failed_conversion_does_not_create_output(
    monkeypatch: pytest.MonkeyPatch, rgb_pdf: Path, cmyk_profile: Path, tmp_path: Path
) -> None:
    executable = tmp_path / "gs.exe"
    executable.write_bytes(b"")
    output = tmp_path / "converted.pdf"
    responses = iter(
        [
            CompletedProcess([], 0, "GPL Ghostscript test\n", ""),
            CompletedProcess([], 1, "", "conversion error"),
        ]
    )
    monkeypatch.setattr(
        "print_color_preflight.ghostscript.subprocess.run", lambda *args, **kwargs: next(responses)
    )
    with pytest.raises(GhostscriptError, match="conversion error"):
        convert_pdf(
            rgb_pdf,
            output,
            ConversionOptions(cmyk_profile),
            executable=executable,
        )
    assert not output.exists()
