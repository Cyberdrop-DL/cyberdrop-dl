from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest
import yaml
from cyclopts.exceptions import UnknownOptionError
from pydantic import BaseModel

import cyberdrop_dl.cli.download
from cyberdrop_dl.config import Config, Files, _resolve_paths, merge_additive_args, settings
from cyberdrop_dl.config.appdata import AppData
from cyberdrop_dl.config.auth import Authentication, Notifications
from cyberdrop_dl.exceptions import CDLConfigRuntimeErrorsGroup
from cyberdrop_dl.models import AppriseURL, merge_dicts


def test_config_equality() -> None:
    config1 = Config()
    time.sleep(0.1)
    config2 = Config()
    assert config1.__dict__ == config2.__dict__
    assert config1 == config2
    assert config1.model_dump() == config2.model_dump()
    config1.resolve_paths()
    config2.resolve_paths()
    assert config1 == config2
    assert config1.model_dump() == config2.model_dump()


def test_parse_config_from_args() -> None:
    assert Config() == Config.parse_args([])


def test_parse_config_from_args2() -> None:
    config = Config.model_validate({"download_folder": "downloads"})
    assert config == Config.parse_args(["--download-folder", "downloads"])
    assert config == Config.parse_args(["-o", "downloads"])
    with pytest.raises(UnknownOptionError):
        _ = Config.parse_args(["-i", "test.txt"])


def test_logs_equality() -> None:
    logs1 = settings.Logs()
    time.sleep(0.1)
    logs2 = settings.Logs()
    assert logs1._created_at != logs2._created_at
    assert logs1.__dict__ == logs2.__dict__
    assert logs1 == logs2


class TestMergeDicts:
    def test_overwrite(self) -> None:
        dict1 = {"a": 1, "b": 2}
        dict2 = {"b": 3, "c": 4}
        expected = {"a": 1, "b": 3, "c": 4}
        assert merge_dicts(dict1, dict2) == expected

    def test_merge_with_new_keys(self) -> None:
        dict1 = {"a": 1}
        dict2 = {"b": 2, "c": 3}
        expected = {"a": 1, "b": 2, "c": 3}
        assert merge_dicts(dict1, dict2) == expected

    def test_merge_recursive(self) -> None:
        dict1 = {
            "a": {
                "b": 1,
                "c": 2,
            },
            "d": 3,
        }
        dict2 = {
            "a": {
                "b": 4,
                "e": 4,
                "f": {
                    "g": 5,
                    "h": 6,
                },
            },
            "i": 7,
        }
        expected = {
            "a": {
                "b": 4,
                "c": 2,
                "e": 4,
                "f": {
                    "g": 5,
                    "h": 6,
                },
            },
            "d": 3,
            "i": 7,
        }
        assert merge_dicts(dict1, dict2) == expected

    def test_merge_with_empty_dict1(self) -> None:
        dict1 = {}
        dict2 = {"a": 1, "b": 2}
        expected = {"a": 1, "b": 2}
        assert merge_dicts(dict1, dict2) == expected

    def test_merge_with_empty_dict2(self) -> None:
        dict1 = {"a": 1, "b": 2}
        dict2 = {}
        expected = {"a": 1, "b": 2}
        assert merge_dicts(dict1, dict2) == expected

    def test_merge_with_both_empty_dicts(self) -> None:
        dict1 = {}
        dict2 = {}
        expected = {}
        assert merge_dicts(dict1, dict2) == expected

    def test_dict_overwrites_value(self) -> None:
        dict1 = {"a": 1}
        dict2 = {"a": {"x": 1}}
        expected = {"a": {"x": 1}}
        assert merge_dicts(dict1, dict2) == expected

    def test_value_should_not_overwrite_dict(self) -> None:
        dict1 = {"a": {"x": 1}}
        dict2 = {"a": 1}
        expected = {"a": {"x": 1}}
        assert merge_dicts(dict1, dict2) == expected


class TestRuntimeLogsConfig:
    @staticmethod
    def parse(level: object, console_level: object) -> settings.Logs:
        return settings.Logs.model_validate({"level": level, "console_level": console_level})

    def test_default(self) -> None:
        default = settings.Logs()
        expected = settings.Logs(level="debug", console_level="debug")  # pyright: ignore[reportArgumentType]

        assert default.effective_level == 10
        assert default.effective_console_level == 10
        assert default.effective_level == expected.effective_level
        assert default.effective_console_level == expected.effective_console_level

    def test_falsy_console_log_level(self) -> None:
        for name, level, console_level in [("warning", 30, None), ("error", 40, ""), ("info", 20, "none")]:
            logs = self.parse(name, console_level)
            assert logs.level == name.upper()
            assert logs.console_level is None
            assert logs.effective_level == level
            assert logs.effective_console_level == level


def test_default_config_does_not_need_ffmpeg() -> None:
    cyberdrop_dl.cli.download._check_ffmpeg(Config())


def test_media_durations_need_ffmpeg() -> None:
    config = Config.parse_args(["--video.duration.max", "20 seconds"])
    duration = config.filters.duration.video.max
    assert duration
    assert duration.total_seconds() == 20
    assert config.filters.duration.needs_ffmpeg
    with pytest.raises(CDLConfigRuntimeErrorsGroup) as exc:
        cyberdrop_dl.cli.download._check_ffmpeg(config)

    assert len(exc.value.exceptions) == 1
    assert type(exc.value.exceptions[0]) is RuntimeError
    assert str(exc.value.exceptions[0]) == "Filtering files by duration requires 'ffmpeg' to be installed"


