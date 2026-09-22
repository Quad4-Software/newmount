# SPDX-License-Identifier: 0BSD
"""Raw ctypes bindings for the Linux mount syscalls.

mount(2) and umount2(2) go through the libc wrappers. The new mount API
(open_tree, move_mount, fsopen, fsconfig, fsmount, fspick, mount_setattr,
all since kernel 5.2) goes through libc syscall(2) so no compiler or
libmount is needed. Every mainline architecture uses the asm-generic
numbers for these syscalls, verified against /usr/include/asm/unistd_64.h,
/usr/include/asm/unistd_32.h and /usr/include/asm-generic/unistd.h. MIPS
applies its ABI base offset instead.
"""

import ctypes
import ctypes.util
import errno
import os
import platform
import sys
from typing import NamedTuple, NoReturn

from .errors import MountError, UnsupportedError


class MountAttr(ctypes.Structure):
    """struct mount_attr for mount_setattr(2), see /usr/include/linux/mount.h.

    All four fields are u64, so the structure is 32 bytes on every ABI,
    matching MOUNT_ATTR_SIZE_VER0.
    """

    _fields_ = [
        ("attr_set", ctypes.c_uint64),
        ("attr_clr", ctypes.c_uint64),
        ("propagation", ctypes.c_uint64),
        ("userns_fd", ctypes.c_uint64),
    ]


class _Numbers(NamedTuple):
    """Per-architecture syscall numbers for the new mount API."""

    open_tree: int
    move_mount: int
    fsopen: int
    fsconfig: int
    fsmount: int
    fspick: int
    mount_setattr: int


# asm-generic numbering shared by x86_64, i386, aarch64, riscv and all
# other modern ports
_GENERIC = _Numbers(428, 429, 430, 431, 432, 433, 442)

_GENERIC_MACHINES = frozenset(
    {
        "x86_64",
        "amd64",
        "i386",
        "i486",
        "i586",
        "i686",
        "x86",
        "aarch64",
        "arm64",
        "riscv64",
        "riscv32",
        "loongarch64",
        "s390x",
        "s390",
    }
)

_libc: ctypes.CDLL | None = None
_numbers: _Numbers | None = None


def _get_libc() -> ctypes.CDLL:
    global _libc
    if _libc is None:
        if sys.platform != "linux":
            raise UnsupportedError("newmount is only available on Linux")
        name = ctypes.util.find_library("c")
        _libc = ctypes.CDLL(name or None, use_errno=True)
        _libc.syscall.restype = ctypes.c_long
    return _libc


def _syscall_numbers() -> _Numbers:
    """Return the syscall numbers for this architecture."""
    global _numbers
    if _numbers is not None:
        return _numbers
    machine = platform.machine().lower()
    if machine in ("mips64", "mips64el"):
        base = 5000  # n64 ABI
    elif machine in ("mips", "mipsel", "mips32"):
        base = 4000  # o32 ABI
    elif machine in _GENERIC_MACHINES or machine.startswith(("arm", "ppc", "powerpc")):
        base = 0
    else:
        raise UnsupportedError(
            f"no mount API syscall numbers for architecture {machine}"
        )
    _numbers = _Numbers(*(base + n for n in _GENERIC))
    return _numbers


def _raise_errno(err: int) -> NoReturn:
    if err in (errno.ENOSYS, errno.EOPNOTSUPP):
        raise UnsupportedError(err, os.strerror(err))
    raise MountError(err, os.strerror(err))


def _call(nr: int, *args: object) -> int:
    ret = int(_get_libc().syscall(nr, *args))
    if ret == -1:
        _raise_errno(ctypes.get_errno())
    return ret


def mount(
    source: bytes | None,
    target: bytes,
    fstype: bytes | None,
    flags: int,
    data: bytes | None,
) -> None:
    """mount(2) through the libc wrapper."""
    ret = int(_get_libc().mount(source, target, fstype, ctypes.c_ulong(flags), data))
    if ret == -1:
        _raise_errno(ctypes.get_errno())


def umount2(target: bytes, flags: int) -> None:
    """umount2(2) through the libc wrapper."""
    ret = int(_get_libc().umount2(target, ctypes.c_int(flags)))
    if ret == -1:
        _raise_errno(ctypes.get_errno())


def fsopen(fstype: bytes, flags: int) -> int:
    """fsopen(2): open a filesystem context, returns an fd."""
    return int(_call(_syscall_numbers().fsopen, fstype, ctypes.c_uint(flags)))


def fsconfig(
    fd: int,
    cmd: int,
    key: bytes | None,
    value: bytes | None,
    aux: int,
) -> None:
    """fsconfig(2): pass one parameter or command to a context fd."""
    _call(
        _syscall_numbers().fsconfig,
        ctypes.c_int(fd),
        ctypes.c_uint(cmd),
        key,
        value,
        ctypes.c_int(aux),
    )


def fsmount(fd: int, flags: int, attr_flags: int) -> int:
    """fsmount(2): create a detached mount from a context, returns an fd."""
    return int(
        _call(
            _syscall_numbers().fsmount,
            ctypes.c_int(fd),
            ctypes.c_uint(flags),
            ctypes.c_uint(attr_flags),
        )
    )


def open_tree(dfd: int, path: bytes, flags: int) -> int:
    """open_tree(2): open or clone a mount tree, returns an fd."""
    return int(
        _call(
            _syscall_numbers().open_tree,
            ctypes.c_int(dfd),
            path,
            ctypes.c_uint(flags),
        )
    )


def move_mount(
    from_dfd: int,
    from_path: bytes,
    to_dfd: int,
    to_path: bytes,
    flags: int,
) -> None:
    """move_mount(2): attach or relocate a mount."""
    _call(
        _syscall_numbers().move_mount,
        ctypes.c_int(from_dfd),
        from_path,
        ctypes.c_int(to_dfd),
        to_path,
        ctypes.c_uint(flags),
    )


def fspick(dfd: int, path: bytes, flags: int) -> int:
    """fspick(2): reopen an existing mount for reconfiguration."""
    return int(
        _call(
            _syscall_numbers().fspick,
            ctypes.c_int(dfd),
            path,
            ctypes.c_uint(flags),
        )
    )


def mount_setattr(dfd: int, path: bytes, flags: int, attr: MountAttr) -> None:
    """mount_setattr(2): change attributes of a mount or mount tree."""
    _call(
        _syscall_numbers().mount_setattr,
        ctypes.c_int(dfd),
        path,
        ctypes.c_uint(flags),
        ctypes.byref(attr),
        ctypes.c_size_t(ctypes.sizeof(attr)),
    )
