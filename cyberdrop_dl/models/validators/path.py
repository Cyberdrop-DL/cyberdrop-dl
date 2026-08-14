from pathlib import Path


def exists(path: Path) -> None:
    if not path.exists():
        raise ValueError(f"'{path}' does not exists")
