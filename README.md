# newmount

[![CI](https://github.com/Quad4-Software/newmount/actions/workflows/ci.yml/badge.svg)](https://github.com/Quad4-Software/newmount/actions/workflows/ci.yml)
[![CodeQL](https://github.com/Quad4-Software/newmount/actions/workflows/codeql.yml/badge.svg)](https://github.com/Quad4-Software/newmount/actions/workflows/codeql.yml)
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/Quad4-Software/newmount/badge)](https://securityscorecards.dev/viewer/?uri=github.com/Quad4-Software/newmount)
[![PyPI](https://img.shields.io/pypi/v/newmount.svg)](https://pypi.org/project/newmount/)
[![License: 0BSD](https://img.shields.io/badge/license-0BSD-blue)](LICENSE)

Dependency-free ctypes bindings for the Linux mount API: the classic
mount(2)/umount2(2) calls, and the new mount API (kernel 5.2+) built on
fsopen, fsconfig, fsmount, open_tree, move_mount, fspick and
mount_setattr.

Requires Python 3.10+ and Linux. Mounting needs CAP_SYS_ADMIN, which an
unprivileged process gets inside a user+mount namespace
(`unshare -Urm`).

## Install

    pip install newmount

## Example: classic bind mount

    import newmount

    # bind recursively, then remount read-only
    newmount.bind("/srv/data", "/mnt/data", readonly=True)

## Example: clone, reconfigure and attach with the new API

    import newmount

    # clone the tree, flip the clone read-only, attach it
    with newmount.open_tree_clone("/srv/data") as tree:
        tree.apply_attrs(set=newmount.MOUNT_ATTR_RDONLY)
        tree.attach("/mnt/data")

    # or build a fresh filesystem from scratch
    with newmount.FsContext("tmpfs") as ctx:
        ctx.set("size", "16m")
        ctx.create()
        with ctx.mount() as mnt:
            mnt.attach("/mnt/scratch")

## Development

    uv sync --group dev
    make check

License: 0BSD. Quad4 Software, https://quad4.io
