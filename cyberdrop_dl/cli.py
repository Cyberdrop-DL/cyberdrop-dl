from pathlib import Path
from typing import Annotated

import cyclopts.validators
from cyclopts import Parameter
from cyclopts.core import App
from cyclopts.help import DefaultFormatter

from cyberdrop_dl import __version__
from cyberdrop_dl.commands import CLIarguments
from cyberdrop_dl.commands.cache import app as cache_app
from cyberdrop_dl.commands.cleanup import app as cleanup_app
from cyberdrop_dl.commands.config import app as config_app
from cyberdrop_dl.commands.database import app as database_app
from cyberdrop_dl.commands.hash import compute_hashes
from cyberdrop_dl.commands.retry import app as retry_app
from cyberdrop_dl.commands.retry import create_retry_source
from cyberdrop_dl.commands.scrape import download, prepare_manager, scrape
from cyberdrop_dl.scrape_source import RetryScrapeSource, RetrySource

app = App(
    name="cyberdrop-dl",
    help="Bulk asynchronous downloader for multiple file hosts",
    version=__version__,
    default_parameter=Parameter(negative_iterable=[], json_dict=False, json_list=False),
    result_action="return_value",
    help_formatter=DefaultFormatter().with_newline_metadata(),  # pyright: ignore[reportUnknownMemberType]
)


@app.default
def main_menu(
    *,
    # This is the same as the main scrape option but input_file does not have to exists. We will create it for the user
    input_file: Annotated[
        Path,
        Parameter(
            alias="-i",
            help="Text/HTML file with URL(s) to download",
            validator=cyclopts.validators.Path(dir_okay=False),
            show_default=False,
        ),
    ] = Path("URLs.txt"),  # pyright: ignore[reportCallInDefaultInitializer]
    cli_args: CLIarguments | None = None,
) -> None:
    "Show a TUI menu equivalent to the CLI commands"
    input_file = input_file.resolve().absolute()
    with prepare_manager(cli_args, cli_overrides=None)() as manager:
        from cyberdrop_dl import program_ui

        source = program_ui.run(manager, input_file)
        scrape(manager, source=_parse_scrape_source(source))


def _parse_scrape_source(src: Path | RetrySource) -> Path | RetryScrapeSource:
    if isinstance(src, Path):
        return src
    return create_retry_source(src)


@app.command
def show() -> None:
    """Show a list of all supported sites"""
    from cyberdrop_dl.commands import supported_sites

    table = supported_sites.as_rich_table()
    app.console.print(table)


@app.command
def report() -> None:
    """Generate and display information about the system"""
    from cyberdrop_dl.commands.report import generate_report

    app.console.print(generate_report())


for cmd in download, database_app, cleanup_app, config_app, cache_app, retry_app:
    app.command(cmd)


app.command(compute_hashes, name="hash")
