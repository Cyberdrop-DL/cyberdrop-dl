import logging
from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter, validators

app = App(name="cleanup", help="Perform maintenance tasks")
logger = logging.getLogger(__name__)


@app.command()
def files(
    dir: Annotated[
        Path,
        Parameter(
            help="Path to dir to clean up",
            validator=validators.Path(exists=True, file_okay=False, dir_okay=True),
        ),
    ],
    /,
) -> None:
    """Delete partial (`.cdl_hls` and `.part`) files, empty folders and empty files inside `dir` (recursive)"""

    from cyberdrop_dl.utils import _partial_files, delete_empty_files_and_folders

    dir = dir.expanduser().resolve().absolute()
    logger.info("Deleting partial downloads...")
    for file in _partial_files(dir):
        try:
            file.unlink()
        except OSError as e:
            logger.error(f"Unable to delete '{file}' ({e!r})")
        else:
            logger.debug(f"Deleted '{file}'")

    logger.info("Deleting empty files and folders...")
    delete_empty_files_and_folders(dir)
    logger.info("DONE!", extra={"color": "green"})
