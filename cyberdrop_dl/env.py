import os

ALL_VARS: dict[str, str | None] = {}
os.environ["PYDANTIC_ERRORS_INCLUDE_URL"] = "0"


def _env(name: str) -> str | None:
    full_name = "CDL_" + name
    value = ALL_VARS[full_name] = os.getenv(full_name)
    return value


RUNNING_IN_TERMUX = bool(
    os.getenv("TERMUX_VERSION") or os.getenv("TERMUX_MAIN_PACKAGE_FORMAT") or "com.termux" in os.getenv("$PREFIX", "")
)
PORTRAIT_MODE = bool(RUNNING_IN_TERMUX or _env("PORTRAIT_MODE"))


DEBUG_LOG_FOLDER = _env("DEBUG_LOG_FOLDER")

MAX_CRAWLER_ERRORS = int(_env("MAX_CRAWLER_ERRORS") or 10)
DEBUG_MODE = bool(
    DEBUG_LOG_FOLDER
    or _env("DEBUG_MODE")
    or os.getenv("PYCHARM_HOSTED")
    or os.getenv("TERM_PROGRAM") in ("vscode", "zed")
)
NO_PLUGINS = bool(_env("NO_PLUGINS"))
EDITOR = os.getenv("EDITOR")

# CRAWLERS

PIXELDRAIN_PROXY = _env("PIXELDRAIN_PROXY")
BANDCAMP_FORMATS = _env("BANDCAMP_FORMATS")
EPORNER_PREFER_H264 = _env("EPORNER_PREFER_H264")
ENABLE_TWITTER = bool(_env("ENABLE_TWITTER"))
ONEPACE_PREFER_DUB = bool(_env("ONEPACE_PREFER_DUB"))

ALL_VARS = dict(sorted(ALL_VARS.items()))  # pyright: ignore[reportConstantRedefinition]
ALL_VARS_RESOLVED = dict(
    sorted((k, v) for k, v in globals().items() if k not in ("os", "ALL_VARS") and not k.startswith("_"))
)
