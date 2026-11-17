import logging

from cyclopts import App

from cyberdrop_dl.appdata import AppData
from cyberdrop_dl.commands import CLIarguments, open_folder

app = App(name="cache", help="Cache operations")
logger = logging.getLogger(__name__)


@app.command()
def file(*, cli: CLIarguments | None = None) -> None:
    "Show path to the cache file"
    file = (cli and cli.cache_file) or AppData.default().cache_file
    app.console.print(file)


@app.command()
def clear(*, cli: CLIarguments | None = None) -> None:
    "Delete the cache file"

    file = (cli and cli.cache_file) or AppData.default().cache_file
    try:
        file.unlink()
    except FileNotFoundError:
        logger.info("Cache file does not exists. Nothing to do")
    else:
        logger.info("Cache file at '%s' deleted", file)


@app.command(name="dir", alias="folder")
def folder(*, cli: CLIarguments | None = None) -> None:
    "Open folder with cache file in default file explorer"
    file = (cli and cli.cache_file) or AppData.default().cache_file

    open_folder(file.parent)
