from typing import Literal

from cyclopts.types import ExistingDirectory, ExistingFile


async def compute_hashes(
    folder: ExistingDirectory,
    /,
    *,
    database_file: ExistingFile | None = None,
    hashes: tuple[Literal["xxh128", "md5", "sha256"], ...] = ("xxh128", "md5", "sha256"),
) -> None:
    """Compute and save hashes of every file inside `folder` (recursively)"""

    from cyberdrop_dl import stats
    from cyberdrop_dl.config.appdata import AppData
    from cyberdrop_dl.database import Database
    from cyberdrop_dl.hasher import Hasher, hash_directory

    folder = folder.expanduser().resolve().absolute()
    database = Database(database_file or AppData.default().db_file)
    extra_hashes = set(hashes)
    extra_hashes.discard("xxh128")
    hasher = Hasher(tuple(extra_hashes), database, folder)  # pyright: ignore[reportArgumentType]
    hash_stats = await hash_directory(hasher)
    stats.print(hash_stats)
