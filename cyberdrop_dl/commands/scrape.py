from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import cyclopts.validators
from cyclopts import Parameter, Token
from cyclopts.group import Group

from cyberdrop_dl.commands import CLIarguments
from cyberdrop_dl.commands._compat import check_for_v9_files
from cyberdrop_dl.config import Config
from cyberdrop_dl.config.appdata import AppData
from cyberdrop_dl.exceptions import CDLConfigRuntimeErrorsGroup
from cyberdrop_dl.logs import log_spacer, set_console_level, setup_file_logging
from cyberdrop_dl.models.validators import to_yarl_url
from cyberdrop_dl.scrape_source import URLsSource
from cyberdrop_dl.url_objects import AbsoluteHttpURL
from cyberdrop_dl.utils import cleanup

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from cyclopts.argument import ArgumentCollection

    from cyberdrop_dl.manager import Manager
    from cyberdrop_dl.scrape_source import RetryScrapeSource, URLsSource


def scrape(manager: Manager, source: URLsSource | RetryScrapeSource) -> None:
    from cyberdrop_dl import aio

    with setup_file_logging(
        manager.config.logs.files.main,
        level=manager.config.logs.effective_level,
        log_http_traffic=manager.config.logs.http_traffic,
    ):
        aio.run(_scrape(manager, source))


async def _scrape(manager: Manager, source: URLsSource | RetryScrapeSource) -> None:
    from cyberdrop_dl import ffmpeg
    from cyberdrop_dl.scrape_mapper import ScrapeMapper

    manager.log_config_settings()
    if not ffmpeg.is_installed():
        _check_ffmpeg(manager.config)

    log_spacer()
    async with manager.database:
        log_spacer()
        logger.info("Starting CDL...")
        async with ScrapeMapper(manager)() as scrape_mapper:
            stats = await scrape_mapper.run(source)
            scrape_mapper.shutdown()

        await _post_runtime(manager)
        stats_summary = manager.print_stats(stats)
        await _check_for_updates(manager)
        await _notify(manager.config, stats_summary)


async def _post_runtime(manager: Manager) -> None:
    log_spacer()
    logger.info("Running Post-Download Processes\n", extra={"color": "green"})

    if (
        manager.config.hashing.mode.enabled
        and manager.config.hashing.dedupe.enabled
        and not manager.config.ignore_history
    ):
        file_hashes = await manager.hasher.run(manager.completed_downloads)
        await manager.deduper.run(file_hashes)

    if manager.config.sort.enabled:
        await manager.sorter.run()

    _perform_cleanup(manager.config)


async def _check_for_updates(manager: Manager) -> None:
    from cyberdrop_dl.updates import check_latest_pypi

    log_spacer()
    async with manager.http_client.create_aiohttp_session() as session:
        await check_latest_pypi(session)


async def _notify(config: Config, stats_summary: str) -> None:
    log_spacer()
    logger.info("Closing program...")
    logger.info("Finished downloading. Enjoy :)", extra={"color": "green"})

    if webhook_url := config.notifications.webhook:
        from cyberdrop_dl import webhook

        await webhook.notify(webhook_url, stats_summary)

    if urls := config.notifications.apprise:
        from cyberdrop_dl.utils import apprise

        await apprise.notify(urls, stats_summary)


def _validate_inputs(args: ArgumentCollection) -> None:
    try:
        cyclopts.validators.LimitedChoice(min=1, max=1)(args)
    except ValueError as e:
        if "choices may be specified." in str(e):
            raise ValueError(
                "You must provide either URLs/Files as positional arguments, `--input-file`, `--input-folder` or `--input` (and only one)"
            ) from None
        raise


_inputs_group = Group(sort_key=-1, validator=_validate_inputs)


def _file_or_url(_, tokens: Sequence[Token]) -> Path | AbsoluteHttpURL:

    value = tokens[0].value
    path = Path(value)
    if path.is_file():
        return path.resolve().absolute()
    if value.startswith(("http://", "https://")):
        return to_yarl_url(value)

    raise ValueError(f"'{value}' if not a valid URL or file")


