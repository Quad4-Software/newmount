# SPDX-License-Identifier: 0BSD
"""Exercise the syscall wrappers as an unprivileged caller.

Every call runs the full wrapper and fails with MountError (EPERM or
EBADF) instead of skipping, so the paths are covered without a
namespace. Behavioural coverage lives in test_integration.py.
"""

import errno
import os
import tempfile

import pytest

import newmount

_NOT_A_FS_FD = -1


def _null_fd() -> int:
    return os.open("/dev/null", os.O_RDONLY)


def test_fsopen_unprivileged() -> None:
    with pytest.raises(newmount.MountError):
        newmount.fsopen("tmpfs")


def test_fsconfig_bad_fd() -> None:
    with pytest.raises(newmount.MountError) as excinfo:
        newmount.fsconfig(_NOT_A_FS_FD, newmount.FSCONFIG_SET_STRING, "size", "4m")
    assert excinfo.value.errno in (errno.EBADF, errno.EINVAL)


def test_fsconfig_each_command_bad_fd() -> None:
    for cmd, value in (
        (newmount.FSCONFIG_SET_FLAG, None),
        (newmount.FSCONFIG_SET_BINARY, b"blob"),
        (newmount.FSCONFIG_SET_PATH, tempfile.gettempdir()),
        (newmount.FSCONFIG_SET_PATH_EMPTY, ""),
        (newmount.FSCONFIG_SET_FD, None),
        (newmount.FSCONFIG_CMD_CREATE, None),
        (newmount.FSCONFIG_CMD_RECONFIGURE, None),
        (newmount.FSCONFIG_CMD_CREATE_EXCL, None),
    ):
        aux = 0 if cmd != newmount.FSCONFIG_SET_FD else _null_fd()
        with pytest.raises(newmount.MountError) as excinfo:
            newmount.fsconfig(_NOT_A_FS_FD, cmd, "key", value, aux)
        assert excinfo.value.errno in (errno.EBADF, errno.EINVAL)


def test_fsmount_bad_fd() -> None:
    # capability is checked before the fd, so EPERM is valid too
    with pytest.raises(newmount.MountError) as excinfo:
        newmount.fsmount(_NOT_A_FS_FD)
    assert excinfo.value.errno in (errno.EBADF, errno.EINVAL, errno.EPERM)


def test_open_tree_unprivileged() -> None:
    with pytest.raises(newmount.MountError) as excinfo:
        newmount.open_tree(
            newmount.AT_FDCWD, tempfile.gettempdir(), newmount.OPEN_TREE_CLONE
        )
    assert excinfo.value.errno == errno.EPERM


def test_move_mount_bad_fd() -> None:
    with pytest.raises(newmount.MountError) as excinfo:
        newmount.move_mount(
            _NOT_A_FS_FD, "", newmount.AT_FDCWD, "/x", newmount.MOVE_MOUNT_F_EMPTY_PATH
        )
    assert excinfo.value.errno in (errno.EBADF, errno.EINVAL, errno.ENOENT, errno.EPERM)


def test_fspick_unprivileged() -> None:
    with pytest.raises(newmount.MountError):
        newmount.fspick(newmount.AT_FDCWD, "/")


def test_mount_setattr_unprivileged() -> None:
    attr = newmount.MountAttr(attr_set=newmount.MOUNT_ATTR_RDONLY)
    with pytest.raises(newmount.MountError):
        newmount.mount_setattr(newmount.AT_FDCWD, "/", 0, attr)


def test_attach_and_apply_attrs_bad_fd() -> None:
    with pytest.raises(newmount.MountError):
        newmount.attach(_NOT_A_FS_FD, tempfile.gettempdir())
    with pytest.raises(newmount.MountError):
        newmount.apply_attrs("/", set=newmount.MOUNT_ATTR_RDONLY)


def test_context_methods_on_foreign_fd() -> None:
    fd = _null_fd()
    ctx = newmount.FsContext._adopt(fd)
    try:
        with pytest.raises(newmount.MountError) as excinfo:
            ctx.set_flag("ro")
        assert excinfo.value.errno in (errno.EBADF, errno.EINVAL)
        with pytest.raises(newmount.MountError):
            ctx.set("size", "4m")
        with pytest.raises(newmount.MountError):
            ctx.set("source", b"blob")
        with pytest.raises(newmount.MountError):
            ctx.set("fd", fd)
        with pytest.raises(newmount.MountError):
            ctx.set_path("key", tempfile.gettempdir())
        with pytest.raises(newmount.MountError):
            ctx.set_path("key", "", allow_empty=True)
        with pytest.raises(newmount.MountError):
            ctx.create()
        with pytest.raises(newmount.MountError):
            ctx.create(exclusive=True)
        with pytest.raises(newmount.MountError):
            ctx.reconfigure()
        with pytest.raises(newmount.MountError):
            ctx.mount()
    finally:
        ctx.close()
    assert ctx.closed


def test_mountfd_methods_on_foreign_fd() -> None:
    fd = _null_fd()
    mnt = newmount.MountFd(fd)
    try:
        assert not mnt.closed
        assert mnt.fileno() == fd
        assert repr(mnt)
        with pytest.raises(newmount.MountError):
            mnt.attach(tempfile.gettempdir())
        with pytest.raises(newmount.MountError):
            mnt.apply_attrs(set=newmount.MOUNT_ATTR_RDONLY)
    finally:
        mnt.close()
    assert mnt.closed
    mnt.close()  # idempotent


def test_fspick_classmethod() -> None:
    with pytest.raises(newmount.MountError):
        newmount.FsContext.pick("/")


def test_open_tree_clone_unprivileged() -> None:
    with pytest.raises(newmount.MountError):
        newmount.open_tree_clone("/")


def test_classic_helpers_unprivileged() -> None:
    target = tempfile.mkdtemp()
    with pytest.raises(newmount.MountError):
        newmount.bind(target, target)
    with pytest.raises(newmount.MountError):
        newmount.make_private(target)
    with pytest.raises(newmount.MountError):
        newmount.make_shared(target)
    with pytest.raises(newmount.MountError):
        newmount.make_slave(target)
    with pytest.raises(newmount.MountError):
        newmount.make_unbindable(target)
    with pytest.raises(newmount.MountError):
        newmount.tmpfs(target, size="1m", mode=0o700, uid=0, gid=0)
    with pytest.raises(newmount.MountError):
        newmount.mount_proc(target)
