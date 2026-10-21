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
        pdf = Pdf.open(pdf_path, password=password or "", inherit_page_attributes=False)
    except pikepdf.PasswordError as exc:
        raise PdfInspectionError("PDF is encrypted and requires the correct password") from exc
    except pikepdf.PdfError as exc:
        raise PdfInspectionError(f"PDF could not be parsed: {exc}") from exc

    with pdf:
        _validate_page_tree_resources(pdf)
        inventory = PdfInventory(
            path=pdf_path,
            page_count=len(pdf.pages),
            pdf_version=str(pdf.pdf_version),
            encrypted=pdf.is_encrypted,
        )
        _read_output_intents(pdf, inventory)
        seen_fonts: set[str] = set()
        for page_number, page in enumerate(pdf.pages, start=1):
            if "/TrimBox" not in page.obj:
                inventory.pages_without_trimbox.append(page_number)
            resources = _page_resources(page.obj)
            if resources is not None:
                _inspect_resources(resources, inventory, page_number, set(), seen_fonts)
            _inspect_content(page, inventory, page_number, resources=resources)
        _build_findings(inventory)
        for finding in inventory.findings:
            references = inventory.evidence.get(finding.code)
            if references:
                finding.details["references"] = sorted(
                    references,
                    key=lambda ref: (
                        ref["page"],
                        ref["resource"],
                        ref.get("instruction", 0),
                        ref.get("object") or "",
                    ),
                )
        return inventory


def _validate_page_tree_resources(pdf: Pdf) -> None:
    """Inspect raw page nodes before pikepdf Page wrappers repair Resources."""
    pending = [pdf.Root.get("/Pages")]
    seen: set[tuple[int, int]] = set()
    while pending:
        node = pending.pop()
        if not isinstance(node, pikepdf.Dictionary):
            raise PdfInspectionError("PDF page tree entries must be dictionaries")
        identity = node.objgen
        if identity != (0, 0):
            if identity in seen:
                raise PdfInspectionError("PDF page tree contains a repeated node")
            seen.add(identity)
        resources = node.get("/Resources")
        if resources is not None and not isinstance(resources, pikepdf.Dictionary):
            raise PdfInspectionError("PDF Resources must be a dictionary")
        if node.get("/Type") == pikepdf.Name.Page:
            continue
        children = node.get("/Kids")
        if not isinstance(children, pikepdf.Array):
            raise PdfInspectionError("PDF Pages Kids must be an array")
        pending.extend(children)


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
    if not isinstance(intents, (pikepdf.Array, list)):
        raise PdfInspectionError("PDF OutputIntents must be an array")
    for item in intents:
        if not isinstance(item, pikepdf.Dictionary):
            raise PdfInspectionError("PDF OutputIntents entries must be dictionaries")
        identifier = _text(item.get("/OutputConditionIdentifier"))
        info = _text(item.get("/Info"))
        inventory.output_intents.append(identifier or info or "Unlabeled output intent")


def _reference(obj: Any, page: int, resource: str, **extra: Any) -> dict[str, Any]:
    objgen = getattr(obj, "objgen", (0, 0))
    return {
        "page": page,
        "object": f"{objgen[0]} {objgen[1]} R" if objgen != (0, 0) else None,
        "resource": resource,
        **extra,
    }


def _evidence(inventory: PdfInventory, code: str, reference: dict[str, Any]) -> None:
    rows = inventory.evidence.setdefault(code, [])
    if reference not in rows:
        rows.append(reference)


