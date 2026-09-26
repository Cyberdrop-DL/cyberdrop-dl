from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from cyclopts import App, Parameter

from cyberdrop_dl.commands import CLIarguments, SQLiteFile, open_folder
from cyberdrop_dl.config.appdata import AppData

if TYPE_CHECKING:
    from cyberdrop_dl.database import Database
    from cyberdrop_dl.database.hash import PruneStats

app = App(name="database", help="Commands for managing the database")
prune_app = App(name="prune", help="Delete database entries that are no longer useful")
app.command(prune_app)


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


@prune_app.command()
def hashes(
    *,
    dry_run: Annotated[
        bool,
        Parameter(help="Report what would be deleted without modifying the database"),
    ] = False,
    cli: CLIarguments | None = None,
) -> None:
    """Delete the hashes of files that no longer exist on disk.

    Only affects the `hash` and `files` tables.
    """
    from cyberdrop_dl import aio, stats
    from cyberdrop_dl.database import Database

    db_file = (cli and cli.database_file) or AppData.default().db_file
    stats.print(aio.run(_prune_hashes(Database(db_file), dry_run=dry_run)))


async def _prune_hashes(database: Database, *, dry_run: bool) -> PruneStats:
    async with database:
        return await database.hash.prune_missing_files(dry_run=dry_run)


@app.command()
def file(*, cli: CLIarguments | None = None) -> None:
    "Show file path to the database"
    file = (cli and cli.database_file) or AppData.default().db_file
    app.console.print(file)


@app.command(name="dir", alias="folder")
def folder(*, cli: CLIarguments | None = None) -> None:
    "Open folder with database in default file explorer"
    file = (cli and cli.database_file) or AppData.default().db_file

    open_folder(file.parent)
