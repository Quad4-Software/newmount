# SPDX-License-Identifier: 0BSD
"""Constant and struct-layout checks against the local kernel headers."""

import ctypes

import newmount
from newmount import _syscall


def test_mount_flags_match_sys_mount_h() -> None:
    expected = {
        "MS_RDONLY": 1,
        "MS_NOSUID": 2,
        "MS_NODEV": 4,
        "MS_NOEXEC": 8,
        "MS_SYNCHRONOUS": 16,
        "MS_REMOUNT": 32,
        "MS_MANDLOCK": 64,
        "MS_DIRSYNC": 128,
        "MS_NOSYMFOLLOW": 256,
        "MS_NOATIME": 1024,
        "MS_NODIRATIME": 2048,
        "MS_BIND": 4096,
        "MS_MOVE": 8192,
        "MS_REC": 16384,
        "MS_SILENT": 32768,
        "MS_POSIXACL": 1 << 16,
        "MS_UNBINDABLE": 1 << 17,
        "MS_PRIVATE": 1 << 18,
        "MS_SLAVE": 1 << 19,
        "MS_SHARED": 1 << 20,
        "MS_RELATIME": 1 << 21,
        "MS_KERNMOUNT": 1 << 22,
        "MS_I_VERSION": 1 << 23,
        "MS_STRICTATIME": 1 << 24,
        "MS_LAZYTIME": 1 << 25,
        "MS_MGC_VAL": 0xC0ED0000,
        "MS_MGC_MSK": 0xFFFF0000,
    }
    for name, value in expected.items():
        assert getattr(newmount, name) == value, name


def test_umount_flags_match_sys_mount_h() -> None:
    assert newmount.MNT_FORCE == 1
    assert newmount.MNT_DETACH == 2
    assert newmount.MNT_EXPIRE == 4
    assert newmount.UMOUNT_NOFOLLOW == 8


def test_fsconfig_commands_match_linux_mount_h() -> None:
    expected = {
        "FSCONFIG_SET_FLAG": 0,
        "FSCONFIG_SET_STRING": 1,
        "FSCONFIG_SET_BINARY": 2,
        "FSCONFIG_SET_PATH": 3,
        "FSCONFIG_SET_PATH_EMPTY": 4,
        "FSCONFIG_SET_FD": 5,
        "FSCONFIG_CMD_CREATE": 6,
        "FSCONFIG_CMD_RECONFIGURE": 7,
        "FSCONFIG_CMD_CREATE_EXCL": 8,
    }
    for name, value in expected.items():
        assert getattr(newmount, name) == value, name


def test_new_api_flags_match_linux_mount_h() -> None:
    assert newmount.OPEN_TREE_CLONE == 1
    assert newmount.OPEN_TREE_NAMESPACE == 2
    assert newmount.OPEN_TREE_CLOEXEC != 0
    assert newmount.MOVE_MOUNT_F_SYMLINKS == 0x01
    assert newmount.MOVE_MOUNT_F_AUTOMOUNTS == 0x02
    assert newmount.MOVE_MOUNT_F_EMPTY_PATH == 0x04
    assert newmount.MOVE_MOUNT_T_SYMLINKS == 0x10
    assert newmount.MOVE_MOUNT_T_AUTOMOUNTS == 0x20
    assert newmount.MOVE_MOUNT_T_EMPTY_PATH == 0x40
    assert newmount.MOVE_MOUNT_SET_GROUP == 0x100
    assert newmount.MOVE_MOUNT_BENEATH == 0x200
    assert newmount.FSOPEN_CLOEXEC == 1
    assert newmount.FSMOUNT_CLOEXEC == 1
    assert newmount.FSMOUNT_NAMESPACE == 2
    assert newmount.FSPICK_CLOEXEC == 1
    assert newmount.FSPICK_SYMLINK_NOFOLLOW == 2
    assert newmount.FSPICK_NO_AUTOMOUNT == 4
    assert newmount.FSPICK_EMPTY_PATH == 8


def test_mount_attr_bits_match_linux_mount_h() -> None:
    expected = {
        "MOUNT_ATTR_RDONLY": 0x00000001,
        "MOUNT_ATTR_NOSUID": 0x00000002,
        "MOUNT_ATTR_NODEV": 0x00000004,
        "MOUNT_ATTR_NOEXEC": 0x00000008,
        "MOUNT_ATTR__ATIME": 0x00000070,
        "MOUNT_ATTR_RELATIME": 0x00000000,
        "MOUNT_ATTR_NOATIME": 0x00000010,
        "MOUNT_ATTR_STRICTATIME": 0x00000020,
        "MOUNT_ATTR_NODIRATIME": 0x00000080,
        "MOUNT_ATTR_IDMAP": 0x00100000,
        "MOUNT_ATTR_NOSYMFOLLOW": 0x00200000,
        "MOUNT_ATTR_SIZE_VER0": 32,
    }
    for name, value in expected.items():
        assert getattr(newmount, name) == value, name
    # the atime field sits at bit 4 inside the mask
    assert newmount.MOUNT_ATTR__ATIME >> newmount.MOUNT_ATTR_ATIME_SHIFT == 0x7


def test_mount_attr_layout() -> None:
    # /usr/include/linux/mount.h declares all four fields as __u64
    assert ctypes.sizeof(newmount.MountAttr) == 32
    assert newmount.MountAttr.attr_set.offset == 0
    assert newmount.MountAttr.attr_clr.offset == 8
    assert newmount.MountAttr.propagation.offset == 16
    assert newmount.MountAttr.userns_fd.offset == 24
    attr = newmount.MountAttr(attr_set=1, attr_clr=2, propagation=3, userns_fd=4)
    assert (attr.attr_set, attr.attr_clr, attr.propagation, attr.userns_fd) == (
        1,
        2,
        3,
        4,
    )


def test_at_flags_match_fcntl_h() -> None:
    assert newmount.AT_FDCWD == -100
    assert newmount.AT_SYMLINK_NOFOLLOW == 0x100
    assert newmount.AT_SYMLINK_FOLLOW == 0x400
    assert newmount.AT_NO_AUTOMOUNT == 0x800
    assert newmount.AT_EMPTY_PATH == 0x1000
    assert newmount.AT_RECURSIVE == 0x8000


def test_syscall_numbers() -> None:
    # asm-generic numbering, identical on x86_64, i386, aarch64, riscv
    nrs = _syscall._syscall_numbers()
    assert nrs.open_tree == 428
    assert nrs.move_mount == 429
    assert nrs.fsopen == 430
    assert nrs.fsconfig == 431
    assert nrs.fsmount == 432
    assert nrs.fspick == 433
    assert nrs.mount_setattr == 442


def test_all_exports_exist() -> None:
    for name in newmount.__all__:
        assert hasattr(newmount, name), name