type FileOrURL = Annotated[AbsoluteHttpURL | Path, Parameter(converter=_file_or_url)]


def download(
    *urls_or_files: Annotated[
        FileOrURL,
        Parameter(
            group=_inputs_group,
            help="File(s)/ URL(s) to download",
            show_default=False,
            consume_multiple=True,
            allow_repeating=False,
        ),
    ],
    input_file: Annotated[
        Path | None,
        Parameter(
            group=_inputs_group,
            help="Text/HTML file with URL(s) to download",
            validator=cyclopts.validators.Path(exists=True, dir_okay=False),
        ),
    ] = None,
    input_folder: Annotated[
        Path | None,
        Parameter(
            group=_inputs_group,
            help="""Read all '.txt' within this folder for URL(s) to download (non recursive).
            All URLs within the same file will be grouped in the own subfolder (the filename) within the downloads folder""",
            validator=cyclopts.validators.Path(exists=True, dir_okay=True, file_okay=False),
        ),
    ] = None,
    input: Annotated[  # noqa: A002
        Path | None,
        Parameter(
            group=_inputs_group,
            alias="-i",
            help="File/folder with URL(s) to download (non recursive)",
            validator=cyclopts.validators.Path(exists=True),
        ),
    ] = None,
    cli_args: CLIarguments | None = None,
    cli_overrides: Config | None = None,
) -> None:
    "Download URLs"
    source = input or input_folder or input_file
    if source:
        source = source.resolve().absolute()
    with prepare_manager(cli_args, cli_overrides)() as manager:
        scrape(manager, source or urls_or_files)


def prepare_manager(cli_args: CLIarguments | None, cli_overrides: Config | None) -> Manager:
    check_for_v9_files()

    from cyberdrop_dl.manager import Manager

    cli_args = cli_args or CLIarguments()
    appdata, config = _prepare_appdata_and_config(cli_args, cli_overrides)
    manager = Manager(cli_args, appdata, config)
    set_console_level(manager.config.logs.effective_console_level)
    manager.appdata.mkdirs()
    return manager


def _prepare_appdata_and_config(cli: CLIarguments, cli_overrides: Config | None = None) -> tuple[AppData, Config]:
    appdata = AppData.create(
        config_file=cli.config_file,
        cache_file=cli.cache_file,
        db_file=cli.database_file,
    )

    config = Config.from_file(cli.config_file or appdata.config_file)

    if cli_overrides:
        config = config | cli_overrides

    return appdata, config


def _check_ffmpeg(config: Config) -> None:
    errors: list[Exception] = []
    if config.sort.needs_ffmpeg:
        exc = RuntimeError("Sorting media files requires 'ffmpeg' to be installed")
        exc.add_note("Disable sorting or install ffmpeg")
        errors.append(exc)

    if config.filters.duration.needs_ffmpeg:
        exc = RuntimeError("Filtering files by duration requires 'ffmpeg' to be installed")
        exc.add_note("Disable media duration limits or install ffmpeg")
        errors.append(exc)

    if errors:
        raise CDLConfigRuntimeErrorsGroup("Some config options are impossible to fulfill", errors)


def _perform_cleanup(config: Config) -> None:

    logger.info("Checking for partial downloads...")
    if cleanup.has_partial_files(config.download_folder):
        logger.warning("There are partial downloads in the downloads folder")

    if config.delete_partial_files:
        logger.info("Deleting partial downloads...")
        cleanup.rm_partial_files(config.download_folder)

    if not config.delete_empty_folders:
        return

    _delete_empty_files(config)


def _delete_empty_files(config: Config) -> None:
    logger.info("Deleting empty files and folders...")
    cleanup.rm_empty_dirs(config.download_folder)

    sorted_folder = config.sort.output_folder
    if sorted_folder and config.sort.enabled:
        cleanup.rm_empty_dirs(sorted_folder)
