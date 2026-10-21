from pathlib import Path
from subprocess import CompletedProcess
from typing import Any

import pytest
from PIL import Image

from print_color_preflight.ink import analyze_ink_coverage


def test_ink_closes_raster_storage_before_temporary_cleanup(
    monkeypatch: pytest.MonkeyPatch, rgb_pdf: Path, tmp_path: Path
) -> None:
    executable = tmp_path / "gs.exe"
    executable.write_bytes(b"")
    opened: list[Image.Image] = []
    original_open = Image.open

    def record_open(*args: Any, **kwargs: Any) -> Image.Image:
        image = original_open(*args, **kwargs)
        opened.append(image)
        return image

    def render(command: list[str], **kwargs: object) -> CompletedProcess[str]:
        output = Path(
            next(item for item in command if item.startswith("-sOutputFile="))
            .split("=", 1)[1]
            .replace("%04d", "0001")
        )
        with Image.new("CMYK", (2, 1)) as image:
            image.putdata([(255, 255, 255, 255), (0, 0, 0, 0)])
            image.save(output)
        return CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("print_color_preflight.ink.Image.open", record_open)
    monkeypatch.setattr("print_color_preflight.ink.subprocess.run", render)
    result = analyze_ink_coverage(rgb_pdf, executable=executable)
    assert result.sampled_pixels == 2
    assert result.maximum_tac_percent == 400
    assert len(opened) == 1
    for image in opened:
        with pytest.raises(ValueError, match="closed"):
            image.getpixel((0, 0))
