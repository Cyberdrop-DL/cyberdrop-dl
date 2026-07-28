import logging

from cyclopts import App
from cyclopts.help import DefaultFormatter

from cyberdrop_dl import __version__
from cyberdrop_dl.constants import DEFAULT_PARAMETER
from cyberdrop_dl.logs import setup_console_logging

logger = logging.getLogger("cyberdrop_dl")

app = App(
    name="cyberdrop-dl crawler tester",
    version=__version__,
    default_parameter=DEFAULT_PARAMETER,
    help_format="rich",
    result_action="return_value",
    help_formatter=DefaultFormatter().with_newline_metadata(),  # pyright: ignore[reportUnknownMemberType]
)


def _cases():
    logger.info("Loading test cases ...")
    from tests.crawlers.test_crawlers import test_cases

    return test_cases


def _crawlers():
    logger.info("Importing crawlers ...")
    from cyberdrop_dl.crawlers import Registry

    return Registry.get_crawlers()


@app.command(name="list")
def list_cases() -> None:
    "Show a map with all existing test cases"

    all_cases = sorted(_cases().load_cases().items())
    cases = {domain: len(module.cases) for domain, module in all_cases}
    app.console.print(cases)
    app.console.print("Domains:", len(cases), " Cases:", sum(cases.values()))


@app.command
def missing() -> None:
    "Show a list a crawlers with 0 test cases"

    crawlers = tuple(_crawlers())
    test_domains = set(_cases().load_cases())
    missing = sorted(c.__module__ for c in crawlers if c.DOMAIN not in test_domains)
    app.console.print(missing)
    app.console.print(f"Total: {len(missing)} ({100 * len(missing) / len(crawlers):0.2f} %)")


@app.command
def orphan() -> None:
    "Show a list of test cases that match with no crawler"

    domains = {c.DOMAIN for c in _crawlers()}
    test_modules = set(_cases().load_modules())
    orphan = dict(sorted((m.domain, m.file) for m in test_modules if m.domain not in domains))
    app.console.print(orphan)
    app.console.print(f"Total: {len(orphan)}")


if __name__ == "__main__":
    with setup_console_logging():
        app()
