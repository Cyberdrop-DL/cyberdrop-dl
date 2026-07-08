# `level`

| Type                                            | Default |
| ----------------------------------------------- | ------- |
| `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | `DEBUG` |

Only log messages of this level or higher to the main log file, according to [Python logging levels](https://docs.python.org/3/library/logging.html#levels).

| Level      | Value | Description                                                                                        |
| ---------- | ----- | -------------------------------------------------------------------------------------------------- |
| `DEBUG`    | 10    | Offers detailed information and HTTP requests details, typically useful to troubleshoot problems   |
| `INFO`     | 20    | Provides general information about scrape and download progress                                    |
| `WARNING`  | 30    | Potential issues or something that might need attention (e.g. `Login wasn't provided for <FORUM>`) |
| `ERROR`    | 40    | Serious problem preventing `cyberdrop-dl` to execute some function                                 |
| `CRITICAL` | 50    | Fatal error that causes `cyberdrop-dl` to exit immediately                                         |

```yaml
logs:
  level: DEBUG
```

{% hint style="info" %}
Using anything other that `DEBUG` makes troubleshooting issues harder. Practically speaking, you should _only_ change this if you expect CDL to run for an extended period
(with a large number of input URLs) to minimize the log files sizes
{% endhint %}

{% hint style="warning" %}
`DEBUG` logs raw HTTP requests to the main log file. These requests may have personally identifiable information like your IP or login credentials for sites in cookies/headers
{% endhint %}

# `console_level`

| Type                                                      | Default |
| --------------------------------------------------------- | ------- |
| `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` or `null` | `null`  |

Only log messages of this level or higher to the console. A `null` value will use the same level as `logs.level`

```yaml
logs:
  level: null
```

# `expire_after`

| Type                  | Default |
| --------------------- | ------- |
| `timedelta` or `null` | `null`  |

if `logs.rotate` is enabled, this setting specifies the retention period for log files before they are deleted.

- A `timedelta` input is expected to be a valid ISO 8601 timespan, ex: `P10DT2H30M10S`
- An `int` input is assumed to be seconds
- A `str` input is expected to be in the format; `<value> <unit>`, ex: `10 days`.
- A `null` value means disabled (never delete any logs)

{% hint style="warning" %}
Any `.log` or `.csv` file within `logs.folder` will be deleted, even if CDL did not create them
{% endhint %}

{% hint style="info" %}
Log files with an absolute path not relative to `logs.folder` will never be deleted
{% endhint %}

```yaml
logs:
  expire_after: null
```

# `folder`

| Type             | Default |
| ---------------- | ------- |
| `Path` or `null` | `null`  |

The path to the location you want `cyberdrop-dl` to store logs in. A `null` values will use the platform's default

- Windows: `%AppData%/cyberdrop-dl/Logs`
- macOS/Linux/Android: `${XDG_STATE_HOME}/cyberdrop-dl/logs` or `~/.local/state/cyberdrop-dl/logs`

```yaml
logs:
  folder: null
```

# `rotate`

| Type   | Default |
| ------ | ------- |
| `bool` | `false` |

If enabled, `cyberdrop-dl` will add the current date and time as a suffix to each log file, in the format `YYMMDD_HHMMSS`

Every log file will be created inside a sub folder with the current date

This will prevent overriding old log files

```yaml
logs:
  rotate: false
```

# Files

## `main`

| Type   | Default          | Restrictions                                  |
| ------ | ---------------- | --------------------------------------------- |
| `Path` | `downloader.log` | extension will always be overridden to `.log` |

Path of main log file. For relative paths, the final path will be `logs.folder` / `logs.files.main`

```yaml
logs:
  files:
    main: downloader.log
```

## `download_errors`

| Type   | Default               | Restrictions                                  |
| ------ | --------------------- | --------------------------------------------- |
| `Path` | `download_errors.csv` | extension will always be overridden to `.csv` |

Path of the download error log. For relative paths, the final path will be `logs.folder` / `logs.files.download_errors`

`cyberdrop-dl` will output the links it fails to download, the reason and their origin in CSV format.

```yaml
logs:
  files:
    download_errors: download_errors.csv
```

## `scrape_errors`

| Type   | Default             | Restrictions                                  |
| ------ | ------------------- | --------------------------------------------- |
| `Path` | `scrape_errors.csv` | extension will always be overridden to `.csv` |

Path of the errors errors log file. For relative paths, the final path will be `logs.folder` / `logs.files.scrape_errors`

`cyberdrop-dl` will save to the file the links it fails to scrape, the reason and their origin in CSV format.

```yaml
logs:
  files:
    scrape_errors: scrape_errors.csv
```

## `unsupported`

| Type   | Default           | Restrictions                                  |
| ------ | ----------------- | --------------------------------------------- |
| `Path` | `unsupported.csv` | extension will always be overridden to `.csv` |

Path of the unsupported log file. For relative paths, the final path will be `logs.folder` / `logs.files.unsupported`

`cyberdrop-dl` will output links it can't download to this file.

```yaml
logs:
  files:
    unsupported: unsupported.csv
```

## `last_forum_post`

| Type   | Default               | Restrictions                                  |
| ------ | --------------------- | --------------------------------------------- |
| `Path` | `last_forum_post.csv` | extension will always be overridden to `.csv` |

Save the URL of the last scraped post from each thread to this file. For relative paths, the final path will be `logs.folder` / `logs.files.last_forum_post`

```yaml
logs:
  files:
    unsupported: last_forum_post.csv
```
