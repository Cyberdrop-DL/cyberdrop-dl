from pathlib import Path

from cyberdrop_dl import __version__, supported_sites

REPO_ROOT = Path(__file__).parents[2]
CLI_ARGUMENTS_MD = REPO_ROOT / "docs/reference/cli-arguments.md"
SUPPORTED_SITES_MD = REPO_ROOT / "docs/reference/supported-websites.md"


def write_if_updated(path: Path, old_content: str, new_content: str) -> None:
    relative = path.relative_to(REPO_ROOT)
    if old_content != new_content:
        path.write_text(new_content, encoding="utf8")
        msg = f"Updated:'{relative}'"
    else:
        msg = f"Did not change: '{relative}'"
    print(msg)  # noqa: T201


def make_supported_sites_markdown_table() -> str:
    return "".join(
        (
            "\n",
            "## Supported sites",
            "\n\n",
            f"List of sites supported by cyberdrop-dl-patched as of version {__version__}",
            "\n\n",
            supported_sites.as_markdown(),
            "\n",
        )
    )


def replace(text: str, marker: str, new_content: str) -> str:
    start_marker = f"<!-- START_{marker} -->"
    start = text.index(start_marker) + len(start_marker)
    end = text.index(f"<!-- END_{marker} -->")
    return text[:start] + "\n" + new_content + "\n" + text[end:]


def update_supported_sites() -> None:
    new_content = replace(
        old_content := SUPPORTED_SITES_MD.read_text(),
        marker="SUPPORTED_SITES",
        new_content=make_supported_sites_markdown_table(),
    )
    write_if_updated(SUPPORTED_SITES_MD, old_content, new_content)


def get_help_message() -> str:
    from rich.console import Console

    from cyberdrop_dl.__main__ import app

    with Console(record=True, width=100) as console:
        app.help_print([], console=console)

    return console.export_text()


def update_cli_overview() -> None:
    new_content = replace(
        old_content := CLI_ARGUMENTS_MD.read_text(),
        marker="CLI_OVERVIEW",
        new_content=f"```shell\n{get_help_message()}```",
    )
    write_if_updated(CLI_ARGUMENTS_MD, old_content, new_content)


if __name__ == "__main__":
    update_cli_overview()
    update_supported_sites()
