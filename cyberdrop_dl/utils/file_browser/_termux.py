from __future__ import annotations

import dataclasses
import subprocess
import sys
import webbrowser
from typing import ClassVar, override

from cyberdrop_dl import env


class AndroidActivityManagerBrowser(webbrowser.UnixBrowser):
    USER_ID: ClassVar[str] = env.TERMUX.get("USER_ID", "0")

    def __init__(self, name: str, activity: str) -> None:
        super().__init__("am")
        self.package_name: str = name
        self.activity: str = activity
        self.args: list[str] = [
            "start",
            "--user",
            self.USER_ID,
            "-a",
            "android.intent.action.VIEW",
            "-n",
            f"{name}/{activity}",
            "-d",
            "%s",
        ]

    @override
    def open(self, url: str, new: int = 0, autoraise: bool = True) -> bool:
        cmdline = [self.name] + [arg.replace("%s", url) for arg in self.args]
        sys.audit("webbrowser.open", url)
        try:
            p = subprocess.Popen(
                cmdline,
                close_fds=True,
                start_new_session=True,
                stderr=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )
            try:
                return not p.wait(timeout=8)
            except subprocess.TimeoutExpired:
                return True
        except OSError:
            return False


@dataclasses.dataclass(slots=True, frozen=True, order=True, kw_only=True)
class FileManager:
    name: str
    package_name: str
    activity: str
    url: str
    skip: str | bool = False


# Ordered by preference
ANDROID_FILE_MANAGERS = (
    FileManager(
        name="Documents UI (AOSP built-in file browser)",  # Android 10+
        package_name="com.google.android.documentsui",
        activity="com.android.documentsui.DocumentsActivity",
        url="https://source.android.com/docs/core/ota/modular-system/documentsui",
        skip="Can't take custom URI, always opens at /downloads",
    ),
    FileManager(
        name="Solid Explorer",
        package_name="pl.solidexplorer2",
        activity="pl.solidexplorer.SolidExplorer",
        url="https://play.google.com/store/apps/details?id=pl.solidexplorer2",
    ),
    FileManager(
        name="Mixplorer",
        package_name="com.mixplorer",
        activity="com.mixplorer.activities.BrowseActivity",
        url="https://xdaforums.com/t/app-2-3-mixplorer-v6-x-released-fully-featured-file-manager.1523691/",
    ),
    FileManager(
        name="Mixplorer Silver",
        package_name="com.mixplorer.silver",
        activity="com.mixplorer.activities.BrowseActivity",
        url="https://play.google.com/store/apps/details?id=com.mixplorer.silver",
    ),
    FileManager(
        name="Samsung MyFiles",
        package_name="com.sec.android.app.myfiles",
        activity="com.sec.android.app.myfiles.ui.MultiInstanceLaunchActivity",
        url="https://play.google.com/store/apps/details?id=com.sec.android.app.myfiles",
    ),
)
