from __future__ import annotations

from pathlib import Path
from typing import Any

import pikepdf
from pikepdf import Name, Pdf

from .models import Finding, PdfInventory, Severity


class PdfInspectionError(RuntimeError):
    """Raised when a PDF cannot be safely inspected."""


def inspect_pdf(path: Path, password: str | None = None) -> PdfInventory:
    pdf_path = path.expanduser().resolve()
    if not pdf_path.is_file():
        raise PdfInspectionError(f"PDF does not exist: {pdf_path}")
    try:
        pdf = Pdf.open(pdf_path, password=password or "")
    except pikepdf.PasswordError as exc:
        raise PdfInspectionError("PDF is encrypted and requires the correct password") from exc
    except pikepdf.PdfError as exc:
        raise PdfInspectionError(f"PDF could not be parsed: {exc}") from exc

    with pdf:
        inventory = PdfInventory(
            path=pdf_path,
            page_count=len(pdf.pages),
            pdf_version=str(pdf.pdf_version),
            encrypted=pdf.is_encrypted,
        )
        _read_output_intents(pdf, inventory)
        seen_resources: set[tuple[int, int]] = set()
        for page_number, page in enumerate(pdf.pages, start=1):
            if "/TrimBox" not in page.obj:
                inventory.pages_without_trimbox.append(page_number)
            resources = page.obj.get("/Resources")
            if resources is not None:
                _inspect_resources(resources, inventory, page_number, seen_resources)
            _inspect_content(page, inventory, page_number)
        _build_findings(inventory)
        return inventory


def embed_output_intent(
    pdf_path: Path,
    profile_path: Path,
    identifier: str,
    registry_name: str = "http://www.color.org",
) -> None:
    """Embed the destination profile as an output intent without claiming PDF/X conformance."""
    profile_data = profile_path.read_bytes()
    with Pdf.open(pdf_path, allow_overwriting_input=True) as pdf:
        stream = pdf.make_stream(profile_data)
        stream[Name.N] = 4
        intent = pikepdf.Dictionary(
            S=Name.GTS_PDFX,
            OutputConditionIdentifier=identifier,
            Info=identifier,
            RegistryName=registry_name,
            DestOutputProfile=stream,
        )
        pdf.Root[Name.OutputIntents] = pikepdf.Array([pdf.make_indirect(intent)])
        pdf.save(pdf_path)


def _read_output_intents(pdf: Pdf, inventory: PdfInventory) -> None:
    intents: Any = pdf.Root.get("/OutputIntents", [])
    for item in intents:
        identifier = _text(item.get("/OutputConditionIdentifier"))
        info = _text(item.get("/Info"))
        inventory.output_intents.append(identifier or info or "Unlabeled output intent")


def _inspect_resources(
    resources: Any,
    inventory: PdfInventory,
    page_number: int,
    seen_resources: set[tuple[int, int]],
) -> None:
    object_id = getattr(resources, "objgen", (0, 0))
    if object_id != (0, 0) and object_id in seen_resources:
        return
    if object_id != (0, 0):
        seen_resources.add(object_id)

    color_spaces = resources.get("/ColorSpace", {})
    for _, definition in color_spaces.items():
        _record_color_space(definition, inventory)

    fonts = resources.get("/Font", {})
    for _, font in fonts.items():
        inventory.font_count += 1
        base_name = _name(font.get("/BaseFont", "/Unknown"))
        descriptor = font.get("/FontDescriptor")
        descendants = font.get("/DescendantFonts", [])
        if descriptor is None and descendants:
            descriptor = descendants[0].get("/FontDescriptor")
        if descriptor is None or not any(
            key in descriptor for key in ("/FontFile", "/FontFile2", "/FontFile3")
        ):
            inventory.unembedded_fonts.add(base_name)

    ext_states = resources.get("/ExtGState", {})
    for _, state in ext_states.items():
        if _number(state.get("/ca", 1)) < 1 or _number(state.get("/CA", 1)) < 1:
            inventory.has_transparency = True
        blend_mode = _name(state.get("/BM", "/Normal"))
        if blend_mode not in {"Normal", "Compatible"}:
            inventory.has_transparency = True
        if bool(state.get("/OP", False)) or bool(state.get("/op", False)):
            inventory.has_overprint = True

    xobjects = resources.get("/XObject", {})
    for _, xobject in xobjects.items():
        subtype = _name(xobject.get("/Subtype", ""))
        if subtype == "Image":
            color_space = xobject.get("/ColorSpace")
            if color_space is not None:
                _record_color_space(color_space, inventory)
            soft_mask = xobject.get("/SMask")
            if soft_mask is not None and _name(soft_mask) != "None":
                inventory.has_transparency = True
        elif subtype == "Form":
            group = xobject.get("/Group")
            if group is not None and _name(group.get("/S", "")) == "Transparency":
                inventory.has_transparency = True
            child_resources = xobject.get("/Resources")
            if child_resources is not None:
                _inspect_resources(child_resources, inventory, page_number, seen_resources)


