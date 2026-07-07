---
description: Get off to the races.
icon: bullseye-arrow
layout:
  title:
    visible: true
  description:
    visible: true
  tableOfContents:
    visible: true
  outline:
    visible: false
  pagination:
    visible: true
---

# Getting Started

## Installing `cyberdrop-dl`</a>

There are two ways to install `cyberdrop-dl`. The first is the easy method, where you simply download the start scripts.
The start scripts will automatically install a compatible python version and then install `cyberdrop-dl`.

The second method is installing `cyberdrop-dl` directly from pypi using `uv`, `pipx` or `pip`

For instructions, see:

{% content-ref url="cyberdrop-dl-install.md" %}
{% endcontent-ref %}

{% content-ref url="cyberdrop-dl-on-android.md" %}
{% endcontent-ref %}

## What now?</a>

If you downloaded the start scripts, just open the `run` script with the name of the OS you are using.
For a manual install, execute the program with this command:

```shell
cyberdrop-dl
```

On the main screen, you can use the 'Edit URLs' option to add the URLs for the files you wish to download, then go back to the main menu
and choose `download` to start. That's it!

However, `cyberdrop-dl` has a ton of configuration options if you want more control over the downloads. You may want to review the following:

{% content-ref url="../reference/config/" %}
[configuration-options](../reference/config/)
{% endcontent-ref %}

{% content-ref url="../reference/cli-arguments.md" %}
[cli-arguments.md](../reference/cli-arguments.md)
{% endcontent-ref %}

{% content-ref url="../reference/config/notifications.md" %}
[notifications.md](../reference/config/notifications.md)
{% endcontent-ref %}

## AppData and Configuration

`cyberdrop-dl` have 3 files to control its behavior at runtime:

- A config file (YAML)
- A database file (SQLite)
- A cache file (JSON)

Additionally, a dedicated `logs` folder is created to store logs files of a session.
On Windows, all files are stored in `%AppData%/cyberdrop-dl`, with the logs folder being `%AppData%/cyberdrop-dl/logs`
On Unix systems, `cyberdrop-dl` follows the [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir/0.8/) to store application files.

These are the default locations used on each platform

| Location    | Windows                               | macOS/Linux/Android                                                                        |
| ----------- | ------------------------------------- | ------------------------------------------------------------------------------------------ |
| Config file | `%AppData%/cyberdrop-dl/config.yaml`  | `${XDG_CONFIG_HOME}/cyberdrop-dl/config.yaml` or `~/.config/cyberdrop-dl/config.yaml`      |
| Cache       | `%AppData%/cyberdrop-dl/cache.json`   | `${XDG_CACHE_HOME}/cyberdrop-dl/cache.json` or `~/.cache/cyberdrop-dl/cache.json`          |
| Database    | `%AppData%/cyberdrop-dl/cyberdrop.db` | `${XDG_DATA_HOME}/cyberdrop-dl/cyberdrop.db` or `~/.local/share/cyberdrop-dl/cyberdrop.db` |
| Logs        | `%AppData%/cyberdrop-dl/Logs`         | `${XDG_STATE_HOME}/cyberdrop-dl/logs` or `~/.local/state/cyberdrop-dl/logs`                |

### See also

You may also want to peek at what websites the program actually supports:

{% content-ref url="../reference/supported-websites.md" %}
[supported-websites.md](../reference/supported-websites.md)
{% endcontent-ref %}

If you have any issues, perhaps the [FAQ](../frequently-asked-questions.md) might help you!
