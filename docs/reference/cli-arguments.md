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

| Type                                                                             | Default | Action        |
| -------------------------------------------------------------------------------- | ------- | ------------- |
| `chrome", "edge", "safari", "safari_ios", "chrome_android", "firefox"` or `null` | `null`  | `store_const` |

Impersonation allows CDL to make requests and appear to be a legitimate web browser. This helps bypass bot-protection on some sites and it's required for any site that only accepts HTTP2 connections.

- The default value (`null`) means CDL will automatically use impersonation for crawlers that were programmed to use it.
- Passing an specific target (ex: `--impersonate chrome_android`) will make CDL use impersonation for all requests, using that tarjet

{% hint style="info" %}
The current default target is `chrome`. The default target can change on any new release without notice
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
│ --config-file                        path to the CDL settings.yaml file to load                  │
│ --download --no-download             skips UI, start download immediately [default: False]       │
│ --download-tiktok-audios             download TikTok audios from posts and save them as separate │
│   --no-download-tiktok-audios        files [default: False]                                      │
│ --download-tiktok-src-quality-video  download TikTok videos in source quality [default: False]   │
│   s --no-download-tiktok-src-qualit                                                              │
│   y-videos                                                                                       │
│ --impersonate                        Use this target as impersonation for all scrape requests    │
│                                      [choices: chrome, edge, safari, safari_ios, chrome_android, │
│                                      firefox]                                                    │
│ --portrait --no-portrait             force CDL to run with a vertical layout [default: False]    │
│ --print-stats --no-print-stats       show stats report at the end of a run [default: True]       │
│ --ui                                 DISABLED, ACTIVITY, SIMPLE or FULLSCREEN [choices:          │
│                                      disabled, activity, simple, fullscreen] [default:           │
│                                      fullscreen]                                                 │
│ --deep-scrape --no-deep-scrape       [default: False]                                            │
│ --disable-crawlers                   [default: []]                                               │
│ --download-folder --output -o -d     [default: Downloads]                                        │
│ --dump-json -j --no-dump-json        [default: False]                                            │
│ --dump-responses                     Save text/HTML/JSON responses to disk (flaresolverr         │
│   --no-dump-responses                responses are excluded) [default: False]                    │
│ --flaresolverr                                                                                   │
│ --input-file -i                      [default: URLs.txt]                                         │
│ --max-file-name-length               [default: 95]                                               │
│ --max-folder-name-length             [default: 60]                                               │
│ --min-free-space                     [default: 5000000000]                                       │
│ --proxy                                                                                          │
│ --ssl-context                        [choices: truststore, certifi, truststore+certifi]          │
│                                      [default: truststore+certifi]                               │
│ --user-agent                         [default: Mozilla/5.0 (X11; Linux x86_64; rv:150.0)         │
│                                      Gecko/20100101 Firefox/150.0]                               │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Cookies ────────────────────────────────────────────────────────────────────────────────────────╮
│ --cookies  File/folder to import cookies from (.txt Netscape files)                              │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ DownloadOptions ────────────────────────────────────────────────────────────────────────────────╮
│ --block-download-sub-folders         [default: False]                                            │
│   --no-block-download-sub-folders                                                                │
│ --mtime --no-mtime                   [default: True]                                             │
│ --include-album-id-in-folder-name -  [default: False]                                            │
│   -no-include-album-id-in-folder-na                                                              │
│   me                                                                                             │
│ --include-thread-id-in-folder-name   [default: False]                                            │
│   --no-include-thread-id-in-folder-                                                              │
│   name                                                                                           │
│ --max-children                       [default: []]                                               │
│ --remove-domains-from-folder-names   [default: False]                                            │
│   --no-remove-domains-from-folder-n                                                              │
│   ames                                                                                           │
│ --separate-posts-format              [default: {default}]                                        │
│ --separate-posts                     [default: False]                                            │
│   --no-separate-posts                                                                            │
│ --skip-download-mark-completed       [default: False]                                            │
│   --no-skip-download-mark-completed                                                              │
│ --max-thread-depth                   [default: 0]                                                │
│ --max-thread-folder-depth                                                                        │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ DupeCleanup ────────────────────────────────────────────────────────────────────────────────────╮
│ --hashes                        [choices: xxh128, md5, sha256] [default: ('xxh128', 'md5',       │
│                                 'sha256')]                                                       │
│ --auto-dedupe --no-auto-dedupe  [default: True]                                                  │
│ --hashing                       [choices: off, in-place, post-download] [default: in-place]      │
│ --send-deleted-to-trash         [default: True]                                                  │
│   --no-send-deleted-to-trash                                                                     │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ FileSizeLimits ─────────────────────────────────────────────────────────────────────────────────╮
│ --max-image-size  [default: 0]                                                                   │
│ --max-other-size  [default: 0]                                                                   │
│ --max-video-size  [default: 0]                                                                   │
│ --min-image-size  [default: 0]                                                                   │
│ --min-other-size  [default: 0]                                                                   │
│ --min-video-size  [default: 0]                                                                   │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Filters ────────────────────────────────────────────────────────────────────────────────────────╮
│ --exclude.audio --exclude.no-audio  [default: False]                                             │
│ --exclude.images                    [default: False]                                             │
│   --exclude.no-images                                                                            │
│ --exclude.other --exclude.no-other  [default: False]                                             │
│ --exclude.videos                    [default: False]                                             │
│   --exclude.no-videos                                                                            │
│ --exclude.files-with-no-ext         [default: True]                                              │
│   --exclude.no-files-with-no-ext                                                                 │
│ --exclude.before                                                                                 │
│ --exclude.after                                                                                  │
│ --exclude.coomer-ads                [default: False]                                             │
│   --exclude.no-coomer-ads                                                                        │
│ --exclude.coomer-post-content       [default: True]                                              │
│   --exclude.no-coomer-post-content                                                               │
│ --filename-regex                                                                                 │
│ --only-hosts                        [default: []]                                                │
│ --skip-hosts                        [default: []]                                                │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ GenericCrawlers ────────────────────────────────────────────────────────────────────────────────╮
│ --wordpress-media  [default: []]                                                                 │
│ --wordpress-html   [default: []]                                                                 │
│ --discourse        [default: []]                                                                 │
│ --chevereto        [default: []]                                                                 │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Jdownloader ────────────────────────────────────────────────────────────────────────────────────╮
│ --jdownloader --no-jdownloader  [default: False]                                                 │
│ --jdownloader.autostart         [default: False]                                                 │
│   --jdownloader.no-autostart                                                                     │
│ --jdownloader.download-dir                                                                       │
│ --jdownloader.whitelist         [default: []]                                                    │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Logs ───────────────────────────────────────────────────────────────────────────────────────────╮
│ --level                         Only log messages of this level or higher to the main log file   │
│                                 [choices: DEBUG, INFO, WARNING, ERROR, CRITICAL] [default:       │
│                                 DEBUG]                                                           │
│ --console-level                 Only log messages of this level or higher to the console. An     │
│                                 empty or None value will use the same level as log_level         │
│                                 [choices: DEBUG, INFO, WARNING, ERROR, CRITICAL]                 │
│ --download-error-urls           [default: Download_Error_URLs.csv]                               │
│ --log-folder                    [default: AppData/Logs]                                          │
│ --logs-expire-after                                                                              │
│ --main-log                      [default: downloader.log]                                        │
│ --rotate-logs --no-rotate-logs  [default: False]                                                 │
│ --scrape-error-urls             [default: Scrape_Error_URLs.csv]                                 │
│ --unsupported-urls              [default: Unsupported_URLs.csv]                                  │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ MediaDurationLimits ────────────────────────────────────────────────────────────────────────────╮
│ --max-video-duration  [default: 0:00:00]                                                         │
│ --max-audio-duration  [default: 0:00:00]                                                         │
│ --min-video-duration  [default: 0:00:00]                                                         │
│ --min-audio-duration  [default: 0:00:00]                                                         │
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
│ --ignore-history             [default: False]                                                    │
│   --no-ignore-history                                                                            │
│ --delete-partial-files       [default: False]                                                    │
│   --no-delete-partial-files                                                                      │
│ --delete-empty-folders       [default: True]                                                     │
│   --no-delete-empty-folders                                                                      │
│ --slow-download-speed        [default: 0]                                                        │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Sort ───────────────────────────────────────────────────────────────────────────────────────────╮
│ --sort --no-sort            [default: False]                                                     │
│ --sort.input-folder                                                                              │
│ --sort.output-folder        [default: Downloads/Cyberdrop-DL Sorted Downloads]                   │
│ --sort.formats.audio        Format to generate sorted audio file [default:                       │
│                             {sort_dir}/{base_dir}/Audio/{filename}{ext}]                         │
│ --sort.formats.image        Format to generate sorted image file [default:                       │
│                             {sort_dir}/{base_dir}/Images/{filename}{ext}]                        │
│ --sort.formats.other        Format to generate sorted files of unknown type [default:            │
│                             {sort_dir}/{base_dir}/Other/{filename}{ext}]                         │
│ --sort.formats.video        Format to generate sorted video file [default:                       │
│                             {sort_dir}/{base_dir}/Videos/{filename}{ext}]                        │
│ --sort.formats.incrementer  Format for separator on name collisions [default:  ({i})]            │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ UIOptions ──────────────────────────────────────────────────────────────────────────────────────╮
│ --refresh-rate  [default: 10.0]                                                                  │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
```
<!-- END_CLI_OVERVIEW -->
