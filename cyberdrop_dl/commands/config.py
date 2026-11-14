import logging
from typing import Any

from cyclopts import App

from cyberdrop_dl.commands import CLIarguments, open_folder
from cyberdrop_dl.config import Config
from cyberdrop_dl.config.appdata import AppData
from cyberdrop_dl.prompts import ask_should_create_config

app = App(name="config", help="Config file operations")
logger = logging.getLogger(__name__)


@app.command()
def file(*, cli: CLIarguments | None = None) -> None:
    "Show path to the config file"
    file = (cli and cli.config_file) or AppData.default().config_file
    app.console.print(file)


@app.command()
def edit(*, cli: CLIarguments | None = None) -> None:
    "Open the default config file on a text editor"
    from cyberdrop_dl.utils import text_editor

    file = cli and cli.config_file
    if not file:
        file = AppData.default().config_file
        if not file.exists():
            if not ask_should_create_config(file):
                return
            Config().save_to(file)

    text_editor.open(file)


@app.command()
def fill(*, cli: CLIarguments | None = None) -> None:
    """Add missing settings to the config file with their default values (comments will be deleted)

    Settings from config overrides will be merged into the main config file"""

    file = (cli and cli.config_file) or AppData.default().config_file
    if not file.exists():
        logger.info("Config file '%s' does not exists. Nothing to do", file)
        return

    config = Config.from_file(file)
    new_keys, _ = _compare_dict_keys(config.model_dump(mode="json", exclude_unset=True), config.model_dump(mode="json"))
    if not new_keys:
        logger.info("Config '%s' is up to date. Nothing to do", file)
        return

    config.save_to(file)
    for key in new_keys:
        logger.info("Added '%s' to config", key)


def _compare_dict_keys(dict1: dict[str, Any], dict2: dict[str, Any], prefix: str = ""):
    missing_in_dict2: list[str] = []
    missing_in_dict1: list[str] = []

    for key in dict.fromkeys((*dict1, *dict2)):
        path = f"{prefix}.{key}" if prefix else str(key)

        if key not in dict1:
            missing_in_dict1.append(path)
        elif key not in dict2:
            missing_in_dict2.append(path)
        elif isinstance(dict1[key], dict) and isinstance(dict2[key], dict):
            missing1, missing2 = _compare_dict_keys(dict1[key], dict2[key], path)
            missing_in_dict1.extend(missing1)
            missing_in_dict2.extend(missing2)

    return missing_in_dict1, missing_in_dict2


@app.command()
def new() -> None:
    "Create a new config with default options and print it"
    app.console.print(Config().dump_yaml(), soft_wrap=True)


@app.command(name="dir", alias="folder")
def folder(*, cli: CLIarguments | None = None) -> None:
    "Open folder with config file in default file explorer"
    file = (cli and cli.config_file) or AppData.default().config_file

    open_folder(file.parent)
