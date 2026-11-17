import logging
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Annotated, Literal

import cyclopts.validators
from cyclopts import Parameter
from cyclopts.bind import normalize_tokens
from cyclopts.core import App
from cyclopts.exceptions import CommandCollisionError
from cyclopts.help import DefaultFormatter

from cyberdrop_dl import __version__
from cyberdrop_dl.commands import CLIarguments
from cyberdrop_dl.commands.cache import app as cache_app
from cyberdrop_dl.commands.cleanup import app as cleanup_app
from cyberdrop_dl.commands.config import app as config_app
from cyberdrop_dl.commands.database import app as database_app
from cyberdrop_dl.commands.hash import compute_hashes
from cyberdrop_dl.constants import DEFAULT_PARAMETER
from cyberdrop_dl.progress import hyperlink

logger = logging.getLogger(__name__)
COMMANDS_DOCS = Path(__file__).parent / "commands" / "commands"
NO_CONFIG_COMMANDS = []


def make_app():
    app = App(
        name="cyberdrop-dl",
        version=__version__,
        default_parameter=DEFAULT_PARAMETER,
        help_prologue=f"cyberdrop-dl [blue]v{__version__}[/blue]\nBulk [cyan]asynchronous[/cyan] downloader for multiple file hosts",
        help_format="rich",
        help_epilogue="\n".join(
            (
                f"Github:      {hyperlink('https://github.com/Cyberdrop-DL/cyberdrop-dl').markup}",
                f"Wiki (docs): {hyperlink('https://script-ware.gitbook.io/cyberdrop-dl').markup}",
            )
        ),
        result_action="return_value",
        help_formatter=DefaultFormatter().with_newline_metadata(),  # pyright: ignore[reportUnknownMemberType]
    )
    if "pytest" in sys.modules:
        register_download(app)
    return app


def register_download(app: App) -> None:
    from cyberdrop_dl.commands.retry import app as retry_app
    from cyberdrop_dl.commands.scrape import download

    for cmd in download, retry_app:
        try:
            app.command(cmd)
        except CommandCollisionError:
            pass


app = make_app()


@app.default
def main_menu(
    *,
    # This is the same as the main scrape option but input_file does not have to exists. We will create it for the user
    input_file: Annotated[
        Path,
        Parameter(
            alias=("-i", "--input"),
            help="Text/HTML file with URL(s) to download",
            validator=cyclopts.validators.Path(dir_okay=False),
            show_default=False,
        ),
    ] = Path("URLs.txt"),  # pyright: ignore[reportCallInDefaultInitializer]
    cli_args: CLIarguments | None = None,
) -> None:
    "Run [cyan]'cyberdrop-dl'[/cyan] without arguments to start the interactive TUI"
    input_file = input_file.resolve().absolute()
    from cyberdrop_dl.commands.scrape import prepare_manager, scrape

    with prepare_manager(cli_args, cli_overrides=None)() as manager:
        from cyberdrop_dl import program_ui

        source = program_ui.run(manager, input_file)
        if not isinstance(source, Path):
            from cyberdrop_dl.commands.retry import create_retry_src

            source = create_retry_src(source)
        scrape(manager, source)


@app.command
def show(
    *,
    json: Annotated[bool, Parameter(help="Output full site information as a JSON array")] = False,
) -> None:
    """Show a list of all supported sites"""
    from cyberdrop_dl.commands import supported_sites

    content = supported_sites.as_rich_json() if json else supported_sites.as_rich_table()
    app.console.print(content, soft_wrap=json)


@app.command
def report() -> None:
    """Generate and display information about the system"""
    from cyberdrop_dl.commands.report import generate_report

    app.console.print(generate_report(), soft_wrap=True)


for cmd in database_app, cleanup_app, config_app, cache_app:
    app.command(cmd)


app.command(compute_hashes, name="hash")


def _parse_tokens(tokens: Iterable[str] | str | None) -> list[str]:
    tokens = normalize_tokens(tokens)
    if not (tokens and tokens[0].startswith(("https://", "http://"))):
        return tokens

    cmd = "download"
    logger.warning(
        "URL provided as first argument. Assuming '%s' command. Run the proper command ('%s') to suppress this warning",
        cmd,
        "cyberdrop-dl download <URLS> [<OPTIONS>]",
    )
    return [cmd, *tokens]


def parse_tokens(tokens: Iterable[str] | str | None) -> list[str]:
    tokens = _parse_tokens(tokens)
    if not tokens or tokens[0] == "download":
        from cyberdrop_dl.config import normalize_aliases

        return normalize_aliases(tokens)

    return tokens


@app.command
def docs(
    *,
    format: Literal["markdown", "md", "html", "htm", "rst", "rest"] = "markdown",  # noqa: A002
) -> None:
    """Show documentation for every command"""
    docs = _generate_docs(format)
    app.console.print(docs, soft_wrap=True)


def _generate_docs(format: Literal["markdown", "md", "html", "htm", "rst", "rest"]) -> str:  # noqa: A002
    if format in {"markdown", "md"}:
        ext = ".md"
    elif format in {"rst", "rest"}:
        ext = ".rst"
    elif format in {"html", "htm"}:
        ext = ".html"
    else:
        raise ValueError(format)

    file = COMMANDS_DOCS.with_suffix(ext)
    try:
        return file.read_text(encoding="utf8")
    except FileNotFoundError:
        pass
    content = app.generate_docs(format)
    try:
        file.write_text(content, encoding="utf8")
    except OSError:
        pass
    return content
