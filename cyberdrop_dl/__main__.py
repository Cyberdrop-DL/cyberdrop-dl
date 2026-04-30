# ruff: noqa: E402
import logging
import sys
from collections.abc import Sequence
from typing import Annotated

from cyclopts import App, CycloptsPanel, Parameter

from cyberdrop_dl import __version__, aio, program_ui, tracebacks, webhook

tracebacks.install_exception_hook()

from cyberdrop_dl.cli import CLIargs
from cyberdrop_dl.config import Config
from cyberdrop_dl.logs import log_spacer, setup_console_logging, setup_file_logging
from cyberdrop_dl.managers.manager import AppData, Manager
from cyberdrop_dl.models.types import HttpURL
from cyberdrop_dl.progress import REFRESH_RATE, TUI_DISABLED
from cyberdrop_dl.scrape_mapper import ScrapeMapper
from cyberdrop_dl.sorter import Sorter
from cyberdrop_dl.updates import check_latest_pypi
from cyberdrop_dl.utils import apprise, check_partials_and_empty_folders

logger = logging.getLogger("cyberdrop_dl")


async def _scrape(manager: Manager) -> None:
    with setup_file_logging(manager.config.settings.logs.main_log):
        await manager.async_startup()
        REFRESH_RATE.set(manager.config.global_settings.ui_options.refresh_rate)
        TUI_DISABLED.set(manager.cli_args.ui.is_disabled)

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
            async with manager.client_manager.create_aiohttp_session() as session:
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
    logger.info("Running Post-Download Processes\n ", extra={"color": "green"})

    await manager.hasher.cleanup_dupes_after_download()

    if manager.config.settings.sorting.sort_downloads and not manager.cli_args.retry_any:
        sorter = Sorter.from_manager(manager)
        await sorter.run()

    check_partials_and_empty_folders(manager)

    if manager.config.settings.runtime_options.update_last_forum_post:
        await manager.logs.update_last_forum_post(manager.config.settings.files.input_file)


def _main(manager: Manager) -> None:
    manager.resolve_paths()
    if not manager.cli_args.download:
        program_ui.run(manager)

    try:
        aio.run(_scrape(manager))

    except KeyboardInterrupt:
        logger.info("Exiting (Ctrl + C) ...")


app = App(
    name="cyberdrop-dl",
    help="Bulk asynchronous downloader for multiple file hosts",
    version=__version__,
    default_parameter=Parameter(negative_iterable=[]),
    result_action="return_value",
)


@app.default()
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


@app.command()
def show() -> None:
    """Show a list of all supported sites"""
    from cyberdrop_dl import supported_sites

    table = supported_sites.as_rich_table()
    app.console.print(table)


def main(args: Sequence[str] | None = None) -> None:
    with setup_console_logging():
        try:
            app(args)
        except* ValueError as exc_group:
            msg = "\n" + "\n".join(map(str, exc_group.exceptions))
            app.console.print(CycloptsPanel(msg, title=exc_group.message))


if __name__ == "__main__":
    sys.exit(main())
