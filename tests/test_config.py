from __future__ import annotations

import time

import pytest
from cyclopts.exceptions import UnknownOptionError

from cyberdrop_dl.config import Config, settings
from cyberdrop_dl.config.merge import merge_dicts


def test_config_equality():
    config1 = Config()
    time.sleep(0.1)
    config2 = Config()
    assert config1.__dict__ == config2.__dict__
    assert config1 == config2
    assert config1.model_dump() == config2.model_dump()
    config1.settings.resolve_paths()
    config2.settings.resolve_paths()
    assert config1 == config2
    assert config1.model_dump() == config2.model_dump()


def test_parse_config_from_args():
    assert Config() == Config.parse_args([])


def test_parse_config_from_args2():
    config = Config.model_validate(
        {
            "settings": {
                "files": {
                    "input_file": "test.txt",
                }
            }
        }
    )
    assert config == Config.parse_args(["--input-file", "test.txt"])
    assert config == Config.parse_args(["-i", "test.txt"])
    with pytest.raises(UnknownOptionError):
        _ = Config.parse_args(["--i", "test.txt"])


def test_logs_equality():
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
    def parse(level: object, console_level: object):
        return settings.RuntimeOptions.model_validate({"log_level": level, "console_log_level": console_level})

    def test_default(self) -> None:
        default = settings.RuntimeOptions()
        expected = settings.RuntimeOptions(log_level="debug", console_log_level="debug")  # pyright: ignore[reportArgumentType]

        assert default.effective_log_level == 10
        assert default.effective_console_log_level == 10
        assert default.effective_log_level == expected.effective_log_level
        assert default.effective_console_log_level == expected.effective_console_log_level

    def test_falsy_console_log_level(self) -> None:
        for a, b in [(30, None), (40, ""), (20, "none")]:
            config = self.parse(a, b)
            assert config.effective_log_level == a
            assert config.effective_console_log_level == a
