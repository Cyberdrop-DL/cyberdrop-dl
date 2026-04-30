import hashlib
import os

ALL_VARS: dict[str, str | None] = {}
os.environ["PYDANTIC_ERRORS_INCLUDE_URL"] = "0"


def _env(name: str, *, censor: bool = False) -> str | None:
    full_name = "CDL_" + name
    value = os.getenv(full_name)
    if censor and value:
        value = hashlib.sha256(value.encode("utf-8")).hexdigest()
    ALL_VARS[full_name] = value
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
ENABLE_DEBUG_CRAWLERS = (
    _env("ENABLE_DEBUG_CRAWLERS", censor=True) == "d396ab8c85fcb1fecd22c8d9b58acf944a44e6d35014e9dd39e42c9a64091eda"
)

NO_PLUGINS = bool(_env("NO_PLUGINS"))
EDITOR = os.getenv("EDITOR")

# CRAWLERS

PIXELDRAIN_PROXY = _env("PIXELDRAIN_PROXY")
BANDCAMP_FORMATS = _env("BANDCAMP_FORMATS")
ENABLE_TWITTER = bool(_env("ENABLE_TWITTER"))
ONEPACE_PREFER_DUB = bool(_env("ONEPACE_PREFER_DUB"))

ALL_VARS = dict(sorted(ALL_VARS.items()))  # pyright: ignore[reportConstantRedefinition]
ALL_VARS_RESOLVED = dict(
    sorted((k, v) for k, v in globals().items() if k not in ("os", "hashlib", "ALL_VARS") and not k.startswith("_"))
)
