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
Use `-` instead of `_` to separate words in an config option name when using it as a CLI argument:

Ex: `delete_partial_files` needs to be `delete-partial-files` when using it via the CLI
{% endhint %}

All config option except authentication credentials have a CLI equivalent to override them.

For items not explained below, you can find their counterparts in the configuration options to see what they do.

## CLI only arguments

These options can onlny be supplied via CLI argmunets. They are not included on the config file

### `--config-file`

| Type   | Default |
| ------ | ------- |
| `Path` | `null`  |

Path to the config file to use for this session. The config file at the default location will be ignored. This file _must_ have a `.yml` or `.yaml` extension

{% hint style="info" %}
If provided, this file _must_ exists already, but it can be empty
{% endhint %}

### `--cache-file`

| Type   | Default |
| ------ | ------- |
| `Path` | `null`  |

Path to the cache file to use for this session. The cache at the default location will be ignored. This file _must_ have a `.json` extension

{% hint style="info" %}
If provided, this file _must_ exists already, but it can be empty
{% endhint %}

### `--database-file`

| Type   | Default |
| ------ | ------- |
| `Path` | `null`  |

Path to the database file to use for this session. The database at the default location will be ignored. This file _must_ have a `.db` extension

{% hint style="info" %}
If provided, this file _must_ exists already, but it can be empty
{% endhint %}

## Overview

<!-- START_CLI_OVERVIEW -->

