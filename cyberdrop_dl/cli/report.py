from __future__ import annotations

from typing import TYPE_CHECKING, Any

from cyberdrop_dl import ALL_DEPENDENCIES, __version__, ffmpeg
from cyberdrop_dl.utils import get_system_information
from cyberdrop_dl.utils.markdown import Row, markdown_table

if TYPE_CHECKING:
    from collections.abc import Generator, Iterable, Sequence


def _unpack(data: Iterable[tuple[str, Any]]) -> Generator[tuple[str, str]]:
    for name, value in data:
        yield name, str(value)


def _table(title: str, headers: Sequence[str], rows: Iterable[Row]) -> str:
    return f"## {title}\n\n" + markdown_table(headers, *rows) + "\n"


def generate_report() -> str:
    return "\n".join(
        [
            _table(
                "Version",
                ["Name", "Value"],
                [
                    ("cyberdrop-dl", __version__),
                    ("ffmpeg", str(ffmpeg.version())),
                    ("ffprobe", str(ffmpeg.ffprobe_version())),
                ],
            ),
            _table(
                "System",
                ["Name", "Value"],
                _unpack(get_system_information().items()),
            ),
            _table(
                "Dependencies",
                ["Package", "Version"],
                _unpack(sorted(ALL_DEPENDENCIES.items())),
            ),
        ]
    )


def report() -> None:
    """Generate and display information about the system"""
    print(generate_report())  # noqa: T201


if __name__ == "__main__":
    report()
