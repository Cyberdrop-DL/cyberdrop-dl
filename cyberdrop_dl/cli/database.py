from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter, validators

app = App(name="database", help="Commands for managing the database")


@app.command()
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
    from cyberdrop_dl.database.transfer import run as transfer_db

    transfer_db(db_path, force=force)
