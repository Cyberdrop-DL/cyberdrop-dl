from pathlib import Path

import pytest
from cyclopts import App
from cyclopts.exceptions import ValidationError

from cyberdrop_dl import __version__
from cyberdrop_dl.__main__ import run_cdl
from cyberdrop_dl.commands import CLIarguments
from cyberdrop_dl.commands.report import generate_report
from cyberdrop_dl.config import Config

app = App(result_action="return_value", exit_on_error=False, suppress_keyboard_interrupt=False)


@app.default()
def parse_cli_args(*, cli: CLIarguments | None = None) -> CLIarguments | None:
    return cli


@pytest.mark.parametrize(
    ("command", "text"),
    [
        ("--help", "Bulk asynchronous downloader for multiple file hosts"),
        ("show", "cyberdrop-dl supported sites"),
    ],
)
def test_command_by_console_output(capsys: pytest.CaptureFixture[str], command: str, text: str) -> None:
    try:
        run_cdl(command.split())
    except SystemExit:
        pass
    output = capsys.readouterr().out
    assert text in output


def test_report() -> None:
    report = generate_report()

    for value in "cyberdrop-dl", __version__, "aiohttp", "GIL enabled":
        assert value in report


def test_cli_args_parsing(tmp_cwd: Path) -> None:
    cli = app([])
    assert cli is None
    config_yaml = Path("test_file.yaml")

    with pytest.raises(ValidationError, match="does not exist"):
        _ = app(["--config-file", config_yaml.name])

    config_text = config_yaml.with_suffix(".txt")
    config_text.touch()
    with pytest.raises(ValidationError, match='does not match one of supported extensions \\{"yaml", "yml"\\}'):
        _ = app(["--config-file", config_text.name])

    config_yaml.touch()
    config_yaml = config_yaml.with_suffix(".yaml")
    cli = app(["--config-file", config_yaml.name])
    assert type(cli) is CLIarguments
    assert cli.config_file == tmp_cwd / config_yaml
    assert cli.database_file is None
    assert cli.cache_file is None


def test_custom_bool_parsing() -> None:
    config = Config.parse_args("--jdownloader")
    assert config.jdownloader.enabled
    config = Config.parse_args("--no-jdownloader")
    assert not config.jdownloader.enabled
    config = Config.parse_args("--jdownloader.no-enabled")
    assert not config.jdownloader.enabled
    config = Config.parse_args("--sort")
    assert config.sort.enabled
    config = Config.parse_args("--no-sort")
    assert not config.sort.enabled
