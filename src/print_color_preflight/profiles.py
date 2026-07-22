from __future__ import annotations

import hashlib
from pathlib import Path

from .models import ProfileInfo


class ProfileError(ValueError):
    """Raised when an ICC profile is missing or unsuitable."""


def inspect_profile(path: Path) -> ProfileInfo:
    profile_path = path.expanduser().resolve()
    if not profile_path.is_file():
        raise ProfileError(f"ICC profile does not exist: {profile_path}")

    data = profile_path.read_bytes()
    if len(data) < 128:
        raise ProfileError("ICC profile is shorter than the required 128-byte header")
    declared_size = int.from_bytes(data[0:4], "big")
    if declared_size < 128 or declared_size > len(data):
        raise ProfileError(
            f"ICC profile header declares {declared_size} bytes but file contains {len(data)}"
        )
    if data[36:40] != b"acsp":
        raise ProfileError("File does not contain the ICC 'acsp' signature")

    description = profile_path.stem
    try:
        from PIL import ImageCms

        opened = ImageCms.getOpenProfile(str(profile_path))
        description = ImageCms.getProfileDescription(opened).strip() or description
    except (ImportError, OSError):
        pass

    return ProfileInfo(
        path=profile_path,
        description=description,
        device_class=_signature(data[12:16]),
        color_space=_signature(data[16:20]),
        connection_space=_signature(data[20:24]),
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )


def require_cmyk_output_profile(path: Path) -> ProfileInfo:
    profile = inspect_profile(path)
    if profile.color_space != "CMYK":
        raise ProfileError(
            f"Destination profile must use CMYK device values; found {profile.color_space}"
        )
    if profile.device_class not in {"prtr", "link"}:
        raise ProfileError(
            "Destination profile must be an output (prtr) or DeviceLink (link) profile; "
            f"found {profile.device_class}"
        )
    return profile


def _signature(value: bytes) -> str:
    return value.decode("ascii", errors="replace").strip()
