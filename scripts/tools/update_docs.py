from pathlib import Path

from cyberdrop_dl import __version__, supported_sites
from cyberdrop_dl.constants import CDL_USER_AGENT

REPO_ROOT = Path(__file__).parents[2]
CLI_ARGUMENTS_MD = REPO_ROOT / "docs/reference/cli-arguments.md"
SUPPORTED_SITES_MD = REPO_ROOT / "docs/reference/supported-websites.md"
GENERAL_MD = REPO_ROOT / "docs/reference/configuration-options/global-settings/general.md"


def _write_if_updated(path: Path, old_content: str, new_content: str) -> None:
    relative = path.relative_to(REPO_ROOT)
    if old_content != new_content:
        path.write_text(new_content, encoding="utf8")
        msg = f"Updated:'{relative}'"
    else:
        msg = f"Did not change: '{relative}'"
    print(msg)


def _make_supported_sites_markdown_table() -> str:
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


def _replace_content(text: str, marker: str, new_content: str) -> str:
    start_marker = f"<!-- START_{marker} -->"
    start = text.index(start_marker) + len(start_marker)
    end = text.index(f"<!-- END_{marker} -->")
    return text[:start] + "\n" + new_content + "\n" + text[end:]


def _get_help_message() -> str:
    from rich.console import Console

    from cyberdrop_dl.__main__ import app

    with Console(record=True, width=100) as console:
        app.help_print([], console=console)

    return console.export_text()


def _update_file(file: Path, new_content: str, *, marker: str) -> None:
    new_content = _replace_content(
        old_content := file.read_text(),
        marker=marker,
        new_content=new_content,
    )
    _write_if_updated(file, old_content, new_content)


def _get_custom_ua_crawlers() -> list[str]:
    from cyberdrop_dl.crawlers.crawler import Registry

    Registry.import_all()
    return sorted(c.FOLDER_DOMAIN for c in Registry.concrete if c._DEFAULT_UA and CDL_USER_AGENT in c._DEFAULT_UA)


def update_supported_sites() -> None:
    _update_file(
        SUPPORTED_SITES_MD,
        _make_supported_sites_markdown_table(),
        marker="SUPPORTED_SITES",
    )


def update_cli_overview() -> None:
    new_content = f"```shell\n{_get_help_message()}```"
    _update_file(
        CLI_ARGUMENTS_MD,
        new_content,
        marker="CLI_OVERVIEW",
    )


def update_custom_ua_crawlers() -> None:
    new_content = "- " + "\n- ".join(_get_custom_ua_crawlers())
    _update_file(
        GENERAL_MD,
        new_content,
        marker="CUSTOM_UA_CRAWLERS",
    )


if __name__ == "__main__":
    update_cli_overview()
    update_supported_sites()
    update_custom_ua_crawlers()
