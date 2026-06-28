---
description:
icon: android
---

# Installing cyberdrop-dl on Android

Cyberdrop-dl is a terminal app. That means you need a terminal emulator to run it. The defacto choice in Android is [`termux`](https://termux.dev/en/).

{% hint style="info" %}
On Android, some of the dependencies need to be compiled from source. A rust compiler is required. This means the installation could take several minutes, especially on low end phones

Compiling from source also requires a lot of extra storage. You will need at least 3.4GB of free space just for the installation
{% endhint %}

## 1. Install `termux`

Termux wiki: [https://wiki.termux.com/wiki/Installation](https://wiki.termux.com/wiki/Installation)

Install `termux` from [F-droid (recommended)](https://f-droid.org/packages/com.termux/) or from the [Google Playstore (restricted version)](https://play.google.com/store/apps/details?id=com.termux):

## 2. Install `cyberdrop-dl`

Run the following commands inside `termux`

```shell
#!/bin/sh
termux-setup-storage
pkg upgrade -y
pkg install rust micro ffmpeg python uv -y

# Making sure maturin knows we are building ON Android, not FOR Android
ANDROID_API_LEVEL=24
export ANDROID_API_LEVEL

uv tool install --upgrade --force cyberdrop-dl-patched
uv tool update-shell
```

{% hint style="warning" %}
You will loose your config and database file if you ever uninstall `termux`.
Use the `--database-file` and `--config-file` CLI options to change the location of those files:

```shell
mkdir /sdcard/cyberdrop-dl
touch /sdcard/cyberdrop-dl/cyberdrop.db
touch /sdcard/cyberdrop-dl/config.yaml
cyberdrop-dl --database-file /sdcard/cyberdrop-dl/cyberdrop.db --config-file /sdcard/cyberdrop-dl/config.yaml
```

You can setup an alias to always include these options by default when running `cyberdrop-dl`

```shell
echo 'alias cyberdrop-dl="cyberdrop-dl --database-file /sdcard/cyberdrop-dl/cyberdrop.db --config-file /sdcard/cyberdrop-dl/config.yaml"' >> ~/.bashrc
```

{% endhint %}

## How to update `cyberdrop-dl`?

Run this command inside `termux`:

```shell
uv tool upgrade cyberdrop-dl-patched
```