```shell
Usage: cyberdrop-dl COMMAND [OPTIONS] [ARGS]

Bulk asynchronous downloader for multiple file hosts

╭─ Commands ───────────────────────────────────────────────────────────────────────────────────────╮
│ cleanup      Perform maintenance tasks                                                           │
│ database     Commands for managing the database                                                  │
│ show         Show a list of all supported sites                                                  │
│ --help (-h)  Display this message and exit.                                                      │
│ --version    Display application version.                                                        │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Parameters ─────────────────────────────────────────────────────────────────────────────────────╮
│ LINKS --links                        link(s) to content to download (passing multiple links is   │
│                                      supported) [default: ()]                                    │
│ --appdata-folder                     AppData folder path                                         │
│ --completed-after                    only retry downloads that were completed on or after this   │
│                                      date                                                        │
│ --completed-before                   only retry downloads that were completed on or before this  │
│                                      date                                                        │
│ --config-file                        path to the CDL config.yaml file to load                  │
│ --download --no-download             skips UI, start download immediately [default: False]       │
│ --download-tiktok-audios             download TikTok audios from posts and save them as separate │
│   --no-download-tiktok-audios        files [default: False]                                      │
│ --download-tiktok-src-quality-video  download TikTok videos in source quality [default: False]   │
│   s --no-download-tiktok-src-qualit                                                              │
│   y-videos                                                                                       │
│ --impersonate                        Use this target as impersonation for all scrape requests    │
│                                      [choices: chrome, edge, safari, safari_ios, chrome_android, │
│                                      firefox]                                                    │
│ --max-items-retry                    max number of links to retry [default: 0]                   │
│ --portrait --no-portrait             force CDL to run with a vertical layout [default: False]    │
│ --print-stats --no-print-stats       show stats report at the end of a run [default: True]       │
│ --retry-all --no-retry-all           retry all downloads [default: False]                        │
│ --retry-failed --no-retry-failed     retry failed downloads [default: False]                     │
│ --retry-maintenance                  retry download of maintenance files (bunkr). Requires files │
│   --no-retry-maintenance             to be hashed [default: False]                               │
│ --ui                                 DISABLED, ACTIVITY, SIMPLE or FULLSCREEN [choices:          │
│                                      disabled, activity, simple, fullscreen] [default:           │
│                                      fullscreen]                                                 │
│ --deep-scrape --no-deep-scrape       [default: False]                                            │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ BrowserCookies ─────────────────────────────────────────────────────────────────────────────────╮
│ --auto-import --no-auto-import  [default: False]                                                 │
│ --browser                       [choices: chrome, firefox, safari, edge, opera, brave,           │
│                                 librewolf, opera-gx, vivaldi, chromium] [default: firefox]       │
│ --sites                                                                                          │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ DownloadOptions ────────────────────────────────────────────────────────────────────────────────╮
│ --block-download-sub-folders         [default: False]                                            │
│   --no-block-download-sub-folders                                                                │
│ --disable-download-attempt-limit     [default: False]                                            │
│   --no-disable-download-attempt-lim                                                              │
│   it                                                                                             │
│ --disable-file-timestamps            [default: False]                                            │
│   --no-disable-file-timestamps                                                                   │
│ --include-album-id-in-folder-name -  [default: False]                                            │
│   -no-include-album-id-in-folder-na                                                              │
│   me                                                                                             │
│ --include-thread-id-in-folder-name   [default: False]                                            │
│   --no-include-thread-id-in-folder-                                                              │
│   name                                                                                           │
│ --maximum-number-of-children         [default: []]                                               │
│ --remove-domains-from-folder-names   [default: False]                                            │
│   --no-remove-domains-from-folder-n                                                              │
│   ames                                                                                           │
│ --remove-generated-id-from-filename  [default: False]                                            │
│   s --no-remove-generated-id-from-f                                                              │
│   ilenames                                                                                       │
│ --scrape-single-forum-post           [default: False]                                            │
│   --no-scrape-single-forum-post                                                                  │
│ --separate-posts-format              [default: {default}]                                        │
│ --separate-posts                     [default: False]                                            │
│   --no-separate-posts                                                                            │
│ --skip-download-mark-completed       [default: False]                                            │
│   --no-skip-download-mark-completed                                                              │
│ --maximum-thread-depth               [default: 0]                                                │
│ --maximum-thread-folder-depth                                                                    │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ DupeCleanup ────────────────────────────────────────────────────────────────────────────────────╮
│ --add-md5-hash --no-add-md5-hash  [default: False]                                               │
│ --add-sha256-hash                 [default: False]                                               │
│   --no-add-sha256-hash                                                                           │
│ --auto-dedupe --no-auto-dedupe    [default: True]                                                │
│ --hashing                         [choices: off, in-place, post-download] [default: in-place]    │
│ --send-deleted-to-trash           [default: True]                                                │
│   --no-send-deleted-to-trash                                                                     │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ FileSizeLimits ─────────────────────────────────────────────────────────────────────────────────╮
│ --maximum-image-size  [default: 0]                                                               │
│ --maximum-other-size  [default: 0]                                                               │
│ --maximum-video-size  [default: 0]                                                               │
│ --minimum-image-size  [default: 0]                                                               │
│ --minimum-other-size  [default: 0]                                                               │
│ --minimum-video-size  [default: 0]                                                               │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Files ──────────────────────────────────────────────────────────────────────────────────────────╮
│ --download-folder --output -o -d  [default: Downloads]                                           │
│ --dump-json -j --no-dump-json     [default: False]                                               │
│ --input-file -i                   [default: URLs.txt]                                            │
│ --save-pages-html                 [default: False]                                               │
│   --no-save-pages-html                                                                           │
│ --dump-responses                  Save text/HTML/JSON responses to disk (flaresolverr responses  │
│   --no-dump-responses             are excluded) [default: False]                                 │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ General ────────────────────────────────────────────────────────────────────────────────────────╮
│ --ssl-context             [choices: truststore, certifi, truststore+certifi] [default:           │
│                           truststore+certifi]                                                    │
│ --disable-crawlers        [default: []]                                                          │
│ --flaresolverr                                                                                   │
│ --max-file-name-length    [default: 95]                                                          │
│ --max-folder-name-length  [default: 60]                                                          │
│ --proxy                                                                                          │
│ --required-free-space     [default: 5000000000]                                                  │
│ --user-agent              [default: Mozilla/5.0 (X11; Linux x86_64; rv:150.0) Gecko/20100101     │
│                           Firefox/150.0]                                                         │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ GenericCrawlerInstances ────────────────────────────────────────────────────────────────────────╮
│ --wordpress-media  [default: []]                                                                 │
│ --wordpress-html   [default: []]                                                                 │
│ --discourse        [default: []]                                                                 │
│ --chevereto        [default: []]                                                                 │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ IgnoreOptions ──────────────────────────────────────────────────────────────────────────────────╮
│ --exclude-audio --no-exclude-audio   [default: False]                                            │
│ --exclude-images                     [default: False]                                            │
│   --no-exclude-images                                                                            │
│ --exclude-other --no-exclude-other   [default: False]                                            │
│ --exclude-videos                     [default: False]                                            │
│   --no-exclude-videos                                                                            │
│ --filename-regex-filter                                                                          │
│ --ignore-coomer-ads                  [default: False]                                            │
│   --no-ignore-coomer-ads                                                                         │
│ --ignore-coomer-post-content         [default: True]                                             │
│   --no-ignore-coomer-post-content                                                                │
│ --only-hosts                         [default: []]                                               │
│ --skip-hosts                         [default: []]                                               │
│ --exclude-files-with-no-extension -  [default: True]                                             │
│   -no-exclude-files-with-no-extensi                                                              │
│   on                                                                                             │
│ --exclude-before                                                                                 │
│ --exclude-after                                                                                  │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Logs ───────────────────────────────────────────────────────────────────────────────────────────╮
│ --download-error-urls           [default: Download_Error_URLs.csv]                               │
│ --last-forum-post               [default: Last_Scraped_Forum_Posts.csv]                          │
│ --log-folder                    [default: AppData/Logs]                                          │
│ --logs-expire-after                                                                              │
│ --main-log                      [default: downloader.log]                                        │
│ --rotate-logs --no-rotate-logs  [default: False]                                                 │
│ --scrape-error-urls             [default: Scrape_Error_URLs.csv]                                 │
│ --unsupported-urls              [default: Unsupported_URLs.csv]                                  │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ MediaDurationLimits ────────────────────────────────────────────────────────────────────────────╮
│ --maximum-video-duration  [default: 0:00:00]                                                     │
│ --maximum-audio-duration  [default: 0:00:00]                                                     │
│ --minimum-video-duration  [default: 0:00:00]                                                     │
│ --minimum-audio-duration  [default: 0:00:00]                                                     │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ RateLimiting ───────────────────────────────────────────────────────────────────────────────────╮
│ --download-attempts                  [default: 2]                                                │
│ --download-delay                     [default: 0.0]                                              │
│ --download-speed-limit               [default: 0]                                                │
│ --jitter                             [default: 0]                                                │
│ --max-simultaneous-downloads-per-do  [default: 5]                                                │
│   main                                                                                           │
│ --max-simultaneous-downloads         [default: 15]                                               │
│ --rate-limit                         [default: 25]                                               │
│ --connection-timeout                 [default: 15]                                               │
│ --read-timeout                       [default: 300]                                              │
│ --concurrent-segments                Allow up to <N> HLS segments to be downloaded concurrently  │
│                                      [default: 10]                                               │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ RuntimeOptions ─────────────────────────────────────────────────────────────────────────────────╮
│ --log-level                          Only log messages of this level or higher to the main log   │
│                                      file [choices: DEBUG, INFO, WARNING, ERROR, CRITICAL]       │
│                                      [default: DEBUG]                                            │
│ --console-log-level                  Only log messages of this level or higher to the console.   │
│                                      An empty or None value will use the same level as log_level │
│                                      [choices: DEBUG, INFO, WARNING, ERROR, CRITICAL]            │
│ --deep-scrape --no-deep-scrape       [default: False]                                            │
│ --delete-partial-files               [default: False]                                            │
│   --no-delete-partial-files                                                                      │
│ --ignore-history                     [default: False]                                            │
│   --no-ignore-history                                                                            │
│ --jdownloader-autostart              [default: False]                                            │
│   --no-jdownloader-autostart                                                                     │
│ --jdownloader-download-dir                                                                       │
│ --jdownloader-whitelist              [default: []]                                               │
│ --send-unsupported-to-jdownloader -  [default: False]                                            │
│   -no-send-unsupported-to-jdownload                                                              │
│   er                                                                                             │
│ --skip-check-for-empty-folders       [default: False]                                            │
│   --no-skip-check-for-empty-folders                                                              │
│ --skip-check-for-partial-files       [default: False]                                            │
│   --no-skip-check-for-partial-files                                                              │
│ --slow-download-speed                [default: 0]                                                │
│ --update-last-forum-post             [default: True]                                             │
│   --no-update-last-forum-post                                                                    │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Sorting ────────────────────────────────────────────────────────────────────────────────────────╮
│ --scan-folder                                                                                    │
│ --sort-downloads           [default: False]                                                      │
│   --no-sort-downloads                                                                            │
│ --sort-folder              [default: Downloads/Cyberdrop-DL Sorted Downloads]                    │
│ --sort-incrementer-format  [default:  ({i})]                                                     │
│ --sorted-audio             [default: {sort_dir}/{base_dir}/Audio/{filename}{ext}]                │
│ --sorted-image             [default: {sort_dir}/{base_dir}/Images/{filename}{ext}]               │
│ --sorted-other             [default: {sort_dir}/{base_dir}/Other/{filename}{ext}]                │
│ --sorted-video             [default: {sort_dir}/{base_dir}/Videos/{filename}{ext}]               │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ UIOptions ──────────────────────────────────────────────────────────────────────────────────────╮
│ --refresh-rate  [default: 10.0]                                                                  │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
```

<!-- END_CLI_OVERVIEW -->
