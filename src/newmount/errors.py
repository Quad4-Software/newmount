# SPDX-License-Identifier: 0BSD
"""Exception types raised by newmount."""


class MountError(OSError):
    """A mount related syscall or operation failed."""


class UnsupportedError(MountError):
    """The running kernel or architecture lacks the requested feature."""
