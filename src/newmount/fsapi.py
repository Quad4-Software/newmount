# SPDX-License-Identifier: 0BSD
"""The new mount API (kernel 5.2+) plus ergonomic wrappers.

The syscall layer builds a detached mount with fsopen/fsconfig/fsmount,
attaches it with move_mount, clones an existing tree with open_tree,
reopens a mount for reconfiguration with fspick and flips attributes in
place with mount_setattr. All of it requires CAP_SYS_ADMIN in the user
namespace owning the mount namespace; unprivileged callers get there
through a user+mount namespace.

Kernel reference:
https://www.kernel.org/doc/html/latest/filesystems/mount_api.html
"""

from __future__ import annotations

import contextlib
import os
import types
from typing import TypeVar

from . import _syscall
from ._syscall import MountAttr
from .errors import MountError, UnsupportedError
from .flags import (
    AT_EMPTY_PATH,
    AT_FDCWD,
    AT_RECURSIVE,
    FSCONFIG_CMD_CREATE,
    FSCONFIG_CMD_CREATE_EXCL,
    FSCONFIG_CMD_RECONFIGURE,
    FSCONFIG_SET_BINARY,
    FSCONFIG_SET_FD,
    FSCONFIG_SET_FLAG,
    FSCONFIG_SET_PATH,
    FSCONFIG_SET_PATH_EMPTY,
    FSCONFIG_SET_STRING,
    FSMOUNT_CLOEXEC,
    FSOPEN_CLOEXEC,
    FSPICK_CLOEXEC,
    MOVE_MOUNT_F_EMPTY_PATH,
    OPEN_TREE_CLOEXEC,
    OPEN_TREE_CLONE,
)

__all__ = [
    "FsContext",
    "MountAttr",
    "MountFd",
    "Tree",
    "apply_attrs",
    "attach",
    "fsconfig",
    "fsmount",
    "fsopen",
    "fspick",
    "mount_setattr",
    "move_mount",
    "new_api_supported",
    "open_tree",
    "open_tree_clone",
]

_Path = str | bytes | os.PathLike[str] | os.PathLike[bytes]

_OwnedFdT = TypeVar("_OwnedFdT", bound="_OwnedFd")


def fsopen(fstype: str | bytes, flags: int = FSOPEN_CLOEXEC) -> int:
    """Open a filesystem configuration context, returns an fd."""
    return _syscall.fsopen(os.fsencode(fstype), flags)


def fsconfig(
    fd: int,
    cmd: int,
    key: str | bytes | None = None,
    value: str | bytes | None = None,
    aux: int = 0,
) -> None:
    """Issue one fsconfig(2) command on a context fd.

    cmd is an FSCONFIG_* constant. For SET_STRING and the SET_PATH family,
    value is the option or path string and aux the dirfd (AT_FDCWD when
    unset). For SET_BINARY, value is the blob and its length is passed as
    aux. For SET_FD, pass the file descriptor as aux. The CMD_* actions
    take neither key nor value.
    """
    k = None if key is None else os.fsencode(key)
    if cmd == FSCONFIG_SET_BINARY:
        if not isinstance(value, (bytes, bytearray, memoryview)):
            raise TypeError("FSCONFIG_SET_BINARY requires a bytes value")
        blob = bytes(value)
        _syscall.fsconfig(fd, cmd, k, blob, len(blob))
        return
    v = None if value is None else os.fsencode(value)
    _syscall.fsconfig(fd, cmd, k, v, aux)


def fsmount(fd: int, flags: int = FSMOUNT_CLOEXEC, attr_flags: int = 0) -> int:
    """Create a detached mount from a created context, returns an fd.

    attr_flags are MOUNT_ATTR_* bits applied to the new mount.
    """
    return _syscall.fsmount(fd, flags, attr_flags)


def open_tree(dfd: int, path: _Path, flags: int) -> int:
    """open_tree(2): duplicate a mount or clone a tree, returns an fd."""
    return _syscall.open_tree(dfd, os.fsencode(path), flags)


def move_mount(
    from_dfd: int,
    from_path: _Path,
    to_dfd: int,
    to_path: _Path,
    flags: int = 0,
) -> None:
    """move_mount(2): attach a detached mount or relocate an existing one.

    Pass the mount fd as from_dfd with an empty from_path and
    MOVE_MOUNT_F_EMPTY_PATH to attach it; see attach() for the shortcut.
    """
    _syscall.move_mount(
        from_dfd,
        os.fsencode(from_path),
        to_dfd,
        os.fsencode(to_path),
        flags,
    )


