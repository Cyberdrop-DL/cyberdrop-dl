from __future__ import annotations

from dataclasses import field
from time import sleep
from typing import TYPE_CHECKING, Any

from cyberdrop_dl.config import AuthSettings, ConfigSettings, GlobalSettings
from cyberdrop_dl.managers.log_manager import LogManager
from cyberdrop_dl.utils import yaml
from cyberdrop_dl.utils.apprise import get_apprise_urls

if TYPE_CHECKING:
    from pathlib import Path

    from pydantic import BaseModel

    from cyberdrop_dl.managers.manager import Manager
    from cyberdrop_dl.utils.apprise import AppriseURL


class ConfigManager:
    def __init__(self, manager: Manager) -> None:
        self.manager = manager
        self.deep_scrape: bool = False
        self.apprise_urls: list[AppriseURL] = []

        self.authentication_data: AuthSettings = field(init=False)
        self.settings_data: ConfigSettings = field(init=False)
        self.global_settings_data: GlobalSettings = field(init=False)

        config_folder = self.manager.path_manager.config_folder

        self._loaded_config: str = self.manager.parsed_args.cli_only_args.config or self.get_default_config()

        self.settings: Path = config_folder / self.loaded_config / "settings.yaml"
        self.global_settings: Path = config_folder / "global_settings.yaml"
        self.authentication_settings: Path = config_folder / "authentication.yaml"
        auth_override = config_folder / self.loaded_config / "authentication.yaml"

        if auth_override.is_file():
            self.authentication_settings = auth_override

        self.settings.parent.mkdir(parents=True, exist_ok=True)
        self.pydantic_config: str | None = self.manager.cache_manager.get("pydantic_config")
        self._load_configs()

    @property
    def loaded_config(self) -> str:
        return self._loaded_config

    def get_default_config(self) -> str:
        return self.manager.cache_manager.get("default_config") or "Default"

    def _load_configs(self) -> None:
        """Loads all the configs."""
        self._load_authentication_config()
        self._load_global_settings_config()
        self._load_settings_config()
        apprise_file = self.manager.path_manager.config_folder / self.loaded_config / "apprise.txt"
        self.apprise_urls = get_apprise_urls(file=apprise_file)

    @staticmethod
    def _get_model_fields(model: BaseModel, *, exclude_unset: bool = True) -> set[str]:
        fields = set()
        default_dict: dict[str, Any] = model.model_dump(exclude_unset=exclude_unset)
        for submodel_name, submodel in default_dict.items():
            for field_name in submodel:
                fields.add(f"{submodel_name}.{field_name}")
        return fields

    def _load_authentication_config(self) -> None:
        """Verifies the authentication config file and creates it if it doesn't exist."""

        if self.authentication_settings.is_file():
            self.authentication_data = AuthSettings.model_validate(yaml.load(self.authentication_settings))
            set_fields = self._get_model_fields(self.authentication_data)
            posible_fields = self._get_model_fields(AuthSettings(), exclude_unset=False)
            if posible_fields == set_fields:
                return

        else:
            self.authentication_data = AuthSettings()

        yaml.save(self.authentication_settings, self.authentication_data)

    def _load_settings_config(self) -> None:
        """Verifies the settings config file and creates it if it doesn't exist."""

        if self.manager.parsed_args.cli_only_args.config_file:
            self.settings = self.manager.parsed_args.cli_only_args.config_file
            self._loaded_config = "CLI-Arg Specified"

        if self.settings.is_file():
            self.settings_data = ConfigSettings.model_validate(yaml.load(self.settings))
            set_fields = self._get_model_fields(self.settings_data)
            self.deep_scrape = self.settings_data.runtime_options.deep_scrape
            self.settings_data.runtime_options.deep_scrape = False
            posible_fields = self._get_model_fields(ConfigSettings(), exclude_unset=False)
            if posible_fields == set_fields:
                return
        else:
            self.settings_data = ConfigSettings()
            self.settings_data.files.input_file = (
                self.manager.path_manager.appdata / "Configs" / self.loaded_config / "URLs.txt"
            )
            downloads = self.manager.path_manager.cwd / "Downloads"
            self.settings_data.sorting.sort_folder = downloads / "Cyberdrop-DL Sorted Downloads"
            self.settings_data.files.download_folder = downloads / "Cyberdrop-DL Downloads"
            self.settings_data.logs.log_folder = (
                self.manager.path_manager.appdata / "Configs" / self.loaded_config / "Logs"
            )

        yaml.save(self.settings, self.settings_data)

    def _load_global_settings_config(self) -> None:
        """Verifies the global settings config file and creates it if it doesn't exist."""

        if self.global_settings.is_file():
            self.global_settings_data = GlobalSettings.model_validate(yaml.load(self.global_settings))
            set_fields = self._get_model_fields(self.global_settings_data)
            posible_fields = self._get_model_fields(GlobalSettings(), exclude_unset=False)
            if posible_fields == set_fields:
                return

        else:
            self.global_settings_data = GlobalSettings()

        yaml.save(self.global_settings, self.global_settings_data)

    """~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"""

    def write_updated_settings_config(self) -> None:
        """Write updated settings data."""
        yaml.save(self.settings, self.settings_data)

    def write_updated_global_settings_config(self) -> None:
        """Write updated global settings data."""
        yaml.save(self.global_settings, self.global_settings_data)

    """~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"""

    def reload_config(self, config_name: str) -> None:
        """Changes the config."""
        self._loaded_config = config_name

        self.manager.path_manager.startup()
        sleep(1)
        self.manager.log_manager = LogManager(self.manager)
        sleep(1)