def test_resolve_paths(tmp_cwd: Path) -> None:

    class SubConfig(BaseModel):
        path: Path

    class FakeConfig(BaseModel):
        name: str
        child: SubConfig

    config = FakeConfig(
        name="foo",
        child=SubConfig(
            path=Path("/home/user/cdl/{config}/settings.yml"),
        ),
    )

    with pytest.raises(CDLConfigRuntimeErrorsGroup, match="Invalid config") as exc_info:
        _resolve_paths(config)

    assert len(exc_info.value.exceptions) == 1
    first = exc_info.value.exceptions[0]
    assert type(first) is ValueError
    assert "Using '{config}' as reference on a path is no longer supported" in str(first)

    config.child.path = Path("URLs.txt")
    _resolve_paths(config)
    assert config.child.path == tmp_cwd / "URLs.txt"


@pytest.mark.parametrize(
    ("config_args", "cli_args", "expected"),
    [
        (
            [],
            ["a", "b", "c"],
            ["a", "b", "c"],
        ),
        (
            ("e"),
            ("a", "b", "c"),
            ("a", "b", "c"),
        ),
        (
            ("b", "d", "e"),
            ("+", "a", "b", "c"),
            ("a", "b", "c", "d", "e"),
        ),
        (
            ("a", "d", "e"),
            ("-", "a", "b", "c"),
            ("d", "e"),
        ),
        (
            ("drive.google.com", "facebook.com", "youtube.com"),
            ("instagram.com",),
            ("instagram.com",),
        ),
        (
            ("drive.google.com", "facebook.com", "youtube.com"),
            ("+", "instagram.com"),
            ("drive.google.com", "facebook.com", "instagram.com", "youtube.com"),
        ),
        (
            ("drive.google.com", "facebook.com", "youtube.com"),
            ("-", "youtube.com"),
            ("drive.google.com", "facebook.com"),
        ),
    ],
)
def test_additive_args(
    config_args: list[str] | tuple[str, ...],
    cli_args: list[str] | tuple[str, ...],
    expected: list[str] | tuple[str, ...],
) -> None:
    result = merge_additive_args(cli_args, config_args)
    assert type(result) is type(expected)
    assert result == expected


def test_config_from_file(tmp_cwd: Path) -> None:
    config_file = tmp_cwd / "cdl_config.txt"
    config_1 = Config.from_file(config_file)
    assert config_1.source is None
    config_file.touch()
    config_2 = Config.from_file(config_file)
    assert config_2.source == config_file
    config_2._source = None
    assert config_1 == config_2


@pytest.mark.skipif(os.name == "nt", reason="pydantic can't generate schema w pathlib.WindowsPath defaults")
def test_schema_has_not_changed() -> None:
    schema = Config.model_json_schema()
    expected_schema = json.loads(Files.SCHEMA.read_text())
    assert schema == expected_schema, "Validation schema changed"


def test_round_trip_parsed_the_same_config() -> None:
    config = Config()
    for mode in ("python", "json"):
        new_config = Config.model_validate(config.model_dump(mode=mode))
        assert vars(new_config) == vars(config)
        assert new_config == config


@pytest.mark.skipif(os.name == "nt", reason="OS separators make paths different on Windows")
def test_config_default_has_not_changed() -> None:
    config = Config().model_dump(mode="json")
    expected = yaml.safe_load(Files.DEFAULT.read_text())
    assert config == expected, "Config serialization changed"


def test_config_can_be_serialized_as_json() -> None:
    Config().model_dump_json()


def test_config_defaults_are_valid() -> None:
    class StrictConfig(Config, validate_default=True, validation_error_cause=True): ...

    StrictConfig()


class TestCensoredConfig:
    def test_auth_is_censored_on_repr(self) -> None:
        api_key = "my_api_key"
        auth = Authentication.model_validate({"gofile": {"api_key": api_key}})
        assert api_key not in repr(auth)
        assert auth.gofile.api_key == api_key
        assert auth.model_dump()["gofile"]["api_key"] == api_key
        assert auth.censored_dump()["gofile"] is True
        assert auth.model_dump(mode="json")["gofile"]["api_key"] == api_key

    def test_apprise_urls_are_censored(self) -> None:
        url = AppriseURL.model_validate({"url": "https://example.com/a"})
        assert str(url) == "no_logs=https://example.com/a"
        assert repr(url) == "AppriseURL(url=Secret('**********'), tags={'no_logs'})"
        assert url.model_dump() == "no_logs=https://example.com/a"
        assert url.model_dump(mode="json") == "no_logs=**********"

    def test_notifications_are_censored(self) -> None:
        url = AppriseURL.model_validate({"url": "https://example.com/a"})
        noti = Notifications(apprise=(url,))
        assert "example.com" not in repr(noti)
        assert "example.com" not in str(noti)


class TestAppData:
    def test_default_names(self) -> None:
        appdata = AppData.default()
        assert appdata.cache_file.name == "cache.json"
        assert appdata.db_file.name == "cyberdrop.db"
        assert appdata.config_file.name == "config.yaml"

    def test_default_log_folder_name(self) -> None:
        appdata = AppData.default()
        assert appdata.logs_folder.name == "Logs" if os.name == "nt" else "logs"

    def test_create_w_no_args_is_default(self) -> None:
        assert AppData.create() == AppData.default()


def test_log_folder_after_resolution(tmp_cwd: Path) -> None:
    logs = settings.Logs()
    assert logs.folder is None
    tmp_log_folder = tmp_cwd / "logs"
    logs.resolve_filenames(tmp_log_folder)
    assert logs.folder == tmp_log_folder
