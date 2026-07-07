---
description:
icon: download
---

# `cyberdrop-dl` Install

## Using the start scripts (from GitHub release page)

This is the simplest method to get the program up and running. Pre-configured start files are provided that will
automatically install python, install `cyberdrop-dl`, update, and launch the program for you.

{% hint style="info" %}
The start scripts only work on 64bits operating systems. If you are running a 32bit OS, you need to install directly
from pypi and may need to compile some dependencies
{% endhint %}

You can download them from here: <https://github.com/Cyberdrop-DL/cyberdrop-dl/releases/latest>

You only need to download the `Cyberdrop-DL_<version>.zip` file, you don't need to worry about the other files.

Extract the contents of the zip file to any location. The extracted files will include an install file for Windows, macOS, and Linux

Run the `install` file to install/update `cyberdrop-dl`, then open the `run` file to run it. That's it!

{% hint style="info" %}
If you are using Windows, **DO NOT** run the scripts as admin
{% endhint %}

## Manual Install

### 1. Using `uv`

The recommended way to install `cyberdrop-dl` is using [`uv`](https://docs.astral.sh/uv).

{% tabs %}

{% tab title="macOS / Linux" %}

```shell
curl -LsSf https://astral.sh/uv/install.sh | sh
```

{% endtab %}

{% tab title="Windows" %}

```shell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

{% endtab %}
{% endtabs %}

Once you have `uv`, you can install `cyberdrop-dl` using:

```shell
uv tool install cyberdrop-dl-patched
```

### 2. Manual Python Install

If you do not want to or can't use `uv`, you will need to install a compatible python version manually.

If you don't have python, you can find and download it from their official website: <https://www.python.org/downloads/>

{% hint style="info" %}
`cyberdrop-dl` requires python >=3.12
{% endhint %}

Once you have python, you can install `cyberdrop-dl` directly from pypi using `pipx` or `pip`. In a command prompt/terminal window:

{% tabs %}

{% tab title="pipx" %}

- Install `pipx` (if you don't have it already)

```shell
pip install pipx
```

- Install `cyberdrop-dl`

```shell
pipx install cyberdrop-dl-patched
```

{% endtab %}

{% tab title="pip" %}
{% hint style="warning" %}
Using bare `pip` to install `cyberdrop-dl` is discouraged as it may lead to dependency conflicts with global installs
and an inconsistent environment. Please consider using `uv` or `pipx`
{% endhint %}

```shell
pip install cyberdrop-dl-patched
```

{% endtab %}
{% endtabs %}
