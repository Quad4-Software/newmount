# SPDX-License-Identifier: 0BSD
"""End-to-end tests inside a user+mount namespace.

Each test body runs in a forked child that holds CAP_SYS_ADMIN over its
own namespaces, so real mounts are exercised without root. The whole
module is skipped when the kernel disallows unprivileged user namespaces.
"""

import errno
import os
import tempfile
from collections.abc import Callable
from pathlib import Path

import pytest

import newmount
from tests.conftest import requires_userns

pytestmark = requires_userns

Runner = Callable[[Callable[[], None]], None]


def test_classic_tmpfs(userns: Runner) -> None:
    def body() -> None:
        target = tempfile.mkdtemp()
        newmount.tmpfs(target, size="4m", mode=0o750, uid=0, gid=0)
        assert os.path.ismount(target)
        Path(target, "probe").write_text("ok")
        assert Path(target, "probe").read_text() == "ok"
        newmount.umount2(target, newmount.MNT_DETACH)

    userns(body)


def test_bind_readonly_remount(userns: Runner) -> None:
    def body() -> None:
        src = tempfile.mkdtemp()
        dst = tempfile.mkdtemp()
        newmount.tmpfs(src)
        Path(src, "file").write_text("data")
        newmount.bind(src, dst, readonly=True)
        assert Path(dst, "file").read_text() == "data"
        with pytest.raises(OSError, match="Read-only") as excinfo:
            Path(dst, "blocked").write_text("x")
        assert excinfo.value.errno == errno.EROFS
        newmount.umount2(dst, newmount.MNT_DETACH)
        newmount.umount2(src, newmount.MNT_DETACH)

    userns(body)


def test_bind_readwrite(userns: Runner) -> None:
    def body() -> None:
        src = tempfile.mkdtemp()
        dst = tempfile.mkdtemp()
        newmount.tmpfs(src)
        newmount.bind(src, dst)
        Path(dst, "via-bind").write_text("x")
        assert Path(src, "via-bind").read_text() == "x"
        newmount.umount2(dst, newmount.MNT_DETACH)
        newmount.umount2(src, newmount.MNT_DETACH)

    userns(body)


def test_fsapi_tmpfs_end_to_end(userns: Runner) -> None:
    def body() -> None:
        target = tempfile.mkdtemp()
        with newmount.FsContext("tmpfs") as ctx:
            ctx.set("size", "4m")
            ctx.set("mode", "755")
            ctx.create()
            with ctx.mount() as mnt:
                mnt.attach(target)
        assert os.path.ismount(target)
        Path(target, "probe").write_text("ok")
        assert Path(target, "probe").read_text() == "ok"
        newmount.umount2(target, newmount.MNT_DETACH)

    userns(body)


def test_fsapi_mount_attr_flags(userns: Runner) -> None:
    def body() -> None:
        target = tempfile.mkdtemp()
        with newmount.FsContext("tmpfs") as ctx:
            ctx.create()
            mnt = ctx.mount(newmount.MOUNT_ATTR_RDONLY | newmount.MOUNT_ATTR_NOSUID)
            with mnt:
                mnt.attach(target)
        assert os.path.ismount(target)
        with pytest.raises(OSError, match="Read-only") as excinfo:
            Path(target, "blocked").write_text("x")
        assert excinfo.value.errno == errno.EROFS
        newmount.umount2(target, newmount.MNT_DETACH)

    userns(body)


def test_fsapi_low_level_calls(userns: Runner) -> None:
    def body() -> None:
        target = tempfile.mkdtemp()
        cfd = newmount.fsopen("tmpfs", newmount.FSOPEN_CLOEXEC)
        newmount.fsconfig(cfd, newmount.FSCONFIG_SET_STRING, "size", "4m")
        newmount.fsconfig(cfd, newmount.FSCONFIG_CMD_CREATE)
        mfd = newmount.fsmount(cfd, newmount.FSMOUNT_CLOEXEC, 0)
        os.close(cfd)
        newmount.move_mount(
            mfd, "", newmount.AT_FDCWD, target, newmount.MOVE_MOUNT_F_EMPTY_PATH
        )
        os.close(mfd)
        assert os.path.ismount(target)
        newmount.umount2(target, newmount.MNT_DETACH)

    userns(body)


