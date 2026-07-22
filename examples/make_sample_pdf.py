"""Create a tiny untagged-RGB PDF for trying the inspect command."""

from pathlib import Path

import pikepdf


def main() -> None:
    destination = Path("sample-rgb.pdf")
    pdf = pikepdf.Pdf.new()
    page = pdf.add_blank_page(page_size=(360, 240))
    page.obj["/Contents"] = pdf.make_stream(
        b"0.1 0.45 0.9 rg 36 36 288 168 re f\n0.95 0.25 0.1 rg 72 72 216 96 re f\n"
    )
    pdf.save(destination)
    print(destination.resolve())


if __name__ == "__main__":
    main()
