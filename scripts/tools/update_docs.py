from pathlib import Path

from cyberdrop_dl import __version__
from cyberdrop_dl.supported_sites import as_markdown

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


def make_supported_sites_markdown_table(title: str) -> str:
    markdown = as_markdown()
    header = f"{title}\n\nList of sites supported by cyberdrop-dl-patched as of version {__version__}\n\n"
    table = header + markdown + "\n"
    return table


def update_supported_sites() -> None:
    title = "# Supported sites"
    md_table = make_supported_sites_markdown_table(title)
    current_content = SUPPORTED_SITES_MD.read_text()
    end = "<!-- END_SUPPORTED_SITES-->"
    content_before, _, rest = current_content.partition(title)
    _, _, content_after = rest.partition(end)
    new_content = f"{content_before}{md_table}{end}{content_after}"
    write_if_updated(SUPPORTED_SITES_MD, current_content, new_content)


if __name__ == "__main__":
    update_supported_sites()
