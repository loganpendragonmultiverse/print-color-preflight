from pathlib import Path
from subprocess import CompletedProcess

import pytest
from PIL import Image

from print_color_preflight.ghostscript import GhostscriptError
from print_color_preflight.ink import analyze_ink_coverage


def test_estimates_total_area_coverage(monkeypatch, rgb_pdf: Path, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    executable = tmp_path / "gs.exe"
    executable.write_bytes(b"")

    def fake_run(command: list[str], **kwargs: object) -> CompletedProcess[str]:
        output_argument = next(item for item in command if item.startswith("-sOutputFile="))
        output = Path(output_argument.split("=", 1)[1].replace("%04d", "0001"))
        image = Image.new("CMYK", (2, 1))
        image.putdata([(255, 255, 255, 255), (0, 0, 0, 0)])
        image.save(output)
        return CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("print_color_preflight.ink.subprocess.run", fake_run)
    result = analyze_ink_coverage(rgb_pdf, tac_limit_percent=300, dpi=72, executable=executable)
    assert result.maximum_tac_percent == 400
    assert result.pixels_over_limit == 1
    assert result.percent_over_limit == 50


@pytest.mark.parametrize("dpi", [0, 601])
def test_rejects_invalid_dpi(rgb_pdf: Path, dpi: int) -> None:
    with pytest.raises(ValueError, match="DPI"):
        analyze_ink_coverage(rgb_pdf, dpi=dpi)


@pytest.mark.parametrize("limit", [0, 401])
def test_rejects_invalid_tac_limit(rgb_pdf: Path, limit: float) -> None:
    with pytest.raises(ValueError, match="TAC"):
        analyze_ink_coverage(rgb_pdf, tac_limit_percent=limit)


def test_reports_failed_ink_render(monkeypatch, rgb_pdf: Path, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    executable = tmp_path / "gs.exe"
    executable.write_bytes(b"")
    monkeypatch.setattr(
        "print_color_preflight.ink.subprocess.run",
        lambda *args, **kwargs: CompletedProcess(args, 1, "", "render error"),
    )
    with pytest.raises(GhostscriptError, match="render error"):
        analyze_ink_coverage(rgb_pdf, executable=executable)
