from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Annotated

from cyclopts import Parameter

from cyberdrop_dl.cli import CLIargs
from cyberdrop_dl.config import Config
from cyberdrop_dl.exceptions import CDLConfigRuntimeErrorsGroup
from cyberdrop_dl.logs import log_spacer, set_console_level, setup_file_logging
from cyberdrop_dl.models.types import HttpURL  # noqa: TC001

logger = logging.getLogger("cyberdrop_dl")

if TYPE_CHECKING:
    from cyberdrop_dl.manager import Manager


async def _scrape(manager: Manager) -> None:
    from cyberdrop_dl import ffmpeg, webhook
    from cyberdrop_dl.scrape_mapper import ScrapeMapper
    from cyberdrop_dl.updates import check_latest_pypi
    from cyberdrop_dl.utils import apprise

    with setup_file_logging(
        manager.config.logs.main_log,
        level=manager.config.runtime.effective_log_level,
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

            if manager.config.logs.webhook:
                await webhook.send_notification(manager.config.logs.webhook, stats_summary)

            if manager.config.apprise_urls:
                await apprise.send_notifications(manager.config.apprise_urls, stats_summary)


async def _post_runtime(manager: Manager) -> None:
    """Actions to complete after main runtime, and before UI shutdown."""
    from cyberdrop_dl.utils import check_partials_and_empty_folders

    logger.info("Running Post-Download Processes\n", extra={"color": "green"})

    if (
        manager.config.dupe_cleanup.hashing.enabled
        and manager.config.dupe_cleanup.auto_dedupe
        and not manager.config.runtime.ignore_history
    ):
        file_hashes = await manager.hasher.run()
        await manager.deduper.run(file_hashes)

    if manager.config.sorting.sort_downloads:
        await manager.sorter.run()

    check_partials_and_empty_folders(manager.config)


def _main(manager: Manager) -> None:
    from cyberdrop_dl import aio, program_ui

    set_console_level(manager.config.runtime.effective_console_log_level)
    try:
        with manager():
            if not manager.cli_args.download:
                program_ui.run(manager)
            aio.run(_scrape(manager))

    except KeyboardInterrupt:
        logger.info("Exiting (Ctrl + C) ...")


def download(
    links: Annotated[
        tuple[HttpURL, ...],
        Parameter(
            help="link(s) to content to download (passing multiple links is supported)",
        ),
    ] = (),
    *,
    cli: CLIargs | None = None,
    config: Config | None = None,
) -> None:
    from cyberdrop_dl.manager import AppData, Manager

    cli = cli or CLIargs()
    cli.links = links
    config = config or Config()
    appdata = AppData.from_path(cli.appdata_folder) if cli.appdata_folder else AppData.default()

    config = Config.create(appdata, cli.config_file).update(config)

    if not cli.fullscreen_ui or cli.config_file or config.sorting.sort_downloads:
        cli.download = True

    manager = Manager(cli, appdata, config)

    _main(manager)


def _check_ffmpeg(config: Config) -> None:
    errors: list[Exception] = []
    if config.sorting.needs_ffmpeg:
        exc = RuntimeError("Sorting media files requires 'ffmpeg' to be installed")
        exc.add_note("Disable sorting or install ffmpeg")
        errors.append(exc)

    if config.media_duration_limits.needs_ffmpeg:
        exc = RuntimeError("Filtering files by duration requires 'ffmpeg' to be installed")
        exc.add_note("Disable media duration limits or install ffmpeg")
        errors.append(exc)

    if errors:
        raise CDLConfigRuntimeErrorsGroup("Some config options are impossible to fulfill", errors)
