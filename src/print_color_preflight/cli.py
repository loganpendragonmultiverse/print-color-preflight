from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .ghostscript import GhostscriptError, convert_pdf, find_ghostscript, ghostscript_version
from .ink import analyze_ink_coverage
from .models import ConversionOptions, RenderingIntent, Severity, __version__
from .pdf import PdfInspectionError, inspect_pdf
from .profiles import ProfileError, inspect_profile, require_cmyk_output_profile
from .report import write_html_report, write_json_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="print-color-preflight",
        description="Inspect and convert PDFs with an explicit print-condition ICC profile.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_command = subparsers.add_parser("inspect", help="Inspect PDF color and print risks")
    inspect_command.add_argument("pdf", type=Path)
    inspect_command.add_argument("--password")
    inspect_command.add_argument("--json", dest="json_path", type=Path)
    inspect_command.add_argument("--html", dest="html_path", type=Path)
    inspect_command.add_argument(
        "--fail-on",
        choices=["never", "warning", "error"],
        default="error",
        help="Select which finding severity makes the command fail",
    )

    profile_command = subparsers.add_parser("profile", help="Inspect an ICC profile header")
    profile_command.add_argument("icc_profile", type=Path)
    profile_command.add_argument("--require-cmyk-output", action="store_true")
    profile_command.add_argument("--json", dest="json_path", type=Path)

    plan_command = subparsers.add_parser("plan", help="Validate and explain a conversion plan")
    _add_conversion_arguments(plan_command, include_output=False)

    convert_command = subparsers.add_parser(
        "convert", help="Convert PDF colors through Ghostscript"
    )
    _add_conversion_arguments(convert_command, include_output=True)
    convert_command.add_argument("--overwrite", action="store_true")
    convert_command.add_argument("--json", dest="json_path", type=Path)
    convert_command.add_argument("--html", dest="html_path", type=Path)

    ink_command = subparsers.add_parser("ink", help="Estimate total area coverage by raster proof")
    ink_command.add_argument("pdf", type=Path)
    ink_command.add_argument("--limit", type=float, default=300.0, help="TAC limit in percent")
    ink_command.add_argument("--dpi", type=int, default=72)
    ink_command.add_argument("--ghostscript", type=Path)
    ink_command.add_argument("--json", dest="json_path", type=Path)

    doctor_command = subparsers.add_parser("doctor", help="Check the local conversion dependency")
    doctor_command.add_argument("--ghostscript", type=Path)
    return parser


def _add_conversion_arguments(parser: argparse.ArgumentParser, *, include_output: bool) -> None:
    parser.add_argument("pdf", type=Path)
    if include_output:
        parser.add_argument("output", type=Path)
    parser.add_argument("--profile", required=True, type=Path, help="Destination CMYK ICC profile")
    parser.add_argument(
        "--intent",
        choices=[intent.value for intent in RenderingIntent],
        default=RenderingIntent.PERCEPTUAL.value,
    )
    parser.add_argument("--no-black-point-compensation", action="store_true")
    parser.add_argument("--no-preserve-black", action="store_true")
    parser.add_argument("--ghostscript", type=Path)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "inspect":
            return _inspect(args)
        if args.command == "profile":
            return _profile(args)
        if args.command == "plan":
            return _plan(args)
        if args.command == "convert":
            return _convert(args)
        if args.command == "ink":
            return _ink(args)
        if args.command == "doctor":
            executable = find_ghostscript(args.ghostscript)
            print(f"Ghostscript: {executable}")
            print(ghostscript_version(executable))
            return 0
    except (GhostscriptError, PdfInspectionError, ProfileError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


def _inspect(args: argparse.Namespace) -> int:
    inventory = inspect_pdf(args.pdf, args.password)
    data = inventory.to_dict()
    _write_requested_reports(data, args.json_path, args.html_path, "PDF color preflight")
    _print_inventory(data)
    if args.fail_on == "warning" and inventory.highest_severity in {
        Severity.WARNING,
        Severity.ERROR,
    }:
        return 1
    if args.fail_on == "error" and inventory.highest_severity == Severity.ERROR:
        return 1
    return 0


def _profile(args: argparse.Namespace) -> int:
    profile = (
        require_cmyk_output_profile(args.icc_profile)
        if args.require_cmyk_output
        else inspect_profile(args.icc_profile)
    )
    data = profile.to_dict()
    if args.json_path:
        write_json_report(data, args.json_path)
    print(json.dumps(data, indent=2))
    return 0


def _options(args: argparse.Namespace) -> ConversionOptions:
    return ConversionOptions(
        destination_profile=args.profile,
        intent=RenderingIntent(args.intent),
        black_point_compensation=not args.no_black_point_compensation,
        preserve_black=not args.no_preserve_black,
    )


def _plan(args: argparse.Namespace) -> int:
    inventory = inspect_pdf(args.pdf)
    profile = require_cmyk_output_profile(args.profile)
    options = _options(args)
    plan: dict[str, Any] = {
        "input": inventory.to_dict(),
        "destination_profile": profile.to_dict(),
        "rendering_intent": options.intent.value,
        "black_point_compensation": options.black_point_compensation,
        "preserve_black": options.preserve_black,
        "decisions_required": [
            finding.to_dict()
            for finding in inventory.findings
            if finding.code in {"untagged-rgb", "spot-colors", "overprint"}
        ],
        "pdfx_certification": (
            "not claimed; validate the result separately for a required PDF/X flavor"
        ),
    }
    print(json.dumps(plan, indent=2))
    return 0


def _convert(args: argparse.Namespace) -> int:
    result = convert_pdf(
        args.pdf,
        args.output,
        _options(args),
        executable=args.ghostscript,
        overwrite=args.overwrite,
    )
    data = result.to_dict()
    _write_requested_reports(data, args.json_path, args.html_path, "PDF conversion postflight")
    print(f"Converted: {result.output_path}")
    print(f"Profile: {result.profile.description}")
    print(f"SHA-256: {result.output_sha256}")
    return 0


def _ink(args: argparse.Namespace) -> int:
    result = analyze_ink_coverage(
        args.pdf,
        tac_limit_percent=args.limit,
        dpi=args.dpi,
        executable=args.ghostscript,
    )
    data = result.to_dict()
    if args.json_path:
        write_json_report(data, args.json_path)
    print(json.dumps(data, indent=2))
    return 1 if result.pixels_over_limit else 0


def _write_requested_reports(
    data: dict[str, Any], json_path: Path | None, html_path: Path | None, title: str
) -> None:
    if json_path:
        write_json_report(data, json_path)
    if html_path:
        write_html_report(data, html_path, title)


def _print_inventory(data: dict[str, Any]) -> None:
    print(f"PDF: {data['path']}")
    print(
        f"Pages: {data['page_count']} | Version: {data['pdf_version']} | Status: {data['status']}"
    )
    print("Color spaces: " + (", ".join(data["color_spaces"]) or "none detected"))
    print("Output intents: " + (", ".join(data["output_intents"]) or "none"))
    for finding in data["findings"]:
        page = f" page {finding['page']}" if finding.get("page") else ""
        print(f"[{finding['severity'].upper()}] {finding['code']}{page}: {finding['message']}")


if __name__ == "__main__":
    raise SystemExit(main())
