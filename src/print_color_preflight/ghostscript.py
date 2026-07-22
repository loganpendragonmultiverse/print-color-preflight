from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .models import ConversionOptions, ConversionResult
from .pdf import embed_output_intent, inspect_pdf
from .profiles import require_cmyk_output_profile


class GhostscriptError(RuntimeError):
    """Raised when Ghostscript is missing or a conversion fails."""


def find_ghostscript(explicit: Path | None = None) -> Path:
    candidates: list[str] = []
    if explicit is not None:
        candidates.append(str(explicit.expanduser()))
    configured = os.environ.get("PRINT_COLOR_GHOSTSCRIPT")
    if configured:
        candidates.append(configured)
    candidates.extend(["gswin64c.exe", "gswin32c.exe", "gs"])
    for candidate in candidates:
        resolved = shutil.which(candidate) if not Path(candidate).is_file() else candidate
        if resolved:
            return Path(resolved).resolve()
    raise GhostscriptError(
        "Ghostscript was not found. Install it or set PRINT_COLOR_GHOSTSCRIPT "
        "to its CLI executable."
    )


def ghostscript_version(executable: Path) -> str:
    completed = subprocess.run(
        [str(executable), "-version"],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    if completed.returncode != 0:
        raise GhostscriptError(completed.stderr.strip() or "Ghostscript version check failed")
    return (completed.stdout or completed.stderr).splitlines()[0].strip()


def build_conversion_command(
    executable: Path,
    input_path: Path,
    output_path: Path,
    options: ConversionOptions,
) -> tuple[str, ...]:
    args = [
        str(executable),
        "-dSAFER",
        "-dBATCH",
        "-dNOPAUSE",
        "-dNOPROMPT",
        "-dPDFSTOPONERROR",
        "-sDEVICE=pdfwrite",
        f"-dCompatibilityLevel={options.compatibility_level}",
        "-sColorConversionStrategy=CMYK",
        "-sProcessColorModel=DeviceCMYK",
        f"-sOutputICCProfile={options.destination_profile.resolve()}",
        f"-dRenderIntent={options.intent.ghostscript_value}",
        f"-dBlackPtComp={1 if options.black_point_compensation else 0}",
        "-dDeviceGrayToK=true",
        f"-dPreserveBlack={'true' if options.preserve_black else 'false'}",
        f"-sOutputFile={output_path}",
        str(input_path),
    ]
    return tuple(args)


def convert_pdf(
    input_path: Path,
    output_path: Path,
    options: ConversionOptions,
    *,
    executable: Path | None = None,
    overwrite: bool = False,
) -> ConversionResult:
    source = input_path.expanduser().resolve()
    destination = output_path.expanduser().resolve()
    if not source.is_file():
        raise GhostscriptError(f"Input PDF does not exist: {source}")
    if source == destination:
        raise GhostscriptError("Input and output paths must be different")
    if destination.exists() and not overwrite:
        raise GhostscriptError(f"Output already exists (use --overwrite): {destination}")
    profile = require_cmyk_output_profile(options.destination_profile)
    gs = find_ghostscript(executable)
    version = ghostscript_version(gs)
    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="print-color-preflight-") as temporary:
        temporary_output = Path(temporary) / "converted.pdf"
        command = build_conversion_command(gs, source, temporary_output, options)
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if completed.returncode != 0 or not temporary_output.is_file():
            detail = (completed.stderr or completed.stdout).strip()
            raise GhostscriptError(f"Ghostscript conversion failed: {detail}")
        try:
            embed_output_intent(temporary_output, profile.path, profile.description)
            postflight = inspect_pdf(temporary_output)
        except Exception as exc:
            raise GhostscriptError(f"Converted PDF failed postflight validation: {exc}") from exc
        if postflight.page_count == 0:
            raise GhostscriptError("Converted PDF contains no pages")
        if destination.exists():
            destination.unlink()
        shutil.move(str(temporary_output), destination)

    postflight.path = destination
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    public_command = build_conversion_command(gs, source, destination, options)
    return ConversionResult(
        input_path=source,
        output_path=destination,
        profile=profile,
        options=options,
        ghostscript_version=version,
        command=public_command,
        output_sha256=digest,
        inventory=postflight,
    )
