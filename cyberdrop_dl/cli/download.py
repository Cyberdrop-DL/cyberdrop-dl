from __future__ import annotations

import logging
from pathlib import Path  # noqa: TC003
from typing import TYPE_CHECKING, Annotated

import cyclopts.validators
from cyclopts import Parameter
from cyclopts.group import Group

from cyberdrop_dl.cli import CLIargs
from cyberdrop_dl.config import Config
from cyberdrop_dl.exceptions import CDLConfigRuntimeErrorsGroup
from cyberdrop_dl.logs import log_spacer, set_console_level, setup_file_logging
from cyberdrop_dl.models import merge_models
from cyberdrop_dl.models.types import HttpURL  # noqa: TC001
from cyberdrop_dl.utils import cleanup

logger = logging.getLogger("cyberdrop_dl")

if TYPE_CHECKING:
    from cyberdrop_dl.manager import Manager


async def _scrape(manager: Manager) -> None:
    from cyberdrop_dl import ffmpeg, webhook
    from cyberdrop_dl.scrape_mapper import ScrapeMapper
    from cyberdrop_dl.updates import check_latest_pypi
    from cyberdrop_dl.utils import apprise

    with setup_file_logging(
        manager.config.logs.files.main,
        level=manager.config.logs.effective_level,
    ):
        manager.log_config_settings()
        if not ffmpeg.is_installed():
            _check_ffmpeg(manager.config)

        log_spacer()
        async with manager.database:
            log_spacer()
            logger.info("Starting CDL...")
            async with ScrapeMapper(manager)() as scrape_mapper:
                stats = await scrape_mapper.run()

            log_spacer()
            await _post_runtime(manager)

            stats_summary = manager.print_stats(stats)

            log_spacer()
            async with manager.http_client.create_aiohttp_session() as session:
                await check_latest_pypi(session)
            log_spacer()
            logger.info("Closing program...")
            logger.info("Finished downloading. Enjoy :)", extra={"color": "green"})

            if webhook_url := manager.config.notifications.webhook:
                await webhook.send_notification(webhook_url, stats_summary)

            if urls := manager.config.notifications.apprise:
                await apprise.send_notifications(urls, stats_summary)


async def _post_runtime(manager: Manager) -> None:
    """Actions to complete after main runtime, and before UI shutdown."""
    logger.info("Running Post-Download Processes\n", extra={"color": "green"})

    if (
        manager.config.hashing.mode.enabled
        and manager.config.hashing.dedupe.enabled
        and not manager.config.ignore_history
    ):
        file_hashes = await manager.hasher.run()
        await manager.deduper.run(file_hashes)

    if manager.config.sort.enabled:
        await manager.sorter.run()

    _check_partials_and_empty_folders(manager.config)


def _main(manager: Manager) -> None:
    from cyberdrop_dl import aio, program_ui

    set_console_level(manager.config.logs.effective_console_level)
    try:
        with manager():
            if not manager.cli_args.download:
                program_ui.run(manager)
            aio.run(_scrape(manager))

    except KeyboardInterrupt:
        logger.info("Exiting (Ctrl + C) ...")


inputs_group = Group(sort_key=-1, validator=cyclopts.validators.mutually_exclusive)


def download(
    urls: Annotated[
        tuple[HttpURL, ...],
        Parameter(
            group=inputs_group,
            help="URL(s) to download",
        ),
    ] = (),
    /,
    *,
    input_file: Annotated[
        Path | None,
        Parameter(
            group=inputs_group,
            alias="-i",
            help="Text/HTML file with URL(s) to download",
            validator=cyclopts.validators.Path(exists=True, dir_okay=False),
        ),
    ] = None,
    cli: CLIargs | None = None,
    config: Config | None = None,
) -> None:
    if input_file:
        input_file = input_file.resolve().absolute()
    from cyberdrop_dl.manager import AppData, Manager

    cli = cli or CLIargs()
    cli.links = urls
    config = config or Config()
    appdata = AppData.from_path(cli.appdata_folder) if cli.appdata_folder else AppData.default()

    config_file = cli.config_file or appdata.config_file
    config = merge_models(Config.from_file(config_file), config)

    if not config.ui.mode.is_fullscreen or cli.config_file or config.sort.enabled:
        cli.download = True

    manager = Manager(cli, appdata, config, input_file)
    _main(manager)


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


def _check_partials_and_empty_folders(config: Config) -> None:
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
