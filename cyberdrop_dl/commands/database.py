from typing import Annotated

from cyclopts import App, Parameter

from cyberdrop_dl.commands import CLIarguments, SQLiteFile
from cyberdrop_dl.config.appdata import AppData

app = App(name="database", help="Commands for managing the database")


@app.command()
def transfer(
    database_file: Annotated[
        SQLiteFile,
        Parameter(help="Path to the SQLite database file to migrate"),
    ],
    *,
    force: Annotated[
        bool,
        Parameter(
            help="Skip the 'already latest' early-exit check and run all migration steps regardless of detected version"
        ),
    ] = False,
) -> None:
    """Migrate an old database to the latest schema version."""
    from cyberdrop_dl.database.transfer import run as transfer_db

    transfer_db(database_file, force=force)


@app.command()
def file(*, cli: CLIarguments | None = None) -> None:
    "Show file path to the database"
    app.console.print(cli.database_file if cli else AppData.default().db_file)
