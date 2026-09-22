# SPDX-License-Identifier: 0BSD
"""Helpers built on the classic mount(2) and umount2(2) calls."""

from __future__ import annotations

import os

from . import _syscall
from .flags import (
    MS_BIND,
    MS_NODEV,
    MS_NOEXEC,
    MS_NOSUID,
    MS_PRIVATE,
    MS_RDONLY,
    MS_REC,
    MS_REMOUNT,
    MS_SHARED,
    MS_SLAVE,
    MS_UNBINDABLE,
)

__all__ = [
    "bind",
    "make_private",
    "make_shared",
    "make_slave",
    "make_unbindable",
    "mount",
    "mount_proc",
    "tmpfs",
    "umount",
    "umount2",
]

_Path = str | bytes | os.PathLike[str] | os.PathLike[bytes]


def mount(
    source: _Path | None,
    target: _Path,
    fstype: str | bytes | None,
    flags: int = 0,
    data: str | bytes | None = None,
) -> None:
    """Mount a filesystem with mount(2).

    source and fstype may be None for operations that ignore them, such as
    MS_REMOUNT and propagation changes. data is the filesystem specific
    option string. Raises MountError on failure.
    """
    _syscall.mount(
        None if source is None else os.fsencode(source),
        os.fsencode(target),
        None if fstype is None else os.fsencode(fstype),
        flags,
        None if data is None else os.fsencode(data),
    )


def umount2(target: _Path, flags: int = 0) -> None:
    """Unmount with umount2(2); flags are MNT_* and UMOUNT_* bits."""
    _syscall.umount2(os.fsencode(target), flags)


def umount(target: _Path) -> None:
    """Unmount a filesystem, equivalent to umount2(target, 0)."""
    umount2(target, 0)


def bind(
    source: _Path,
    target: _Path,
    *,
    recursive: bool = True,
    readonly: bool = False,
) -> None:
    """Bind mount source onto target.

    A bind mount cannot be created read-only in one call: the kernel
    applies per-mount flags only at creation time. readonly first binds
    and then remounts the new mount with MS_REMOUNT|MS_BIND|MS_RDONLY.
    """
    flags = MS_BIND | (MS_REC if recursive else 0)
    mount(source, target, None, flags)
    if readonly:
        mount(source, target, None, flags | MS_REMOUNT | MS_RDONLY)


def _propagation(target: _Path, flag: int, recursive: bool) -> None:
    mount(None, target, None, flag | (MS_REC if recursive else 0))


def make_private(target: _Path = "/", *, recursive: bool = True) -> None:
    """Mark target (recursively by default) as private propagation."""
    _propagation(target, MS_PRIVATE, recursive)


def make_shared(target: _Path, *, recursive: bool = True) -> None:
    """Mark target (recursively by default) as shared propagation."""
    _propagation(target, MS_SHARED, recursive)


def make_slave(target: _Path, *, recursive: bool = True) -> None:
    """Mark target (recursively by default) as slave propagation."""
    _propagation(target, MS_SLAVE, recursive)


def make_unbindable(target: _Path, *, recursive: bool = True) -> None:
    """Mark target (recursively by default) as unbindable."""
    _propagation(target, MS_UNBINDABLE, recursive)


def tmpfs(
    target: _Path,
    *,
    size: int | str | None = None,
    mode: int | str | None = None,
    uid: int | None = None,
    gid: int | None = None,
    flags: int = 0,
    source: str = "tmpfs",
) -> None:
    """Mount a tmpfs at target, building the option string from keywords.

    size is a byte count or a string like "64m". mode is an int rendered
    as octal or a string passed through unchanged. uid and gid are numeric
    owner ids for the root inode.
    """
    options = []
    if size is not None:
        options.append(f"size={size}")
    if mode is not None:
        options.append(f"mode={mode:o}" if isinstance(mode, int) else f"mode={mode}")
    if uid is not None:
        options.append(f"uid={uid}")
    if gid is not None:
        options.append(f"gid={gid}")
    mount(source, target, "tmpfs", flags, ",".join(options) or None)


def mount_proc(target: _Path = "/proc") -> None:
    """Mount a fresh procfs, usually inside a new pid+mount namespace."""
    mount("proc", target, "proc", MS_NOSUID | MS_NOEXEC | MS_NODEV)
