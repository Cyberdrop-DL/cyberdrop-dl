---
icon: rectangle-terminal
description: Here's the available CLI Arguments
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

# CLI Arguments

{% hint style="info" %}
CLI inputs always take priority over config values.
{% endhint %}

{% hint style="info" %}
Use `-` instead of `_` to separate words in an config option name when using it as a CLI argument: Ex: `auto_dedupe` needs to be `auto-dedupe` when using it via the CLI
{% endhint %}

You can pass any of the **Config Settings** and **Global Settings** options as a cli argument for the program.

For items not explained below, you can find their counterparts in the configuration options to see what they do.

## CLI only arguments

### `appdata-folder`

| Type   | Default                       |
| ------ | ----------------------------- |
| `Path` | `<Current Working Directory>` |

Folder where Cyberdrop-DL will store it's database, cache and config files.

### `completed-after`

| Type   | Default |
| ------ | ------- |
| `date` | `None`  |

Only retry downloads that were completed on or after this date. The date should be in ISO 8601 format, for example, `2021-12-23`

{% hint style="info" %}
This option has no effect unless you run CDL with `--retry-all`
{% endhint %}

### `completed-before`

| Type   | Default |
| ------ | ------- |
| `date` | `None`  |

Only retry downloads that were completed on or before this date. The date should be in ISO 8601 format, for example, `2021-12-23`

{% hint style="info" %}
This option has no effect unless you run CDL with `--retry-all`
{% endhint %}

### `config-file`

| Type   | Default |
| ------ | ------- |
| `Path` | `None`  |

Path to the CDL `settings.yaml` file to load

{% hint style="info" %}
If both `config` and `config-file` are supplied, `config-file` takes priority
{% endhint %}

### `download`

| Type       | Default | Action       |
| ---------- | ------- | ------------ |
| `BoolFlag` | `False` | `store_true` |

Skips UI, start download immediately

### `download-tiktok-audios`

| Type       | Default | Action       |
| ---------- | ------- | ------------ |
| `BoolFlag` | `False` | `store_true` |

Download TikTok audios from posts and save them as separate files

### `download-tiktok-src-quality-videos`

| Type       | Default | Action       |
| ---------- | ------- | ------------ |
| `BoolFlag` | `False` | `store_true` |

By default, CDL will download the "optimized for streaming" version of tiktok videos. Setting this option to `True` will download videos in original (source) quality.

`_original` will be added as a suffix to their filename.

{% hint style="warning" %}
This will make video downloads several times slower

When it is set to `False` (the default) CDL can download 50 videos with a single request.
When it is set to `True` , CDL needs to make at least 3 requests _per_ video to download them.

There's also a daily limit of the API CDL uses: 5000 requests per day per IP

Setting this option to `True` will consume the daily limit faster
{% endhint %}

### `impersonate`

| Type                                                                                         | Default | Action                        |
| -------------------------------------------------------------------------------------------- | ------- | ----------------------------- |
| `chrome", "edge", "safari", "safari_ios", "chrome_android", "firefox"`, `BoolFlag` or `null` | `null`  | `store_true` or `store_const` |

Impersonation allows CDL to make requests and appear to be a legitimate web browser. This helps bypass bot-protection on some sites and it's required for any site that only accepts HTTP2 connections.

- The default value (`null`) means CDL will automatically use impersonation for crawlers that were programmed to use it.
- Passing the flag without any value (`--impersonate`) is the same as `--impersonate True`: CDL will use impersonation for ALL requests, using the default impersonation target
- Passing an specific target (ex: `--impersonate chrome_android`) will make CDL use impersonation for all requests, using that tarjet

{% hint style="info" %}
The current default target is `chrome`. The default target can change on any new release without notice
{% endhint %}

### `max-items-retry`

| Type             | Default |
| ---------------- | ------- |
| `NonNegativeInt` | `0`     |

Max number of links to retry. Using `0` means no limit

{% hint style="info" %}
This option has no effect unless you run CDL with one of the retry options: `--retry-all`, `--retry-failed` or `--retry-maintenance`
{% endhint %}

### `portrait`

| Type       | Default | Action       |
| ---------- | ------- | ------------ |
| `BoolFlag` | `False` | `store_true` |

