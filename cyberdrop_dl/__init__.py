import importlib.metadata
import re

__dist_name__ = "cyberdrop-dl-patched"
_distribution = importlib.metadata.distribution(__dist_name__)
__version__ = _distribution.version
__repo_url__ = next(
    f.removeprefix(prefix) for f in _distribution.metadata.json["project_url"] if f.startswith(prefix := "Repository, ")
)


def _get_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _parse_name(pep508_requirement: str) -> str:
    m = re.match(r"^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?", pep508_requirement)
    assert m is not None
    return m.group(0)


ALL_DEPENDENCIES = {pkg: _get_version(pkg) for req in (_distribution.requires or []) if (pkg := _parse_name(req))}
