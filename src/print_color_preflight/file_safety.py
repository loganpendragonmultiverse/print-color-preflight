from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def signature(path: Path) -> tuple[int, int, int, int, int, str]:
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError(f"Expected a non-symlink regular file: {path}")
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns, digest(path)


def new_destination(path: Path) -> None:
    if os.path.lexists(path):
        raise ValueError(f"Report already exists: {path}")
