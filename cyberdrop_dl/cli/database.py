from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter, validators

from cyberdrop_dl.cli import app
from cyberdrop_dl.database.transfer import run as transfer_db

database_app = App(name="database", help="Commands for managing the database")


@database_app.command()
def transfer(
    db_path: Annotated[
        Path,
        Parameter(
            help="Path to the SQLite database file to migrate",
            validator=validators.Path(exists=True, file_okay=True, dir_okay=False, ext=".db"),
        ),
    ],
    force: Annotated[
        bool,
        Parameter(
            help="Skip the 'already latest' early-exit check and run all migration steps regardless of detected version"
        ),
    ] = False,
) -> None:
    """Migrate an old database to the latest schema version."""
    transfer_db(db_path, force=force)


app.command(database_app, "database")
