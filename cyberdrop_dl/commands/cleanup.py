import logging
from typing import Annotated

from cyclopts import App, Parameter
from cyclopts.types import ResolvedExistingDirectory

app = App(name="cleanup", help="Perform maintenance tasks")
logger = logging.getLogger(__name__)


@app.command()
def files(
    path: Annotated[
        ResolvedExistingDirectory,
        Parameter(help="Path of the folder to clean up"),
    ],
    /,
) -> None:
    """Delete partial (`.cdl_hls` and `.part`) files, empty folders and empty files inside `path` (recursive)"""
    from cyberdrop_dl.utils import cleanup

    logger.info("Deleting partial downloads...")
    cleanup.rm_partial_files(path)
    logger.info("Deleting empty files and folders...")
    cleanup.rm_empty_dirs(path)
    logger.info("DONE!", extra={"color": "green"})
