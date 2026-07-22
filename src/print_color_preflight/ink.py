from __future__ import annotations

import subprocess
import tempfile
from io import BytesIO
from pathlib import Path
from typing import cast

from PIL import Image

from .ghostscript import GhostscriptError, find_ghostscript
from .models import InkCoverageResult


def analyze_ink_coverage(
    pdf_path: Path,
    *,
    tac_limit_percent: float = 300.0,
    dpi: int = 72,
    executable: Path | None = None,
) -> InkCoverageResult:
    if not 1 <= dpi <= 600:
        raise ValueError("DPI must be between 1 and 600")
    if not 0 < tac_limit_percent <= 400:
        raise ValueError("TAC limit must be greater than 0 and no more than 400")
    source = pdf_path.expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"PDF does not exist: {source}")
    gs = find_ghostscript(executable)

    with tempfile.TemporaryDirectory(prefix="print-color-ink-") as temporary:
        pattern = Path(temporary) / "page-%04d.tiff"
        command = [
            str(gs),
            "-dSAFER",
            "-dBATCH",
            "-dNOPAUSE",
            "-dNOPROMPT",
            "-dPDFSTOPONERROR",
            "-sDEVICE=tiff32nc",
            f"-r{dpi}",
            f"-sOutputFile={pattern}",
            str(source),
        ]
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=600,
        )
        images = sorted(Path(temporary).glob("page-*.tiff"))
        if completed.returncode != 0 or not images:
            detail = (completed.stderr or completed.stdout).strip()
            raise GhostscriptError(f"Ink-coverage rendering failed: {detail}")

        sampled_pixels = 0
        pixels_over = 0
        maximum = 0.0
        for image_path in images:
            with (
                Image.open(BytesIO(image_path.read_bytes())) as image,
                image.convert("CMYK") as cmyk,
            ):
                pixels = list(cmyk.get_flattened_data())
                for value in pixels:
                    pixel = cast(tuple[int, int, int, int], value)
                    tac = sum(pixel) * 100.0 / 255.0
                    sampled_pixels += 1
                    maximum = max(maximum, tac)
                    if tac > tac_limit_percent:
                        pixels_over += 1

    percent_over = 100.0 * pixels_over / sampled_pixels if sampled_pixels else 0.0
    return InkCoverageResult(
        page_count=len(images),
        sampled_pixels=sampled_pixels,
        maximum_tac_percent=round(maximum, 2),
        pixels_over_limit=pixels_over,
        percent_over_limit=round(percent_over, 4),
        tac_limit_percent=tac_limit_percent,
        dpi=dpi,
    )