def _entries(value: Any) -> list[tuple[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, pikepdf.Dictionary):
        raise PdfInspectionError("PDF resource entries must be a dictionary")
    return sorted(value.items(), key=lambda item: item[0])


def _page_resources(obj: Any) -> Any:
    seen: set[tuple[int, int]] = set()
    while obj is not None:
        if not isinstance(obj, pikepdf.Dictionary):
            raise PdfInspectionError("PDF page/parent must be a dictionary")
        if "/Resources" in obj:
            return obj["/Resources"]
        objgen = getattr(obj, "objgen", (0, 0))
        if objgen != (0, 0):
            if objgen in seen:
                break
            seen.add(objgen)
        obj = obj.get("/Parent")
    return pikepdf.Dictionary()


def _inspect_resources(
    resources: Any,
    inventory: PdfInventory,
    page_number: int,
    active: set[tuple[int, int]],
    seen_fonts: set[str],
    path: str = "Resources",
    active_forms: frozenset[tuple[int, int]] = frozenset(),
) -> None:
    if not isinstance(resources, pikepdf.Dictionary):
        raise PdfInspectionError("PDF Resources must be a dictionary")
    object_id = getattr(resources, "objgen", (0, 0))
    if object_id != (0, 0) and object_id in active:
        return
    active = active | {object_id} if object_id != (0, 0) else active

    for key, definition in _entries(resources.get("/ColorSpace")):
        _record_color_space(
            definition, inventory, _reference(definition, page_number, f"{path}/ColorSpace{key}")
        )

    for key, font in _entries(resources.get("/Font")):
        if not isinstance(font, pikepdf.Dictionary):
            raise PdfInspectionError("PDF Font entries must be dictionaries")
        reference = _reference(font, page_number, f"{path}/Font{key}")
        # Preserve resource-entry counts while collecting evidence on every page.
        resource_id = getattr(resources, "objgen", (0, 0))
        identity = (
            f"{resource_id}:{key}" if resource_id != (0, 0) else f"{page_number}:{path}:{key}"
        )
        if identity not in seen_fonts:
            inventory.font_count += 1
            seen_fonts.add(identity)
        base_name = _name(font.get("/BaseFont", "/Unknown"))
        descriptor = font.get("/FontDescriptor")
        descendants: Any = font.get("/DescendantFonts", [])
        if not isinstance(descendants, (pikepdf.Array, list)) or any(
            not isinstance(child, pikepdf.Dictionary) for child in descendants
        ):
            raise PdfInspectionError("PDF DescendantFonts must be an array of dictionaries")
        if descriptor is None and descendants:
            descriptor = descendants[0].get("/FontDescriptor")
        if descriptor is not None and not isinstance(descriptor, pikepdf.Dictionary):
            raise PdfInspectionError("PDF FontDescriptor must be a dictionary")
        if descriptor is None or not any(
            key in descriptor for key in ("/FontFile", "/FontFile2", "/FontFile3")
        ):
            inventory.unembedded_fonts.add(base_name)
            _evidence(inventory, "unembedded-fonts", {**reference, "font": base_name})

    for key, state in _entries(resources.get("/ExtGState")):
        if not isinstance(state, pikepdf.Dictionary):
            raise PdfInspectionError("PDF ExtGState entries must be dictionaries")
        reference = _reference(state, page_number, f"{path}/ExtGState{key}")
        transparent = (
            _number(state.get("/ca", 1)) < 1
            or _number(state.get("/CA", 1)) < 1
            or _name(state.get("/BM", "/Normal")) not in {"Normal", "Compatible"}
        )
        if transparent:
            inventory.has_transparency = True
            _evidence(inventory, "transparency", reference)
        if bool(state.get("/OP", False)) or bool(state.get("/op", False)):
            inventory.has_overprint = True
            _evidence(inventory, "overprint", reference)

    for key, xobject in _entries(resources.get("/XObject")):
        if not isinstance(xobject, pikepdf.Stream):
            raise PdfInspectionError("PDF XObject entries must be streams")
        child_path = f"{path}/XObject{key}"
        reference = _reference(xobject, page_number, child_path)
        subtype = _name(xobject.get("/Subtype", ""))
        if subtype == "Image":
            color_space = xobject.get("/ColorSpace")
            if color_space is not None:
                _record_color_space(color_space, inventory, reference)
            soft_mask = xobject.get("/SMask")
            if soft_mask is not None and _name(soft_mask) != "None":
                inventory.has_transparency = True
                _evidence(inventory, "transparency", reference)
        elif subtype == "Form":
            group = xobject.get("/Group")
            if group is not None and not isinstance(group, pikepdf.Dictionary):
                raise PdfInspectionError("PDF Form Group must be a dictionary")
            if group is not None and _name(group.get("/S", "")) == "Transparency":
                inventory.has_transparency = True
                _evidence(inventory, "transparency", reference)
            # Streams have stable indirect identities even when their resource
            # dictionaries are direct. Keep this guard local to the current path
            # so independent aliases and pages still receive their own evidence.
            form_id = xobject.objgen
            if form_id in active_forms:
                continue
            child_resources = xobject.get("/Resources")
            if child_resources is not None:
                _inspect_resources(
                    child_resources,
                    inventory,
                    page_number,
                    active,
                    seen_fonts,
                    f"{child_path}/Resources",
                    active_forms | {form_id},
                )
            # Resource-less Forms use the caller's definitions for content
            # operators; those definitions have already been inventoried.
            _inspect_content(
                xobject,
                inventory,
                page_number,
                f"{child_path}/Contents",
                child_resources if child_resources is not None else resources,
            )


def _inspect_content(
    page: Any,
    inventory: PdfInventory,
    page_number: int,
    path: str = "Contents",
    resources: Any = None,
) -> None:
    obj = page.obj.get("/Contents") if isinstance(page, pikepdf.Page) else page
    try:
        instructions: Any = pikepdf.parse_content_stream(page)
        for index, (operands, operator) in enumerate(instructions, 1):
            operation = str(operator)
            reference = _reference(obj, page_number, path, instruction=index, operator=operation)
            if operation in {"rg", "RG", "k", "K", "g", "G"}:
                name = {"rg": "DeviceRGB", "k": "DeviceCMYK", "g": "DeviceGray"}[operation.lower()]
                _record_color_space(pikepdf.Name("/" + name), inventory, reference)
            elif operation in {"cs", "CS"} and operands:
                _record_named_color_space(resources, operands[0], inventory, reference)
    except (pikepdf.PdfError, TypeError, ValueError) as exc:
        inventory.findings.append(
            Finding(
                code="content-stream-unparsed",
                severity=Severity.WARNING,
                page=page_number,
                message="A content stream could not be fully inspected.",
                details={"reason": str(exc), "references": [_reference(obj, page_number, path)]},
            )
        )


def _record_named_color_space(
    resources: Any, operand: Any, inventory: PdfInventory, reference: dict[str, Any]
) -> None:
    name = _name(operand)
    if name in {"DeviceRGB", "DeviceCMYK", "DeviceGray", "Pattern"}:
        _record_color_space(operand, inventory, reference)
        return
    if isinstance(resources, pikepdf.Dictionary):
        definitions: Any = resources.get("/ColorSpace", {})
        definition = definitions.get(f"/{name}")
        if definition is not None:
            _record_color_space(definition, inventory, reference)


def _record_color_space(
    definition: Any, inventory: PdfInventory, reference: dict[str, Any] | None = None
) -> None:
    if isinstance(definition, pikepdf.Name):
        inventory.color_spaces.add(_name(definition))
        if _name(definition) == "DeviceRGB" and reference is not None:
            _evidence(inventory, "untagged-rgb", reference)
        return
    if not isinstance(definition, pikepdf.Array):
        raise PdfInspectionError("PDF color space must be a name or array")
    values = list(definition)
    if not values or not isinstance(values[0], pikepdf.Name):
        raise PdfInspectionError("PDF color space array must start with a family name")
    family = _name(values[0])
    if family == "ICCBased":
        if len(values) != 2 or not isinstance(values[1], pikepdf.Stream):
            raise PdfInspectionError("PDF ICCBased color space requires a profile stream")
        components: Any = values[1].get("/N")
        if type(components) is not int or components not in {1, 3, 4}:
            raise PdfInspectionError("PDF ICCBased profile N must be 1, 3 or 4")
        inventory.color_spaces.add(
            {1: "ICCBased Gray", 3: "ICCBased RGB", 4: "ICCBased CMYK"}.get(components, "ICCBased")
        )
    elif family in {"Separation", "DeviceN"}:
        inventory.color_spaces.add(family)
        if reference is not None:
            _evidence(inventory, "spot-colors", reference)
        if len(values) < 2:
            raise PdfInspectionError("PDF spot color space requires colorant names")
        if family == "DeviceN":
            if not isinstance(values[1], pikepdf.Array) or not values[1]:
                raise PdfInspectionError("PDF DeviceN colorants must be a nonempty name array")
            names = list(values[1])
        else:
            names = [values[1]]
        if any(not isinstance(name, pikepdf.Name) for name in names):
            raise PdfInspectionError("PDF spot colorants must be names")
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
