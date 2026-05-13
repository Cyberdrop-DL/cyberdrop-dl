from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Annotated

from cyclopts import Parameter

from cyberdrop_dl.cli import CLIargs
from cyberdrop_dl.config import Config
from cyberdrop_dl.logs import log_spacer, set_console_level, setup_file_logging
from cyberdrop_dl.models.types import HttpURL  # noqa: TC001

logger = logging.getLogger("cyberdrop_dl")

if TYPE_CHECKING:
    from cyberdrop_dl.manager import Manager


async def _scrape(manager: Manager) -> None:
    from cyberdrop_dl import webhook
    from cyberdrop_dl.scrape_mapper import ScrapeMapper
    from cyberdrop_dl.updates import check_latest_pypi
    from cyberdrop_dl.utils import apprise

    with setup_file_logging(
        manager.config.settings.logs.main_log,
        level=manager.config.settings.runtime_options.effective_log_level,
    ):
        manager.log_config_settings()
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

            if manager.config.settings.logs.webhook:
                await webhook.send_notification(manager.config.settings.logs.webhook, stats_summary)

            if manager.config.apprise_urls:
                await apprise.send_notifications(manager.config.apprise_urls, stats_summary)


async def _post_runtime(manager: Manager) -> None:
    """Actions to complete after main runtime, and before UI shutdown."""
    from cyberdrop_dl.utils import check_partials_and_empty_folders

    logger.info("Running Post-Download Processes\n", extra={"color": "green"})

    if (
        manager.config.settings.dupe_cleanup_options.hashing.enabled
        and manager.config.settings.dupe_cleanup_options.auto_dedupe
        and not manager.config.settings.runtime_options.ignore_history
    ):
        file_hashes = await manager.hasher.run()
        await manager.deduper.run(file_hashes)

    if manager.config.settings.sorting.sort_downloads and not manager.cli_args.retry_any:
        await manager.sorter.run()

    check_partials_and_empty_folders(manager)

    if manager.config.settings.runtime_options.update_last_forum_post:
        await manager.logs.update_last_forum_post(manager.config.settings.files.input_file)


def _main(manager: Manager) -> None:
    from cyberdrop_dl import aio, program_ui

    set_console_level(manager.config.settings.runtime_options.effective_console_log_level)
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
):
    from cyberdrop_dl.manager import AppData, Manager

    cli = cli or CLIargs()
    cli.links = links
    config = config or Config()
    appdata = AppData.from_path(cli.appdata_folder) if cli.appdata_folder else AppData.default()

    config = Config.create(appdata, cli.config_file).update(config)
    if cli.retry_all or cli.retry_maintenance:
        config.settings.runtime_options.ignore_history = True

    if not cli.fullscreen_ui or cli.retry_any or cli.config_file or config.settings.sorting.sort_downloads:
        cli.download = True

    manager = Manager(cli, appdata, config)

    _main(manager)
