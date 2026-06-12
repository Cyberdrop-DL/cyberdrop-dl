# Runtime Options

These are higher level options that effect the overarching functions of the program.

## `console_log_level`

| Type                                            | Default |
| ----------------------------------------------- | ------- |
| `DEBUG, INFO, WARNING, ERROR, CRITICAL or None` | `None`  |

Only log messages of this level or higher to the console. An empty or `None` value will use the same level as `log_level`

## `deep_scrape`

| Type   | Default |
| ------ | ------- |
| `bool` | `false` |

Cyberdrop-DL uses a some tricks to try to reduce the number of requests it needs to make while scraping a site. However, this may cause a few links to be skipped. Use `--deep-scrape` to disable this functionality and always make a new request.

This setting is temporary and will always reset to `false` after each run

{% hint style="warning" %}
Use this option only when absolutely necessary, as it will significantly increase the number of requests being made.

For example, scraping an album normally takes one single request.

With `--deep-scrape`, CDL will make `n` requests per album, where `n` is the total number of items in the album
{% endhint %}

## `delete_partial_files`

| Type   | Default |
| ------ | ------- |
| `bool` | `false` |

Files downloaded by CDL have a `.part` extension (`.cdl_hls` for HLS segments). CDL only changes the extension to the original one after a successful download.
This allows CDL to resume downloads on subsequent runs.

Setting this to `true` will delete any `.part` and `.cdl_hls` files in the download folder.

## `ignore_history`

| Type   | Default |
| ------ | ------- |
| `bool` | `false` |

By default, the program tracks your downloads in a database to prevent downloading the same files multiple times, to save time and reduce strain on the servers you're downloading from.

Setting this to `true` will cause the program to ignore the database, and will allow you to re-download files.

## `jdownloader_autostart`

| Type   | Default |
| ------ | ------- |
| `bool` | `false` |

Setting this to `true` will make jdownloader start downloads as soon as they are sent.

{% hint style="info" %}
This option has no effect unless `send_unsupported_to_jdownloader` is `true`
{% endhint %}

## `jdownloader_download_dir`

| Type             | Default |
| ---------------- | ------- |
| `Path` or `null` | `null`  |

The `download_dir` jdownloader will use. A `null` value (the default) will make jdownloader use the same `download_dir` as Cyberdrop-DL. Use this option as path mapping when jdownloader is running on a different host / docker.

{% hint style="info" %}
This option has no effect unless `send_unsupported_to_jdownloader` is `true`
{% endhint %}

## `jdownloader_whitelist`

| Type                | Default |
| ------------------- | ------- |
| `list[NonEmptyStr]` | `[]`    |

List of domain names. An unsupported URL will only be sent to jdownloader if its host is found on the list. An empty whitelist (the default) will disable this functionality, sending any unsupported URL to jdownloader.

{% hint style="info" %}
This option has no effect unless `send_unsupported_to_jdownloader` is `true`
{% endhint %}

## `log_level`

| Type                                    | Default |
| --------------------------------------- | ------- |
| `DEBUG, INFO, WARNING, ERROR, CRITICAL` | `DEBUG` |

Only log messages of this level or higher to the main log file, according to [Python logging levels](https://docs.python.org/3/library/logging.html#levels).

| Level      | Value | Description                                                                                        |
| ---------- | ----- | -------------------------------------------------------------------------------------------------- |
| `DEBUG`    | 10    | Offers detailed information, typically useful to troubleshoot problems                             |
| `INFO`     | 20    | Provides general information about scrape and download progress                                    |
| `WARNING`  | 30    | Potential issues or something that might need attention (e.g. `Login wasn't provided for <FORUM>`) |
| `ERROR`    | 40    | Serious problem preventing Cyberdrop-DL to execute some function                                   |
| `CRITICAL` | 50    | Fatal error that causes Cyberdrop-DL to exit immediately                                           |

{% hint style="info" %}
Using anything other that `DEBUG` makes troubleshooting issues harder. Practically speaking, you should _only_ change this if you expect CDL to run for an extended period (with a large number of input URLs) to minimize the log files sizes
{% endhint %}

## `send_unsupported_to_jdownloader`

| Type   | Default |
| ------ | ------- |
| `bool` | `false` |

Cyberdrop-DL has integration with jdownloader. This will allow you to download URLs that Cyberdrop-DL finds but do not support. However, this setting is disabled by default.

Setting this to `true`, will send unsupported links over.

## `skip_check_for_empty_folders`

| Type   | Default |
| ------ | ------- |
| `bool` | `false` |

After a run is complete, the program will do a check (and remove) any empty files and folders in the download and scan folder.

Setting this to `true` will disable this functionality.

## `skip_check_for_partial_files`

| Type   | Default |
| ------ | ------- |
| `bool` | `false` |

After a run is complete, the program will do a check to see if any partially downloaded files remain in the downloads folder and will notify you of them.

Setting this to `true` will skip this check.

## `slow_download_speed`

| Type       | Default |
| ---------- | ------- |
| `ByteSize` | `0`     |

{% hint style="info" %}
This setting specifies speed and it's interpreted as `<value> / second`. ex: `8MB` means `8MB/s`
{% endhint %}

Downloads with a speed lower than this value for more than 10 seconds will be skipped. Set to `0` to disable
