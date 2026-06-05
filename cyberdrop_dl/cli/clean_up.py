import logging
from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter, validators

app = App(name="cleanup", help="Perform maintenance tasks")
logger = logging.getLogger(__name__)


@app.command()
def files(
    path: Annotated[
        Path,
        Parameter(
            help="Path of the folder to clean up",
            validator=validators.Path(exists=True, file_okay=False, dir_okay=True),
        ),
    ],
    /,
) -> None:
    """Delete partial (`.cdl_hls` and `.part`) files, empty folders and empty files inside `dir` (recursive)"""

    from cyberdrop_dl.utils import delete_empty_files_and_folders, delete_partial_files

    path = path.expanduser().resolve().absolute()
    logger.info("Deleting partial downloads...")
    delete_partial_files(path)
    logger.info("Deleting empty files and folders...")
    delete_empty_files_and_folders(path)
    logger.info("DONE!", extra={"color": "green"})
