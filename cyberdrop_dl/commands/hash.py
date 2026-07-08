from typing import Literal

from cyclopts.types import ResolvedExistingDirectory

from cyberdrop_dl.commands import CLIarguments
from cyberdrop_dl.commands._compat import check_for_v9_files
from cyberdrop_dl.config import Config


async def compute_hashes(
    folder: ResolvedExistingDirectory,
    /,
    *,
    hashes: tuple[Literal["xxh128", "md5", "sha256"], ...] | None = None,
    cli: CLIarguments | None = None,
) -> None:
    """Compute and save hashes of every file in a folder (recursively)"""
    check_for_v9_files()
    from cyberdrop_dl import stats
    from cyberdrop_dl.config.appdata import AppData
    from cyberdrop_dl.database import Database
    from cyberdrop_dl.hasher import Hasher, hash_directory

    db_file = cli.database_file if cli else None
    extra_hashes = _choose_hash_algos(hashes, cli)
    database = Database(db_file or AppData.default().db_file)
    hasher = Hasher(extra_hashes, database, folder)  # pyright: ignore[reportArgumentType]
    hash_stats = await hash_directory(hasher)
    stats.print(hash_stats)


def _choose_hash_algos(
    hashes: tuple[Literal["xxh128", "md5", "sha256"], ...] | None,
    cli: CLIarguments | None = None,
) -> tuple[str, ...]:
    if hashes:
        return tuple(set(hashes) - {"xxh128"})
    if cli and cli.config_file:
        return Config.from_file(cli.config_file).hashing.extra_hashes
    return "md5", "sha256"