Force CDL to run with a vertical layout

### `print-stats`

| Type       | Default | Action        |
| ---------- | ------- | ------------- |
| `BoolFlag` | `True`  | `store_false` |

Show stats report at the end of a run

### `retry-all`

| Type       | Default | Action       |
| ---------- | ------- | ------------ |
| `BoolFlag` | `False` | `store_true` |

Retry all downloads

### `retry-failed`

| Type       | Default | Action       |
| ---------- | ------- | ------------ |
| `BoolFlag` | `False` | `store_true` |

Retry failed downloads

### `retry-maintenance`

| Type       | Default | Action       |
| ---------- | ------- | ------------ |
| `BoolFlag` | `False` | `store_true` |

Retry download of maintenance files (bunkr). Requires files to be hashed

### `show-supported-sites`

| Type       | Default | Action       |
| ---------- | ------- | ------------ |
| `BoolFlag` | `False` | `store_true` |

Shows a list of all supported sites and exits

### `ui`

| Type                     | Default      |
| ------------------------ | ------------ |
| `CaseInsensitiveStrEnum` | `FULLSCREEN` |

UI can have 1 of these values:

- `DISABLED` : no output at all
- `ACTIVITY` : only shows a spinner with the text `running CDL...`
- `SIMPLE`: shows spinner + simplified progress bar
- `FULLSCREEN`: shows the normal UI/progress view

{% hint style="info" %}
Values are case insensitive, ex: both `disabled` and `DISABLED` are valid
{% endhint %}

## Overview

Bool arguments like options within `Download Options`, `Ignore Options`, `Runtime Options`, etc. can be prefixed with `--no-` to negate them. Ex: `--no-auto-dedupe` will disable auto dedupe, overriding whatever the config option was set to.

