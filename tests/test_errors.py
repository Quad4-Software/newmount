# SPDX-License-Identifier: 0BSD
"""Error-path tests that need no privileges."""

import errno
import platform
import sys

import pytest

import newmount
import newmount._syscall


def test_mount_error_is_oserror() -> None:
    assert issubclass(newmount.MountError, OSError)
    assert issubclass(newmount.UnsupportedError, newmount.MountError)


def test_call_enosys_maps_to_unsupported() -> None:
    # a syscall number that does not exist returns ENOSYS
    with pytest.raises(newmount.UnsupportedError) as excinfo:
        newmount._syscall._call(0x7FFFFFFF)
    assert excinfo.value.errno == errno.ENOSYS


def test_umount_error_preserves_errno() -> None:
    with pytest.raises(newmount.MountError) as excinfo:
        newmount.umount2("/nonexistent-newmount-path")
    assert excinfo.value.errno in (errno.ENOENT, errno.EINVAL, errno.EPERM)


def test_mount_error_preserves_errno() -> None:
    with pytest.raises(newmount.MountError) as excinfo:
        newmount.mount("nodev", "/nonexistent-newmount-path", "tmpfs", 0)
    assert excinfo.value.errno in (
        errno.ENOENT,
        errno.EPERM,
        errno.EACCES,
        errno.ENODEV,
    )


def test_unsupported_arch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(newmount._syscall, "_numbers", None)
    monkeypatch.setattr(platform, "machine", lambda: "vax9000")
    with pytest.raises(newmount.UnsupportedError):
        newmount._syscall._syscall_numbers()


def test_fsconfig_binary_requires_bytes() -> None:
    with pytest.raises(TypeError, match="bytes"):
        newmount.fsconfig(0, newmount.FSCONFIG_SET_BINARY, "key", "not-bytes")


def _detached_ctx() -> newmount.FsContext:
    ctx = newmount.FsContext.__new__(newmount.FsContext)
    ctx._fd = -1
    return ctx


def test_set_rejects_unknown_value_type() -> None:
    ctx = _detached_ctx()
    with pytest.raises(TypeError, match="unsupported"):
        ctx.set("key", 1.5)  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]


def test_closed_fd_raises() -> None:
    ctx = _detached_ctx()
    assert ctx.closed
    with pytest.raises(ValueError, match="closed"):
        ctx.fileno()
    mnt = newmount.MountFd.__new__(newmount.MountFd)
    mnt._fd = -1
    with pytest.raises(RuntimeError, match="closed"), mnt:
        pass


def test_fd_objects_cannot_be_copied() -> None:
    import copy

    mnt = newmount.MountFd.__new__(newmount.MountFd)
    mnt._fd = -1
    with pytest.raises(TypeError, match="copied"):
        copy.copy(mnt)


def test_new_api_supported_runs() -> None:
    if sys.platform == "linux":
        assert newmount.new_api_supported() is True
