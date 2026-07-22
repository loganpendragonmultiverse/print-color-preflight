from pathlib import Path

import pikepdf
import pytest

from print_color_preflight.pdf import PdfInspectionError, embed_output_intent, inspect_pdf


def test_detects_device_rgb_and_missing_output_intent(rgb_pdf: Path) -> None:
    inventory = inspect_pdf(rgb_pdf)
    assert inventory.page_count == 1
    assert "DeviceRGB" in inventory.color_spaces
    assert {item.code for item in inventory.findings} >= {"untagged-rgb", "missing-output-intent"}
    assert inventory.pages_without_trimbox == [1]


def test_detects_spot_color_and_transparency(tmp_path: Path) -> None:
    path = tmp_path / "spot.pdf"
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page(page_size=(100, 100))
    tint = pdf.make_stream(b"{ dup dup }", FunctionType=4, Domain=[0, 1], Range=[0, 1] * 4)
    page.obj["/Resources"] = pikepdf.Dictionary(
        ColorSpace=pikepdf.Dictionary(
            Spot=pikepdf.Array(
                [pikepdf.Name.Separation, pikepdf.Name("/BrandBlue"), pikepdf.Name.DeviceCMYK, tint]
            )
        ),
        ExtGState=pikepdf.Dictionary(Fade=pikepdf.Dictionary(ca=0.5, OP=True)),
    )
    page.obj["/Contents"] = pdf.make_stream(b"/Spot cs 0.5 scn 0 0 100 100 re f\n")
    pdf.save(path)

    inventory = inspect_pdf(path)
    assert inventory.spot_colors == {"BrandBlue"}
    assert inventory.has_transparency
    assert inventory.has_overprint


def test_embeds_output_intent(rgb_pdf: Path, cmyk_profile: Path) -> None:
    embed_output_intent(rgb_pdf, cmyk_profile, "Test CMYK")
    inventory = inspect_pdf(rgb_pdf)
    assert inventory.output_intents == ["Test CMYK"]


def test_rejects_missing_pdf(tmp_path: Path) -> None:
    with pytest.raises(PdfInspectionError, match="does not exist"):
        inspect_pdf(tmp_path / "missing.pdf")


def test_rejects_malformed_pdf(tmp_path: Path) -> None:
    path = tmp_path / "bad.pdf"
    path.write_bytes(b"not a PDF")
    with pytest.raises(PdfInspectionError, match="could not be parsed"):
        inspect_pdf(path)


def test_reports_encryption_when_password_is_supplied(tmp_path: Path) -> None:
    path = tmp_path / "encrypted.pdf"
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page()
    pdf.save(path, encryption=pikepdf.Encryption(user="reader", owner="owner", R=6))
    inventory = inspect_pdf(path, password="reader")
    assert inventory.encrypted
    assert "encrypted" in {finding.code for finding in inventory.findings}


def test_requires_password_for_encrypted_pdf(tmp_path: Path) -> None:
    path = tmp_path / "encrypted.pdf"
    pdf = pikepdf.Pdf.new()
    pdf.add_blank_page()
    pdf.save(path, encryption=pikepdf.Encryption(user="reader", owner="owner", R=6))
    with pytest.raises(PdfInspectionError, match="correct password"):
        inspect_pdf(path)


def test_detects_cmyk_gray_images_and_unembedded_font(tmp_path: Path) -> None:
    path = tmp_path / "resources.pdf"
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page(page_size=(100, 100))
    image = pdf.make_stream(b"\x00\x00\x00\x00")
    image["/Subtype"] = pikepdf.Name.Image
    image["/Width"] = 1
    image["/Height"] = 1
    image["/BitsPerComponent"] = 8
    image["/ColorSpace"] = pikepdf.Name.DeviceCMYK
    font = pikepdf.Dictionary(Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1)
    font["/BaseFont"] = pikepdf.Name("/NotEmbedded")
    page.obj["/Resources"] = pikepdf.Dictionary(
        XObject=pikepdf.Dictionary(Im=image), Font=pikepdf.Dictionary(F1=font)
    )
    page.obj["/Contents"] = pdf.make_stream(b"0.5 g 0 0 10 10 re f 0 0 0 1 k\n")
    pdf.save(path)
    inventory = inspect_pdf(path)
    assert {"DeviceGray", "DeviceCMYK"} <= inventory.color_spaces
    assert inventory.unembedded_fonts == {"NotEmbedded"}


def test_clean_tagged_pdf_gets_no_obvious_issues(tmp_path: Path, cmyk_profile: Path) -> None:
    path = tmp_path / "tagged.pdf"
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page(page_size=(100, 100))
    page.obj["/TrimBox"] = page.obj["/MediaBox"]
    profile = pdf.make_stream(cmyk_profile.read_bytes())
    profile["/N"] = 4
    page.obj["/Resources"] = pikepdf.Dictionary(
        ColorSpace=pikepdf.Dictionary(Print=pikepdf.Array([pikepdf.Name.ICCBased, profile]))
    )
    page.obj["/Contents"] = pdf.make_stream(b"/Print cs 0 0 0 1 scn 0 0 10 10 re f\n")
    intent = pikepdf.Dictionary(OutputConditionIdentifier="Test")
    pdf.Root["/OutputIntents"] = pikepdf.Array([intent])
    pdf.save(path)
    inventory = inspect_pdf(path)
    assert "ICCBased CMYK" in inventory.color_spaces
    assert [finding.code for finding in inventory.findings] == ["no-obvious-issues"]
