from __future__ import annotations

import math
import subprocess
import tempfile
from contextlib import closing
from pathlib import Path
from typing import cast

import pikepdf
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
    if type(dpi) is not int or not 1 <= dpi <= 600:
        raise ValueError("DPI must be between 1 and 600")
    if type(tac_limit_percent) not in {int, float} or not 0 < tac_limit_percent <= 400:
        raise ValueError("TAC limit must be greater than 0 and no more than 400")
    source = pdf_path.expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"PDF does not exist: {source}")
    _check_raster_budget(source, dpi)
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
            with closing(Image.open(image_path)) as image:
                pixels_on_page = image.width * image.height
                if (
                    pixels_on_page > MAX_PAGE_PIXELS
                    or sampled_pixels + pixels_on_page > MAX_TOTAL_PIXELS
                ):
                    raise ValueError("Rendered raster exceeds the pixel safety budget")
                with closing(image.convert("CMYK")) as cmyk:
                    pixels = cmyk.load()
                    if pixels is None:
                        raise ValueError("Rendered raster has no readable pixels")
                    for y in range(cmyk.height):
                        for x in range(cmyk.width):
                            pixel = cast(tuple[int, int, int, int], pixels[x, y])
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


MAX_PAGE_PIXELS = 40_000_000
MAX_TOTAL_PIXELS = 200_000_000


def _check_raster_budget(path: Path, dpi: int) -> None:
    total = 0
    try:
        with pikepdf.Pdf.open(path) as pdf:
            for page in pdf.pages:
                box = [float(value) for value in page.mediabox]
                unit = float(page.obj.get("/UserUnit", 1))
                if (
                    len(box) != 4
                    or not all(math.isfinite(value) for value in (*box, unit))
                    or unit <= 0
                ):
                    raise ValueError("Invalid page geometry for bounded raster proof")
                width = math.ceil(abs(box[2] - box[0]) * unit * dpi / 72)
                height = math.ceil(abs(box[3] - box[1]) * unit * dpi / 72)
                pixels = width * height
                total += pixels
                if pixels < 1 or pixels > MAX_PAGE_PIXELS or total > MAX_TOTAL_PIXELS:
                    raise ValueError(
                        "PDF raster proof exceeds the pixel safety budget; "
                        "lower DPI or split the document"
                    )
    except (pikepdf.PdfError, OverflowError) as exc:
        raise ValueError(f"Cannot validate raster geometry: {exc}") from exc
