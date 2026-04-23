import os

os.environ["PYDANTIC_ERRORS_INCLUDE_URL"] = "0"
RUNNING_IN_TERMUX = bool(
    os.getenv("TERMUX_VERSION") or os.getenv("TERMUX_MAIN_PACKAGE_FORMAT") or "com.termux" in os.getenv("$PREFIX", "")
)
PORTRAIT_MODE = bool(RUNNING_IN_TERMUX or os.getenv("CDL_PORTRAIT_MODE"))


DEBUG_LOG_FOLDER = os.getenv("CDL_DEBUG_LOG_FOLDER")

MAX_CRAWLER_ERRORS = int(os.getenv("CDL_MAX_CRAWLER_ERRORS") or 10)
DEBUG = bool(
    DEBUG_LOG_FOLDER
    or os.getenv("CDL_DEBUG")
    or os.getenv("PYCHARM_HOSTED")
    or os.getenv("TERM_PROGRAM") in ("vscode", "zed")
)
NO_PLUGINS = bool(os.getenv("CDL_NO_PLUGINS"))

# CRAWLERS

PIXELDRAIN_PROXY = os.getenv("CDL_PIXELDRAIN_PROXY")
BANDCAMP_FORMATS = os.getenv("CDL_BANDCAMP_FORMATS")
EPORNER_PREFER_H264 = os.getenv("CDL_EPORNER_PREFER_H264")
ENABLE_TWITTER = bool(os.getenv("CDL_ENABLE_TWITTER"))
ONEPACE_PREFER_DUB = bool(os.getenv("CDL_ONEPACE_PREFER_DUB"))
