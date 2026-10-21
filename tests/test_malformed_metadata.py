from pathlib import Path
from typing import Any

import pikepdf
import pytest

from print_color_preflight.cli import main
from print_color_preflight.pdf import PdfInspectionError, inspect_pdf


@pytest.mark.parametrize(
    "kind",
    [
        "intents-scalar",
        "intent-entry",
        "descendant-entry",
        "icc-entry",
        "resources-scalar",
        "font-entry",
        "descriptor-scalar",
        "state-entry",
        "xobject-entry",
        "group-scalar",
        "devicen-scalar",
        "devicen-entry",
        "devicen-empty",
        "separation-scalar",
    ],
)
def test_malformed_metadata_is_actionable(
    kind: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "malformed.pdf"
    with pikepdf.Pdf.new() as pdf:
        page = pdf.add_blank_page()
        resources = pikepdf.Dictionary()
        page.obj["/Resources"] = resources
        if kind == "intents-scalar":
            pdf.Root["/OutputIntents"] = 42
        elif kind == "intent-entry":
            pdf.Root["/OutputIntents"] = pikepdf.Array([42])
        elif kind == "descendant-entry":
            resources["/Font"] = pikepdf.Dictionary(
                F=pikepdf.Dictionary(DescendantFonts=pikepdf.Array([42]))
            )
        elif kind == "icc-entry":
            resources["/ColorSpace"] = pikepdf.Dictionary(
                Bad=pikepdf.Array([pikepdf.Name.ICCBased, 42])
            )
        elif kind == "resources-scalar":
            page.obj["/Resources"] = 42
        elif kind == "font-entry":
            resources["/Font"] = pikepdf.Dictionary(F=42)
        elif kind == "descriptor-scalar":
            resources["/Font"] = pikepdf.Dictionary(F=pikepdf.Dictionary(FontDescriptor=42))
        elif kind == "state-entry":
            resources["/ExtGState"] = pikepdf.Dictionary(Bad=42)
        elif kind == "xobject-entry":
            resources["/XObject"] = pikepdf.Dictionary(Bad=42)
        elif kind.startswith("devicen") or kind == "separation-scalar":
            tint = pdf.make_stream(b"{ dup dup }")
            names: Any
            if kind == "devicen-scalar":
                names = 42
            elif kind == "devicen-entry":
                names = pikepdf.Array([42])
            elif kind == "devicen-empty":
                names = pikepdf.Array([])
            else:
                names = 42
            family = (
                pikepdf.Name.Separation if kind == "separation-scalar" else pikepdf.Name.DeviceN
            )
            resources["/ColorSpace"] = pikepdf.Dictionary(
                Bad=pikepdf.Array([family, names, pikepdf.Name.DeviceCMYK, tint])
            )
        else:
            form = pdf.make_stream(b"")
            form["/Subtype"] = pikepdf.Name.Form
            form["/Group"] = 42
            resources["/XObject"] = pikepdf.Dictionary(Bad=form)
        pdf.save(path)
    before = path.read_bytes()
    report = tmp_path / "report.json"
    with pytest.raises(PdfInspectionError, match="PDF"):
        inspect_pdf(path)
    assert main(["inspect", str(path), "--json", str(report)]) == 2
    error = capsys.readouterr().err
    assert "error:" in error and "Traceback" not in error
    assert not report.exists()
    assert path.read_bytes() == before