def fspick(dfd: int, path: _Path, flags: int = FSPICK_CLOEXEC) -> int:
    """fspick(2): reopen an existing mount as a configuration context."""
    return _syscall.fspick(dfd, os.fsencode(path), flags)


def mount_setattr(dfd: int, path: _Path, flags: int, attr: MountAttr) -> None:
    """mount_setattr(2): change attributes of a mount or mount tree."""
    _syscall.mount_setattr(dfd, os.fsencode(path), flags, attr)


def attach(
    fd: int,
    target: _Path,
    *,
    dfd: int = AT_FDCWD,
    flags: int = 0,
) -> None:
    """Attach a detached mount fd (fsmount/open_tree result) at target."""
    move_mount(fd, "", dfd, target, MOVE_MOUNT_F_EMPTY_PATH | flags)


def apply_attrs(
    path: _Path,
    *,
    set: int = 0,  # noqa: A002 - matches the mount_attr field name
    clear: int = 0,
    propagation: int = 0,
    userns_fd: int = 0,
    recursive: bool = False,
    dfd: int = AT_FDCWD,
    flags: int = 0,
) -> None:
    """Change mount attributes in place via mount_setattr(2).

    set and clear take MOUNT_ATTR_* bits; only one atime value may appear
    in set. propagation takes MS_PRIVATE, MS_SHARED, MS_SLAVE or
    MS_UNBINDABLE, or 0 to leave it unchanged. recursive applies the
    change to the whole subtree beneath path.
    """
    attr = MountAttr(
        attr_set=set,
        attr_clr=clear,
        propagation=propagation,
        userns_fd=userns_fd,
    )
    if recursive:
        flags |= AT_RECURSIVE
    p = os.fsencode(path)
    if not p:
        flags |= AT_EMPTY_PATH
    _syscall.mount_setattr(dfd, p, flags, attr)


def new_api_supported() -> bool:
    """Probe whether the kernel provides the new mount API.

    fsopen(2) fails with EPERM without CAP_SYS_ADMIN and with ENODEV for
    an unknown filesystem; both mean the API exists. ENOSYS maps to
    UnsupportedError and means the kernel predates 5.2.
    """
    try:
        fd = fsopen("proc", 0)
    except UnsupportedError:
        return False
    except MountError:
        return True
    os.close(fd)
    return True


def open_tree_clone(
    path: _Path,
    *,
    recursive: bool = True,
    cloexec: bool = True,
    dfd: int = AT_FDCWD,
    flags: int = 0,
) -> Tree:
    """Clone the mount tree rooted at path into a detached Tree.

    recursive passes AT_RECURSIVE so the whole subtree is cloned; with
    recursive=False only the topmost mount is cloned. The clone is not
    attached anywhere until Tree.attach() is called.
    """
    fl = OPEN_TREE_CLONE | flags
    if cloexec:
        fl |= OPEN_TREE_CLOEXEC
    if recursive:
        fl |= AT_RECURSIVE
    return Tree(open_tree(dfd, path, fl))


class _OwnedFd:
    """Base for objects that own a kernel file descriptor."""

    __slots__ = ("_fd",)

    def __init__(self, fd: int) -> None:
        self._fd = fd

    @property
    def closed(self) -> bool:
        """Whether the file descriptor has been closed."""
        return self._fd < 0

    def fileno(self) -> int:
        """Return the underlying file descriptor."""
        if self._fd < 0:
            raise ValueError("file descriptor is closed")
        return self._fd

    def close(self) -> None:
        """Close the file descriptor. Safe to call twice."""
        if self._fd >= 0:
            os.close(self._fd)
            self._fd = -1

    def __copy__(self) -> _OwnedFd:
        raise TypeError(
            f"{type(self).__name__} cannot be copied; it owns a kernel file descriptor"
        )

    def __deepcopy__(self, memo: dict[int, object]) -> _OwnedFd:
        raise TypeError(
            f"{type(self).__name__} cannot be copied; it owns a kernel file descriptor"
        )

    def __repr__(self) -> str:
        state = "closed" if self.closed else "open"
        return f"{type(self).__name__}(fd={self._fd}, {state})"

    def __enter__(self: _OwnedFdT) -> _OwnedFdT:
        if self.closed:
            raise RuntimeError(f"{type(self).__name__} is closed")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: types.TracebackType | None,
    ) -> None:
        self.close()

    def __del__(self) -> None:
        # __del__ must never raise
        with contextlib.suppress(Exception):
            self.close()


