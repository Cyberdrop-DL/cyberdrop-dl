from __future__ import annotations

import functools
import logging
from typing import TYPE_CHECKING

from cyberdrop_dl.logs import log_spacer
from cyberdrop_dl.progress.dedupe import DedupeStats
from cyberdrop_dl.progress.hashing import HashingStats
from cyberdrop_dl.progress.scraping.errors import ScrapeErrorsPanel
from cyberdrop_dl.progress.scraping.files import FileStats
from cyberdrop_dl.progress.sorting import SortStats

if TYPE_CHECKING:
    from collections.abc import Sequence

    from cyberdrop_dl.progress.scraping.errors import UIError


logger = logging.getLogger(__name__)


@functools.singledispatch
def print(stats: object) -> None:
    raise NotImplementedError(f"Unable to print stats for {stats!r}")


@print.register
def _(stats: SortStats) -> None:
    log_spacer()
    logger.info("Sort Stats:", extra={"color": "cyan"})
    logger.info(f"  Audios: {stats.audios:,}")
    logger.info(f"  Images: {stats.images:,}")
    logger.info(f"  Videos: {stats.videos:,}")
    logger.info(f"  Other files: {stats.others:,}")


@print.register
def _(stats: HashingStats) -> None:
    log_spacer()
    logger.info("Checksum Stats:", extra={"color": "cyan"})
    logger.info(f"  Newly hashed: {stats.new_hashed:,} files")
    logger.info(f"  Previously hashed: {stats.prev_hashed:,} files")


@print.register
def _(stats: DedupeStats) -> None:
    log_spacer()
    logger.info("Dedupe Stats:", extra={"color": "cyan"})
    logger.info(f"  Deleted (duplicates of previous downloads): {stats.deleted:,} files")
    logger.info(f"  Errors: {stats.total - stats.deleted:,} files")


@print.register
def _(stats: FileStats) -> None:
    log_spacer()
    logger.info("Download Stats:", extra={"color": "cyan"})
    logger.info(f"  Downloaded: {stats.completed:,} files")
    logger.info(f"  Skipped (by config): {stats.skipped:,} files")
    logger.info(f"  Skipped (previously downloaded): {stats.previously_completed:,} files")
    logger.info(f"  Failed: {stats.failed:,} files")


@print.register
def _(stats: ScrapeErrorsPanel) -> None:
    log_spacer()
    logger.info("Unsupported URLs Stats:", extra={"color": "cyan"})
    logger.info(f"  Sent to Jdownloader: {stats.sent_to_jdownloader:,}")
    logger.info(f"  Skipped: {stats.skipped:,}")


def print_errors(scrape_errors: Sequence[UIError], download_errors: Sequence[UIError]) -> None:
    error_codes = (error.code for error in (*scrape_errors, *download_errors) if error.code is not None)

    try:
        padding = len(str(max(error_codes)))
    except ValueError:
        padding = 0

    for title, errors in (
        ("Scrape Errors:", scrape_errors),
        ("Download Errors:", download_errors),
    ):
        log_spacer()
        logger.info(title, extra={"color": "cyan"})
        if not errors:
            logger.info(f"  {'None':>{padding}}", extra={"color": "green"})
            continue

        for error in errors:
            logger.info(f"  {error.format(padding)}", extra={"color": "red"})
