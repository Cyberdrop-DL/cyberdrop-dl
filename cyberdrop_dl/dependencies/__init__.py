from __future__ import annotations

import importlib.metadata
import re

from cyberdrop_dl import __dist_name__


def _get_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _parse_name(pep508_requirement: str) -> str:
    m = re.match(r"^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?", pep508_requirement)
    assert m is not None
    return m.group(0)


ALL_DEPENDENCIES = {
    pkg: _get_version(pkg) for req in (importlib.metadata.requires(__dist_name__) or []) if (pkg := _parse_name(req))
}


if __name__ == "__main__":
    print(*ALL_DEPENDENCIES.items(), sep="\n")  # noqa: T201
