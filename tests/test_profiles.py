from pathlib import Path

import pytest

from print_color_preflight.profiles import (
    ProfileError,
    inspect_profile,
    require_cmyk_output_profile,
)


def test_inspects_cmyk_profile_header(cmyk_profile: Path) -> None:
    result = require_cmyk_output_profile(cmyk_profile)
    assert result.color_space == "CMYK"
    assert result.device_class == "prtr"
    assert result.connection_space == "Lab"
    assert len(result.sha256) == 64


def test_rejects_short_profile(tmp_path: Path) -> None:
    path = tmp_path / "short.icc"
    path.write_bytes(b"not an icc profile")
    with pytest.raises(ProfileError, match="shorter"):
        inspect_profile(path)


def test_rejects_rgb_as_destination(cmyk_profile: Path) -> None:
    data = bytearray(cmyk_profile.read_bytes())
    data[16:20] = b"RGB "
    cmyk_profile.write_bytes(data)
    with pytest.raises(ProfileError, match="must use CMYK"):
        require_cmyk_output_profile(cmyk_profile)


def test_rejects_missing_profile(tmp_path: Path) -> None:
    with pytest.raises(ProfileError, match="does not exist"):
        inspect_profile(tmp_path / "missing.icc")


def test_rejects_bad_declared_size(cmyk_profile: Path) -> None:
    data = bytearray(cmyk_profile.read_bytes())
    data[0:4] = (9999).to_bytes(4, "big")
    cmyk_profile.write_bytes(data)
    with pytest.raises(ProfileError, match="declares"):
        inspect_profile(cmyk_profile)


def test_rejects_bad_signature(cmyk_profile: Path) -> None:
    data = bytearray(cmyk_profile.read_bytes())
    data[36:40] = b"nope"
    cmyk_profile.write_bytes(data)
    with pytest.raises(ProfileError, match="acsp"):
        inspect_profile(cmyk_profile)


def test_rejects_non_output_profile(cmyk_profile: Path) -> None:
    data = bytearray(cmyk_profile.read_bytes())
    data[12:16] = b"mntr"
    cmyk_profile.write_bytes(data)
    with pytest.raises(ProfileError, match="output"):
        require_cmyk_output_profile(cmyk_profile)
