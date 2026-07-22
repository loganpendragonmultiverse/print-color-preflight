from __future__ import annotations

from pathlib import Path

import pikepdf
import pytest


@pytest.fixture
def rgb_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "rgb.pdf"
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page(page_size=(144, 144))
    page.obj["/Contents"] = pdf.make_stream(b"1 0 0 rg 10 10 100 100 re f\n")
    pdf.save(path)
    return path


@pytest.fixture
def cmyk_profile(tmp_path: Path) -> Path:
    path = tmp_path / "test-cmyk.icc"
    data = bytearray(132)
    data[0:4] = len(data).to_bytes(4, "big")
    data[8:12] = b"\x04\x30\x00\x00"
    data[12:16] = b"prtr"
    data[16:20] = b"CMYK"
    data[20:24] = b"Lab "
    data[36:40] = b"acsp"
    data[128:132] = (0).to_bytes(4, "big")
    path.write_bytes(data)
    return path
