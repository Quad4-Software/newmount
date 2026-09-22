# SPDX-License-Identifier: 0BSD
"""Helpers to run integration tests inside a user+mount namespace.

The new mount API needs CAP_SYS_ADMIN. An unprivileged caller gets there
by unsharing a user namespace, but only the parent may write the child's
/proc/<pid>/{uid,gid}_map. A process inside the new namespace cannot map
itself. run_in_userns therefore forks, unshares CLONE_NEWUSER in the
child, has the parent write the id maps, then unshares CLONE_NEWNS and
runs the test body. This mirrors the sandboxkit sandbox pattern.
"""

import contextlib
import ctypes
import ctypes.util
import os
import sys
import tempfile
import traceback
from collections.abc import Callable
from pathlib import Path

import pytest

import newmount

CLONE_NEWNS = 0x00020000
CLONE_NEWUSER = 0x10000000
CLONE_NEWPID = 0x20000000

_RES_CAP = 1 << 16

_libc = (
    ctypes.CDLL(ctypes.util.find_library("c") or None, use_errno=True)
    if sys.platform == "linux"
    else None
)


def unshare(flags: int) -> None:
    """unshare(2) for test bodies running inside the namespaced child."""
    assert _libc is not None
    if _libc.unshare(flags) != 0:
        raise OSError(ctypes.get_errno(), os.strerror(ctypes.get_errno()))


def _write_id_maps(pid: int) -> None:
    base = Path("/proc") / str(pid)
    (base / "setgroups").write_text("deny")
    (base / "uid_map").write_text(f"0 {os.getuid()} 1")
    (base / "gid_map").write_text(f"0 {os.getgid()} 1")


def _child_body(fn: Callable[[], None], ctl_w: int, ack_r: int, res_w: int) -> None:
    assert _libc is not None
    _libc.unshare(CLONE_NEWUSER)
    os.write(ctl_w, b"1")
    if os.read(ack_r, 1) != b"0":
        os._exit(3)
    _libc.unshare(CLONE_NEWNS)
    newmount.make_private("/")
    fn()


def run_in_userns(fn: Callable[[], None]) -> tuple[bool, str]:
    """Run fn in a forked child inside fresh user+mount namespaces.

    Returns (ok, message). Message carries the child's traceback when it
    raised. The child exits through os._exit, so nothing runs twice.
    """
    ctl_r, ctl_w = os.pipe()
    ack_r, ack_w = os.pipe()
    res_r, res_w = os.pipe()
    try:
        pid = os.fork()
    except OSError:
        for fd in (ctl_r, ctl_w, ack_r, ack_w, res_r, res_w):
            with contextlib.suppress(OSError):
                os.close(fd)
        raise
    if pid == 0:
        for fd in (ctl_r, ack_w, res_r):
            with contextlib.suppress(OSError):
                os.close(fd)
        try:
            _child_body(fn, ctl_w, ack_r, res_w)
        except BaseException:  # noqa: BLE001 - reported over the pipe, not raised
            with contextlib.suppress(OSError):
                os.write(res_w, traceback.format_exc().encode()[:_RES_CAP])
            os._exit(1)
        os._exit(0)
    for fd in (ctl_w, ack_r, res_w):
        os.close(fd)
    return _parent_run(pid, ctl_r, ack_w, res_r)


def _parent_run(pid: int, ctl_r: int, ack_w: int, res_r: int) -> tuple[bool, str]:
    """Parent side: write the child's id maps, then collect its result."""
    ok = os.read(ctl_r, 1) == b"1"
    ack = b"1"
    if ok:
        with contextlib.suppress(OSError):
            _write_id_maps(pid)
            ack = b"0"
    with contextlib.suppress(OSError):
        os.write(ack_w, ack)
    err = bytearray()
    while chunk := os.read(res_r, 65536):
        err += chunk
    for fd in (ctl_r, ack_w, res_r):
        with contextlib.suppress(OSError):
            os.close(fd)
    _, status = os.waitpid(pid, 0)
    passed = ok and os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0
    return passed, err.decode(errors="replace")


def _userns_available() -> bool:
    if sys.platform != "linux" or _libc is None:
        return False

    def probe() -> None:
        target = tempfile.mkdtemp()
        newmount.mount("tmpfs", target, "tmpfs", 0)
        newmount.umount2(target, 0)

    ok, _ = run_in_userns(probe)
    return ok


USERNS_AVAILABLE = _userns_available()

requires_userns = pytest.mark.skipif(
    not USERNS_AVAILABLE,
    reason="unprivileged user+mount namespaces unavailable",
)


@pytest.fixture
def userns() -> Callable[[Callable[[], None]], None]:
    """Return a runner executing a callable inside user+mount namespaces."""

    def runner(fn: Callable[[], None]) -> None:
        ok, err = run_in_userns(fn)
        assert ok, err or "namespaced child failed"

    return runner