class MountFd(_OwnedFd):
    """A detached mount fd, the result of fsmount() or open_tree().

    The mount is not part of the file hierarchy until attach() moves it
    under a mountpoint. Use as a context manager or call close() to
    release the fd.
    """

    __slots__ = ()

    def attach(
        self,
        target: _Path,
        *,
        dfd: int = AT_FDCWD,
        flags: int = 0,
    ) -> None:
        """Attach this detached mount at target via move_mount(2)."""
        attach(self.fileno(), target, dfd=dfd, flags=flags)

    def apply_attrs(
        self,
        *,
        set: int = 0,  # noqa: A002 - matches the mount_attr field name
        clear: int = 0,
        propagation: int = 0,
        userns_fd: int = 0,
        recursive: bool = False,
    ) -> None:
        """Change attributes on this mount via mount_setattr(2)."""
        apply_attrs(
            "",
            set=set,
            clear=clear,
            propagation=propagation,
            userns_fd=userns_fd,
            recursive=recursive,
            dfd=self.fileno(),
        )


class Tree(MountFd):
    """A detached clone of an existing mount tree (OPEN_TREE_CLONE)."""

    __slots__ = ()


class FsContext(_OwnedFd):
    """Filesystem configuration context from fsopen(2) or fspick(2).

    Configure parameters with set()/set_flag()/set_path(), then create()
    to instantiate the superblock and mount() to obtain a detached
    MountFd:

        with FsContext("tmpfs") as ctx:
            ctx.set("size", "16m")
            ctx.create()
            with ctx.mount() as mnt:
                mnt.attach("/mnt/scratch")

    FsContext.pick() reopens an existing mount so reconfigure() can change
    its parameters.
    """

    __slots__ = ()

    def __init__(self, fstype: str | bytes, flags: int = FSOPEN_CLOEXEC) -> None:
        super().__init__(fsopen(fstype, flags))

    @classmethod
    def _adopt(cls, fd: int) -> FsContext:
        self = cls.__new__(cls)
        _OwnedFd.__init__(self, fd)
        return self

    @classmethod
    def pick(
        cls,
        path: _Path,
        *,
        dfd: int = AT_FDCWD,
        flags: int = FSPICK_CLOEXEC,
    ) -> FsContext:
        """Reopen the mount at path for reconfiguration via fspick(2)."""
        return cls._adopt(fspick(dfd, path, flags))

    def _config(
        self,
        cmd: int,
        key: str | bytes | None = None,
        value: str | bytes | None = None,
        aux: int = 0,
    ) -> None:
        fsconfig(self.fileno(), cmd, key, value, aux)

    def set_flag(self, key: str | bytes) -> None:
        """Set a parameter that takes no value (FSCONFIG_SET_FLAG)."""
        self._config(FSCONFIG_SET_FLAG, key)

    def set(self, key: str | bytes, value: str | bytes | int) -> None:
        """Set one parameter, dispatching on the value type.

        str sends FSCONFIG_SET_STRING, bytes sends FSCONFIG_SET_BINARY and
        int sends FSCONFIG_SET_FD with the value as the file descriptor.
        Numeric filesystem options are passed as strings.
        """
        if isinstance(value, str):
            self._config(FSCONFIG_SET_STRING, key, value)
        elif isinstance(value, (bytes, bytearray, memoryview)):
            self._config(FSCONFIG_SET_BINARY, key, bytes(value))
        elif isinstance(value, int):
            self._config(FSCONFIG_SET_FD, key, None, value)
        else:
            raise TypeError(f"unsupported fsconfig value type: {type(value)!r}")

    def set_path(
        self,
        key: str | bytes,
        path: _Path,
        *,
        dfd: int = AT_FDCWD,
        allow_empty: bool = False,
    ) -> None:
        """Set a parameter that takes a path (FSCONFIG_SET_PATH)."""
        cmd = FSCONFIG_SET_PATH_EMPTY if allow_empty else FSCONFIG_SET_PATH
        self._config(cmd, key, os.fsencode(path), dfd)

    def create(self, *, exclusive: bool = False) -> None:
        """Instantiate the superblock (FSCONFIG_CMD_CREATE).

        exclusive uses FSCONFIG_CMD_CREATE_EXCL to fail rather than reuse
        an existing matching superblock.
        """
        self._config(FSCONFIG_CMD_CREATE_EXCL if exclusive else FSCONFIG_CMD_CREATE)

    def reconfigure(self) -> None:
        """Apply queued parameters to an existing superblock."""
        self._config(FSCONFIG_CMD_RECONFIGURE)

    def mount(self, attr_flags: int = 0, *, flags: int = FSMOUNT_CLOEXEC) -> MountFd:
        """Create a detached mount from this context via fsmount(2).

        attr_flags are MOUNT_ATTR_* bits applied to the new mount.
        """
        return MountFd(fsmount(self.fileno(), flags, attr_flags))
