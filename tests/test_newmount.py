# SPDX-License-Identifier: 0BSD

import newmount


def test_version_format() -> None:
    major, minor, patch = newmount.__version__.split(".")
    assert int(major) >= 0
    assert int(minor) >= 0
    assert int(patch) >= 0
