from pathlib import Path


def exists[T: Path](path: T) -> T:
    if not path.exists():
        raise ValueError(f"'{path}' does not exists")
    return path