def test_open_tree_clone_rdonly_attach(userns: Runner) -> None:
    def body() -> None:
        src = tempfile.mkdtemp()
        dst = tempfile.mkdtemp()
        newmount.tmpfs(src)
        Path(src, "file").write_text("data")
        with newmount.open_tree_clone(src) as tree:
            tree.apply_attrs(set=newmount.MOUNT_ATTR_RDONLY)
            tree.attach(dst)
        assert Path(dst, "file").read_text() == "data"
        with pytest.raises(OSError, match="Read-only") as excinfo:
            Path(dst, "blocked").write_text("x")
        assert excinfo.value.errno == errno.EROFS
        newmount.umount2(dst, newmount.MNT_DETACH)
        newmount.umount2(src, newmount.MNT_DETACH)

    userns(body)


def test_mount_setattr_flip(userns: Runner) -> None:
    def body() -> None:
        target = tempfile.mkdtemp()
        newmount.tmpfs(target)
        newmount.apply_attrs(target, set=newmount.MOUNT_ATTR_RDONLY)
        with pytest.raises(OSError, match="Read-only") as excinfo:
            Path(target, "blocked").write_text("x")
        assert excinfo.value.errno == errno.EROFS
        newmount.apply_attrs(target, clear=newmount.MOUNT_ATTR_RDONLY)
        Path(target, "again").write_text("ok")
        newmount.umount2(target, newmount.MNT_DETACH)

    userns(body)


def test_mount_setattr_propagation(userns: Runner) -> None:
    def body() -> None:
        target = tempfile.mkdtemp()
        newmount.tmpfs(target)
        newmount.apply_attrs(target, propagation=newmount.MS_SHARED, recursive=True)
        info = _mountinfo_entry(target)
        assert "shared:" in info
        newmount.apply_attrs(target, propagation=newmount.MS_PRIVATE)
        info = _mountinfo_entry(target)
        assert "shared:" not in info
        newmount.umount2(target, newmount.MNT_DETACH)

    userns(body)


def test_fspick_reconfigure(userns: Runner) -> None:
    def body() -> None:
        target = tempfile.mkdtemp()
        newmount.tmpfs(target, size="4m")
        with newmount.FsContext.pick(target) as ctx:
            ctx.set("size", "16m")
            ctx.reconfigure()
        newmount.umount2(target, newmount.MNT_DETACH)

    userns(body)


def test_make_propagation_helpers(userns: Runner) -> None:
    def body() -> None:
        target = tempfile.mkdtemp()
        newmount.tmpfs(target)
        newmount.make_shared(target)
        assert "shared:" in _mountinfo_entry(target)
        # slave of an empty peer group has neither tag in mountinfo
        newmount.make_slave(target)
        info = _mountinfo_entry(target)
        assert "shared:" not in info
        assert "master:" not in info
        newmount.make_private(target)
        info = _mountinfo_entry(target)
        assert "shared:" not in info
        assert "master:" not in info
        newmount.umount2(target, newmount.MNT_DETACH)

    userns(body)


def test_bad_fstype_raises_mount_error(userns: Runner) -> None:
    def body() -> None:
        with pytest.raises(newmount.MountError) as excinfo:
            newmount.FsContext("definitely-not-a-filesystem")
        assert excinfo.value.errno == errno.ENODEV
        with pytest.raises(newmount.MountError) as excinfo:
            newmount.mount("nodev", tempfile.mkdtemp(), "not-a-fs-either", 0)
        assert excinfo.value.errno == errno.ENODEV

    userns(body)


def test_mount_proc(userns: Runner) -> None:
    def body() -> None:
        # proc refuses to mount unless the caller's active pid namespace
        # is owned by the caller's user namespace; unshare(CLONE_NEWPID)
        # only moves future children, so fork once to get inside it
        from tests.conftest import CLONE_NEWPID, unshare

        unshare(CLONE_NEWPID)
        pid = os.fork()
        if pid == 0:
            try:
                target = tempfile.mkdtemp()
                newmount.mount_proc(target)
                assert Path(target, "self", "status").exists()
                newmount.umount2(target, newmount.MNT_DETACH)
            except BaseException:  # noqa: BLE001 - failure is exit code 1
                os._exit(1)
            os._exit(0)
        _, status = os.waitpid(pid, 0)
        assert os.WIFEXITED(status)
        assert os.WEXITSTATUS(status) == 0

    userns(body)


def _mountinfo_entry(target: str) -> str:
    target = os.path.realpath(target)
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        fields = line.split()
        if len(fields) > 4 and fields[4] == target:
            return line
    return ""
