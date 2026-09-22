# SPDX-License-Identifier: 0BSD
"""Python bindings for the Linux mount API.

Two layers: the classic mount(2)/umount2(2) calls with helpers like
bind() and tmpfs(), and the new mount API (kernel 5.2+) built on
fsopen/fsconfig/fsmount/move_mount/open_tree/fspick/mount_setattr.
"""

from __future__ import annotations

from . import flags as flags
from .classic import (
    bind,
    make_private,
    make_shared,
    make_slave,
    make_unbindable,
    mount,
    mount_proc,
    tmpfs,
    umount,
    umount2,
)
from .errors import MountError, UnsupportedError
from .flags import *  # noqa: F403 - re-export the constant namespace
from .flags import __all__ as _flags_all
from .fsapi import (
    FsContext,
    MountAttr,
    MountFd,
    Tree,
    apply_attrs,
    attach,
    fsconfig,
    fsmount,
    fsopen,
    fspick,
    mount_setattr,
    move_mount,
    new_api_supported,
    open_tree,
    open_tree_clone,
)

__version__ = "0.1.0"

__all__ = [
    "FsContext",
    "MountAttr",
    "MountError",
    "MountFd",
    "Tree",
    "UnsupportedError",
    "__version__",
    "apply_attrs",
    "attach",
    "bind",
    "flags",
    "fsconfig",
    "fsmount",
    "fsopen",
    "fspick",
    "make_private",
    "make_shared",
    "make_slave",
    "make_unbindable",
    "mount",
    "mount_proc",
    "mount_setattr",
    "move_mount",
    "new_api_supported",
    "open_tree",
    "open_tree_clone",
    "tmpfs",
    "umount",
    "umount2",
    *_flags_all,
]