def _inspect_content(page: Any, inventory: PdfInventory, page_number: int) -> None:
    try:
        instructions: Any = pikepdf.parse_content_stream(page)
        for operands, operator in instructions:
            operation = str(operator)
            if operation in {"rg", "RG"}:
                inventory.color_spaces.add("DeviceRGB")
            elif operation in {"k", "K"}:
                inventory.color_spaces.add("DeviceCMYK")
            elif operation in {"g", "G"}:
                inventory.color_spaces.add("DeviceGray")
            elif operation in {"cs", "CS"} and operands:
                _record_named_color_space(page, operands[0], inventory)
    except (pikepdf.PdfError, TypeError, ValueError) as exc:
        inventory.findings.append(
            Finding(
                code="content-stream-unparsed",
                severity=Severity.WARNING,
                page=page_number,
                message="A page content stream could not be fully inspected.",
                details={"reason": str(exc)},
            )
        )


def _record_named_color_space(page: Any, operand: Any, inventory: PdfInventory) -> None:
    name = _name(operand)
    if name in {"DeviceRGB", "DeviceCMYK", "DeviceGray", "Pattern"}:
        inventory.color_spaces.add(name)
        return
    resources = page.obj.get("/Resources", {})
    definitions = resources.get("/ColorSpace", {})
    definition = definitions.get(f"/{name}")
    if definition is not None:
        _record_color_space(definition, inventory)


def _record_color_space(definition: Any, inventory: PdfInventory) -> None:
    if isinstance(definition, pikepdf.Name):
        inventory.color_spaces.add(_name(definition))
        return
    try:
        values = list(definition)
    except (TypeError, ValueError):
        return
    if not values:
        return
    family = _name(values[0])
    if family == "ICCBased" and len(values) > 1:
        components = int(values[1].get("/N", 0))
        inventory.color_spaces.add(
            {1: "ICCBased Gray", 3: "ICCBased RGB", 4: "ICCBased CMYK"}.get(components, "ICCBased")
        )
    elif family in {"Separation", "DeviceN"}:
        inventory.color_spaces.add(family)
        if len(values) > 1:
            names = values[1] if family == "DeviceN" else [values[1]]
            for name in names:
                inventory.spot_colors.add(_name(name))
    elif family:
        inventory.color_spaces.add(family)


def _build_findings(inventory: PdfInventory) -> None:
    if inventory.encrypted:
        inventory.findings.append(
            Finding(
                "encrypted",
                Severity.WARNING,
                "The PDF is encrypted; conversion permissions may apply.",
            )
        )
    if "DeviceRGB" in inventory.color_spaces:
        inventory.findings.append(
            Finding(
                "untagged-rgb",
                Severity.WARNING,
                "DeviceRGB content has no object-level source profile; confirm the intended "
                "RGB space before conversion.",
            )
        )
    if not inventory.output_intents:
        inventory.findings.append(
            Finding(
                "missing-output-intent",
                Severity.WARNING,
                "No output intent identifies the intended printing condition.",
            )
        )
    if inventory.spot_colors:
        inventory.findings.append(
            Finding(
                "spot-colors",
                Severity.WARNING,
                "Spot colors are present and require explicit preserve-or-convert review.",
                details={"names": sorted(inventory.spot_colors)},
            )
        )
    if inventory.has_transparency:
        inventory.findings.append(
            Finding(
                "transparency",
                Severity.INFO,
                "Transparency is present; use a modern PDF workflow and inspect the "
                "converted result.",
            )
        )
    if inventory.has_overprint:
        inventory.findings.append(
            Finding(
                "overprint",
                Severity.INFO,
                "Overprint settings are present and should be proofed with overprint "
                "simulation enabled.",
            )
        )
    if inventory.unembedded_fonts:
        inventory.findings.append(
            Finding(
                "unembedded-fonts",
                Severity.WARNING,
                "One or more fonts are not embedded.",
                details={"fonts": sorted(inventory.unembedded_fonts)},
            )
        )
    if inventory.pages_without_trimbox:
        inventory.findings.append(
            Finding(
                "missing-trimbox",
                Severity.INFO,
                "Some pages rely on MediaBox/CropBox because no TrimBox is defined.",
                details={"pages": inventory.pages_without_trimbox},
            )
        )
    if not inventory.findings:
        inventory.findings.append(
            Finding(
                "no-obvious-issues", Severity.INFO, "No obvious color-preflight issues were found."
            )
        )


def _name(value: Any) -> str:
    return str(value).lstrip("/")


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 1.0
