import logging
import time
from pathlib import Path

from cyberdrop_dl.config.appdata import AppData
from cyberdrop_dl.exceptions import CDLConfigRuntimeErrorsGroup

logger = logging.getLogger(__name__)


def _check_for_v9_database() -> None:
    db = Path("AppData/Cache/cyberdrop.db")
    if not db.exists():
        return

    default = AppData.default()
    msg = "\n".join(
        (
            "Found old database file at '%s'",
            "The default database location changed in v10",
            "Current default: '%s'",
            "",
        )
    )
    logger.warning(msg, db, default.db_file)

    from cyberdrop_dl.prompts import ask_confirmation

    if ask_confirmation("Do you want to move the database to the new default location?"):
        _move_database(db, default.db_file)
        return

    logger.warning("Ignoring database file at '%s'...", db)
    time.sleep(3)
    return


def _move_database(source: Path, dest: Path) -> None:
    if dest.exists():
        raise FileExistsError(f"A database file already exists at '{dest}'")

    import shutil

    dest.parent.mkdir(parents=True, exist_ok=True)
    _ = shutil.move(source, dest)
    logger.info("Database moved to '%s'", dest)
    time.sleep(3)


def _check_for_v9_settings() -> None:

    settings = Path("AppData/Configs/Default/settings.yaml")
    if not settings.exists():
        return

    default = AppData.default()
    msg = "\n".join(
        (
            "Found old config file at '%s'",
            "The default config location changed in v10",
            "Current default: '%s'",
            "",
        ),
    )
    logger.warning(msg, settings, default.config_file)
    msg = "\n".join(
        (
            "",
            "The config file schema changed on v10. Automatic migration is not supported",
            "Please read version 10.0.0 changelog for details on how to migrate your config",
            "or delete the old config to use v10 default settings",
        )
    )
    raise RuntimeError(msg)


def check_for_v9_files() -> None:
    try:
        _check_for_v9_database()
        _check_for_v9_settings()
    except (OSError, ValueError, RuntimeError) as e:
        raise CDLConfigRuntimeErrorsGroup("Migration Error", (e.with_traceback(None),)) from None