```shell
Usage: cyberdrop-dl COMMAND [OPTIONS] [ARGS]

Bulk asynchronous downloader for multiple file hosts

╭─ Commands ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ show         Show a list of all supported sites                                                                                               │
│ --help (-h)  Display this message and exit.                                                                                                   │
│ --version    Display application version.                                                                                                     │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Parameters ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ LINKS --links                               link(s) to content to download (passing multiple links is supported) [default: ()]                │
│ --appdata-folder                            AppData folder path                                                                               │
│ --completed-after                           only retry downloads that were completed on or after this date                                    │
│ --completed-before                          only retry downloads that were completed on or before this date                                   │
│ --config-file                               path to the CDL settings.yaml file to load                                                        │
│ --download --no-download                    skips UI, start download immediately [default: False]                                             │
│ --download-tiktok-audios                    download TikTok audios from posts and save them as separate files [default: False]                │
│   --no-download-tiktok-audios                                                                                                                 │
│ --download-tiktok-src-quality-videos        download TikTok videos in source quality [default: False]                                         │
│   --no-download-tiktok-src-quality-videos                                                                                                     │
│ --impersonate --no-impersonate              Use this target as impersonation for all scrape requests [choices: chrome, edge, safari,          │
│                                             safari_ios, chrome_android, firefox]                                                              │
│ --max-items-retry                           max number of links to retry [default: 0]                                                         │
│ --portrait --no-portrait                    force CDL to run with a vertical layout [default: False]                                          │
│ --print-stats --no-print-stats              show stats report at the end of a run [default: True]                                             │
│ --retry-all --no-retry-all                  retry all downloads [default: False]                                                              │
│ --retry-failed --no-retry-failed            retry failed downloads [default: False]                                                           │
│ --retry-maintenance --no-retry-maintenance  retry download of maintenance files (bunkr). Requires files to be hashed [default: False]         │
│ --ui                                        DISABLED, ACTIVITY, SIMPLE or FULLSCREEN [choices: disabled, activity, simple, fullscreen]        │
│                                             [default: fullscreen]                                                                             │
│ --source                                                                                                                                      │
│ --deep-scrape --no-deep-scrape              [default: False]                                                                                  │
│ --apprise-urls                              [default: ()]                                                                                     │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ BrowserCookies ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --auto-import --no-auto-import  [default: False]                                                                                              │
│ --browser                       [choices: chrome, firefox, safari, edge, opera, brave, librewolf, opera-gx, vivaldi, chromium] [default:      │
│                                 firefox]                                                                                                      │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ DownloadOptions ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --block-download-sub-folders               [default: False]                                                                                   │
│   --no-block-download-sub-folders                                                                                                             │
│ --disable-download-attempt-limit           [default: False]                                                                                   │
│   --no-disable-download-attempt-limit                                                                                                         │
│ --disable-file-timestamps                  [default: False]                                                                                   │
│   --no-disable-file-timestamps                                                                                                                │
│ --include-album-id-in-folder-name          [default: False]                                                                                   │
│   --no-include-album-id-in-folder-name                                                                                                        │
│ --include-thread-id-in-folder-name         [default: False]                                                                                   │
│   --no-include-thread-id-in-folder-name                                                                                                       │
│ --maximum-number-of-children               [default: []]                                                                                      │
│ --remove-domains-from-folder-names         [default: False]                                                                                   │
│   --no-remove-domains-from-folder-names                                                                                                       │
│ --remove-generated-id-from-filenames       [default: False]                                                                                   │
│   --no-remove-generated-id-from-filenames                                                                                                     │
│ --scrape-single-forum-post                 [default: False]                                                                                   │
│   --no-scrape-single-forum-post                                                                                                               │
│ --separate-posts-format                    [default: {default}]                                                                               │
│ --separate-posts --no-separate-posts       [default: False]                                                                                   │
│ --skip-download-mark-completed             [default: False]                                                                                   │
│   --no-skip-download-mark-completed                                                                                                           │
│ --maximum-thread-depth                     [default: 0]                                                                                       │
│ --maximum-thread-folder-depth                                                                                                                 │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ DupeCleanup ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --add-md5-hash --no-add-md5-hash                    [default: False]                                                                          │
│ --add-sha256-hash --no-add-sha256-hash              [default: False]                                                                          │
│ --auto-dedupe --no-auto-dedupe                      [default: True]                                                                           │
│ --hashing                                           [choices: off, in-place, post-download] [default: in-place]                               │
│ --send-deleted-to-trash --no-send-deleted-to-trash  [default: True]                                                                           │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ FileSizeLimits ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --maximum-image-size  [default: 0]                                                                                                            │
│ --maximum-other-size  [default: 0]                                                                                                            │
│ --maximum-video-size  [default: 0]                                                                                                            │
│ --minimum-image-size  [default: 0]                                                                                                            │
│ --minimum-other-size  [default: 0]                                                                                                            │
│ --minimum-video-size  [default: 0]                                                                                                            │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Files ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --download-folder --output -o -d        [default: Downloads]                                                                                  │
│ --dump-json -j --no-dump-json           [default: False]                                                                                      │
│ --input-file -i                         [default: URLs.txt]                                                                                   │
│ --save-pages-html --no-save-pages-html  [default: False]                                                                                      │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ General ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --ssl-context             [choices: truststore, certifi, truststore+certifi] [default: truststore+certifi]                                    │
│ --disable-crawlers        [default: []]                                                                                                       │
│ --flaresolverr                                                                                                                                │
│ --max-file-name-length    [default: 95]                                                                                                       │
│ --max-folder-name-length  [default: 60]                                                                                                       │
│ --proxy                                                                                                                                       │
│ --required-free-space     [default: 5000000000]                                                                                               │
│ --user-agent              [default: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:142.0) Gecko/20100101 Firefox/142.0]                         │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ GenericCrawlerInstances ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --wordpress-media  [default: []]                                                                                                              │
│ --wordpress-html   [default: []]                                                                                                              │
│ --discourse        [default: []]                                                                                                              │
│ --chevereto        [default: []]                                                                                                              │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ IgnoreOptions ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --exclude-audio --no-exclude-audio          [default: False]                                                                                  │
│ --exclude-images --no-exclude-images        [default: False]                                                                                  │
│ --exclude-other --no-exclude-other          [default: False]                                                                                  │
│ --exclude-videos --no-exclude-videos        [default: False]                                                                                  │
│ --filename-regex-filter                                                                                                                       │
│ --ignore-coomer-ads --no-ignore-coomer-ads  [default: False]                                                                                  │
│ --ignore-coomer-post-content                [default: True]                                                                                   │
│   --no-ignore-coomer-post-content                                                                                                             │
│ --only-hosts                                [default: []]                                                                                     │
│ --skip-hosts                                [default: []]                                                                                     │
│ --exclude-files-with-no-extension           [default: True]                                                                                   │
│   --no-exclude-files-with-no-extension                                                                                                        │
│ --exclude-before                                                                                                                              │
│ --exclude-after                                                                                                                               │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Logs ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --download-error-urls           [default: Download_Error_URLs.csv]                                                                            │
│ --last-forum-post               [default: Last_Scraped_Forum_Posts.csv]                                                                       │
│ --log-folder                    [default: AppData/Logs]                                                                                       │
│ --logs-expire-after                                                                                                                           │
│ --main-log                      [default: downloader.log]                                                                                     │
│ --rotate-logs --no-rotate-logs  [default: False]                                                                                              │
│ --scrape-error-urls             [default: Scrape_Error_URLs.csv]                                                                              │
│ --unsupported-urls              [default: Unsupported_URLs.csv]                                                                               │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ MediaDurationLimits ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --maximum-video-duration  [default: 0:00:00]                                                                                                  │
│ --maximum-audio-duration  [default: 0:00:00]                                                                                                  │
│ --minimum-video-duration  [default: 0:00:00]                                                                                                  │
│ --minimum-audio-duration  [default: 0:00:00]                                                                                                  │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ RateLimiting ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --download-attempts                      [default: 2]                                                                                         │
│ --download-delay                         [default: 0.0]                                                                                       │
│ --download-speed-limit                   [default: 0]                                                                                         │
│ --jitter                                 [default: 0]                                                                                         │
│ --max-simultaneous-downloads-per-domain  [default: 5]                                                                                         │
│ --max-simultaneous-downloads             [default: 15]                                                                                        │
│ --rate-limit                             [default: 25]                                                                                        │
│ --connection-timeout                     [default: 15]                                                                                        │
│ --read-timeout                           [default: 300]                                                                                       │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ RuntimeOptions ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --console-log-level                                 [default: 100]                                                                            │
│ --deep-scrape --no-deep-scrape                      [default: False]                                                                          │
│ --delete-partial-files --no-delete-partial-files    [default: False]                                                                          │
│ --ignore-history --no-ignore-history                [default: False]                                                                          │
│ --jdownloader-autostart --no-jdownloader-autostart  [default: False]                                                                          │
│ --jdownloader-download-dir                                                                                                                    │
│ --jdownloader-whitelist                             [default: []]                                                                             │
│ --log-level                                         [default: 10]                                                                             │
│ --send-unsupported-to-jdownloader                   [default: False]                                                                          │
│   --no-send-unsupported-to-jdownloader                                                                                                        │
│ --skip-check-for-empty-folders                      [default: False]                                                                          │
│   --no-skip-check-for-empty-folders                                                                                                           │
│ --skip-check-for-partial-files                      [default: False]                                                                          │
│   --no-skip-check-for-partial-files                                                                                                           │
│ --slow-download-speed                               [default: 0]                                                                              │
│ --update-last-forum-post                            [default: True]                                                                           │
│   --no-update-last-forum-post                                                                                                                 │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Sorting ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --scan-folder                                                                                                                                 │
│ --sort-downloads --no-sort-downloads  [default: False]                                                                                        │
│ --sort-folder                         [default: Downloads/Cyberdrop-DL Sorted Downloads]                                                      │
│ --sort-incrementer-format             [default:  ({i})]                                                                                       │
│ --sorted-audio                        [default: {sort_dir}/{base_dir}/Audio/{filename}{ext}]                                                  │
│ --sorted-image                        [default: {sort_dir}/{base_dir}/Images/{filename}{ext}]                                                 │
│ --sorted-other                        [default: {sort_dir}/{base_dir}/Other/{filename}{ext}]                                                  │
│ --sorted-video                        [default: {sort_dir}/{base_dir}/Videos/{filename}{ext}]                                                 │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ UIOptions ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --refresh-rate  [default: 10]                                                                                                                 │
╰───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
```
