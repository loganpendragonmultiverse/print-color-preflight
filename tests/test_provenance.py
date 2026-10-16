from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pikepdf
import pytest

from print_color_preflight.pdf import inspect_pdf


def refs(inventory: Any, code: str) -> list[dict[str, Any]]:
    return next(
        finding.details["references"] for finding in inventory.findings if finding.code == code
    )


def test_shared_inherited_recursive_resources_and_repeated_xobjects(tmp_path: Path) -> None:
    path = tmp_path / "shared.pdf"
    pdf = pikepdf.Pdf.new()
    pages = [pdf.add_blank_page() for _ in range(2)]
    font = pdf.make_indirect(
        pikepdf.Dictionary(
            Type=pikepdf.Name.Font,
            Subtype=pikepdf.Name.Type1,
            BaseFont=pikepdf.Name.Helvetica,
        )
    )
    tint = pdf.make_stream(b"{ dup dup }", FunctionType=4, Domain=[0, 1], Range=[0, 1] * 4)
    resources = pdf.make_indirect(
        pikepdf.Dictionary(
            Font=pikepdf.Dictionary(F1=font),
            ColorSpace=pikepdf.Dictionary(
                RGB=pikepdf.Name.DeviceRGB,
                Spot=pikepdf.Array(
                    [
                        pikepdf.Name.Separation,
                        pikepdf.Name("/Brand"),
                        pikepdf.Name.DeviceCMYK,
                        tint,
                    ]
                ),
            ),
            ExtGState=pikepdf.Dictionary(
                Fade=pdf.make_indirect(pikepdf.Dictionary(ca=0.5, OP=True))
            ),
        )
    )
    form = pdf.make_stream(b"1 0 0 rg 0 0 10 10 re f /Self Do")
    form["/Subtype"] = pikepdf.Name.Form
    form["/BBox"] = pikepdf.Array([0, 0, 10, 10])
    form["/Resources"] = resources
    form["/Group"] = pikepdf.Dictionary(S=pikepdf.Name.Transparency)
    resources["/XObject"] = pikepdf.Dictionary(Fm=form, Alias=form, Self=form)
    pages[0].obj["/Parent"]["/Resources"] = resources
    for page in pages:
        del page.obj["/Resources"]
        page.obj["/Contents"] = pdf.make_stream(b"/Fm Do /Fm Do /Alias Do")
    pdf.save(path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    inventory = inspect_pdf(path)
    assert inventory.font_count == 1
    for code in ["untagged-rgb", "spot-colors", "unembedded-fonts", "transparency", "overprint"]:
        rows = refs(inventory, code)
        assert {row["page"] for row in rows} == {1, 2}
        assert rows == sorted(
            rows,
            key=lambda row: (
                row["page"],
                row["resource"],
                row.get("instruction", 0),
                row.get("object") or "",
            ),
        )
        assert len({str(row) for row in rows}) == len(rows)
    font_rows = refs(inventory, "unembedded-fonts")
    assert len(font_rows) == 2 and font_rows[0]["object"].endswith(" R")
    rgb = refs(inventory, "untagged-rgb")
    assert any(row["resource"] == "Resources/XObject/Fm/Contents" for row in rgb)
    assert any(row["resource"] == "Resources/XObject/Alias/Contents" for row in rgb)
    assert all(row.get("instruction", 1) == 1 for row in rgb)
    assert inventory.to_dict() == inspect_pdf(path).to_dict()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_direct_font_image_mask_and_nested_form_references(tmp_path: Path) -> None:
    path = tmp_path / "nested.pdf"
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page()
    image = pdf.make_stream(b"abc")
    image["/Subtype"] = pikepdf.Name.Image
    image["/ColorSpace"] = pikepdf.Name.DeviceRGB
    image["/SMask"] = pdf.make_stream(b"a")
    nested = pdf.make_stream(b"/DeviceRGB cs 1 0 0 scn")
    nested["/Subtype"] = pikepdf.Name.Form
    nested["/BBox"] = pikepdf.Array([0, 0, 1, 1])
    nested["/Resources"] = pikepdf.Dictionary(
        XObject=pikepdf.Dictionary(Im=image),
        Font=pikepdf.Dictionary(F1=pikepdf.Dictionary(BaseFont=pikepdf.Name.Courier)),
    )
    page.obj["/Resources"] = pikepdf.Dictionary(XObject=pikepdf.Dictionary(Fm=nested))
    pdf.save(path)
    inventory = inspect_pdf(path)
    assert refs(inventory, "unembedded-fonts")[0]["object"] is None
    assert refs(inventory, "unembedded-fonts")[0]["resource"].endswith("/Resources/Font/F1")
    assert refs(inventory, "transparency")[0]["resource"].endswith("/Resources/XObject/Im")
    assert len(refs(inventory, "untagged-rgb")) == 2


def test_stream_error_has_page_and_object_reference(
    rgb_pdf: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: Any, **kwargs: Any) -> Any:
        raise pikepdf.PdfError("synthetic malformed content")

    monkeypatch.setattr(pikepdf, "parse_content_stream", fail)
    inventory = inspect_pdf(rgb_pdf)
    row = refs(inventory, "content-stream-unparsed")[0]
    assert row["page"] == 1 and row["resource"] == "Contents"
    assert row["object"].endswith(" R")


def test_encrypted_provenance_after_password(tmp_path: Path) -> None:
    path = tmp_path / "encrypted-provenance.pdf"
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page()
    page.obj["/Contents"] = pdf.make_stream(b"1 0 0 rg")
    pdf.save(path, encryption=pikepdf.Encryption(user="reader", owner="owner", R=6))
    inventory = inspect_pdf(path, password="reader")
    assert refs(inventory, "untagged-rgb")[0]["page"] == 1
    assert inventory.encrypted


def test_distinct_resource_font_entries_keep_their_counts(tmp_path: Path) -> None:
    path = tmp_path / "font-entries.pdf"
    pdf = pikepdf.Pdf.new()
    font = pdf.make_indirect(pikepdf.Dictionary(BaseFont=pikepdf.Name.Helvetica))
    for _ in range(2):
        page = pdf.add_blank_page()
        page.obj["/Resources"] = pdf.make_indirect(
            pikepdf.Dictionary(Font=pikepdf.Dictionary(F1=font, F2=font))
        )
    pdf.save(path)
    inventory = inspect_pdf(path)
    assert inventory.font_count == 4
    assert len(refs(inventory, "unembedded-fonts")) == 4


def test_direct_resources_self_referencing_form_terminates(tmp_path: Path) -> None:
    path = tmp_path / "direct-cycle.pdf"
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page()
    form = pdf.make_stream(b"1 0 0 rg /Self Do")
    form["/Subtype"] = pikepdf.Name.Form
    form["/BBox"] = pikepdf.Array([0, 0, 10, 10])
    form["/Resources"] = pikepdf.Dictionary(XObject=pikepdf.Dictionary(Self=form))
    page.obj["/Resources"] = pikepdf.Dictionary(XObject=pikepdf.Dictionary(Fm=form))
    pdf.save(path)
    with pikepdf.Pdf.open(path) as reopened:
        assert reopened.pages[0].Resources.XObject.Fm.Resources.objgen == (0, 0)
    inventory = inspect_pdf(path)
    rgb = refs(inventory, "untagged-rgb")
    assert len(rgb) == 1
    assert rgb[0]["resource"] == "Resources/XObject/Fm/Contents"


def test_resource_less_form_uses_direct_parent_resources_without_rescanning(tmp_path: Path) -> None:
    path = tmp_path / "resource-less.pdf"
    pdf = pikepdf.Pdf.new()
    pages = [pdf.add_blank_page() for _ in range(2)]
    form = pdf.make_stream(b"/RGB cs 1 0 0 scn")
    form["/Subtype"] = pikepdf.Name.Form
    form["/BBox"] = pikepdf.Array([0, 0, 10, 10])
    for page in pages:
        page.obj["/Resources"] = pikepdf.Dictionary(
            ColorSpace=pikepdf.Dictionary(RGB=pikepdf.Name.DeviceRGB),
            XObject=pikepdf.Dictionary(Fm=form, Alias=form),
        )
        page.obj["/Contents"] = pdf.make_stream(b"/Fm Do /Fm Do /Alias Do")
    pdf.save(path)
    with pikepdf.Pdf.open(path) as reopened:
        assert reopened.pages[0].Resources.objgen == (0, 0)
        assert "/Resources" not in reopened.pages[0].Resources.XObject.Fm
    inventory = inspect_pdf(path)
    rows = refs(inventory, "untagged-rgb")
    assert len(rows) == 6
    for page_number in (1, 2):
        assert {row["resource"] for row in rows if row["page"] == page_number} == {
            "Resources/ColorSpace/RGB",
            "Resources/XObject/Fm/Contents",
            "Resources/XObject/Alias/Contents",
        }
    assert inventory.to_dict() == inspect_pdf(path).to_dict()


def test_mutually_recursive_forms_keep_independent_shared_paths(tmp_path: Path) -> None:
    path = tmp_path / "mutual.pdf"
    pdf = pikepdf.Pdf.new()
    pages = [pdf.add_blank_page() for _ in range(2)]
    first = pdf.make_stream(b"1 0 0 rg /Other Do")
    second = pdf.make_stream(b"0 1 0 rg /Other Do")
    for form in (first, second):
        form["/Subtype"] = pikepdf.Name.Form
        form["/BBox"] = pikepdf.Array([0, 0, 10, 10])
    first["/Resources"] = pikepdf.Dictionary(XObject=pikepdf.Dictionary(Other=second))
    second["/Resources"] = pikepdf.Dictionary(XObject=pikepdf.Dictionary(Other=first))
    for page in pages:
        page.obj["/Resources"] = pikepdf.Dictionary(
            XObject=pikepdf.Dictionary(Fm=first, Alias=first)
        )
    pdf.save(path)
    inventory = inspect_pdf(path)
    rows = refs(inventory, "untagged-rgb")
    assert len(rows) == 8
    for page_number in (1, 2):
        assert {row["resource"] for row in rows if row["page"] == page_number} == {
            "Resources/XObject/Fm/Contents",
            "Resources/XObject/Fm/Resources/XObject/Other/Contents",
            "Resources/XObject/Alias/Contents",
            "Resources/XObject/Alias/Resources/XObject/Other/Contents",
        }
