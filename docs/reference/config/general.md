All setting on this section go at the root of the config file

# `download_folder`

| Type   | Default                  |
| ------ | ------------------------ |
| `Path` | `downloads/cyberdrop-dl` |

The path to the folder you want `cyberdrop-dl` to download files to.

```yaml
download_folder: downloads/cyberdrop-dl
```

# `dump_json`

| Type   | Default |
| ------ | ------- |
| `bool` | `False` |

If enabled, CDL will created a [json lines](https://jsonlines.org/) files with the information about every file downloaded in the current run.
The path to this file will be the same as `--log-file` but with the extension `.results.jsonl`

Each line in the file will contain the following details:

```json
{
  "url": "https://store9.gofile.io/download/web/7c88c147-ABCD-4e4d-9a6c-12345678/a_video.mp4",
  "referer": "https://gofile.io/d/ABC123",
  "download_folder": "downloads/cyberdrop-dl/test_album (GoFile)",
  "filename": "0hxte0li0o931lwgcrzbz_source.mp4",
  "original_filename": "a_video.mp4",
  "download_filename": "0hxte0li0o931lwgcrzbz_source.mp4",
  "filesize": 12054723,
  "ext": ".mp4",
  "debrid_link": null,
  "duration": null,
  "album_id": "ABC123",
  "datetime": "2025-01-22T11:00:07",
  "parents": ["https://a_forum.com/threads/<name>.54321/post-123123"],
  "parent_threads": ["https://a_forum.com/threads/<name>.54321"],
  "partial_file": "downloads/cyberdrop-dl/test_album (GoFile)/a_video.mp4.part",
  "complete_file": "downloads/cyberdrop-dl/test_album (GoFile)/a_video.mp4",
  "hash": "xxh128:53ee56b7bfafa31b8780a572e9783df3",
  "downloaded": true,
  "attempts": 1
}
```

```yaml
dump_json: false
```

{% hint style="warning" %}
The schema of this JSON output is NOT stable may change without notice, even on minor version updates
{% endhint %}

# `max_file_name_length`

| Type          | Default |
| ------------- | ------- |
| `PositiveInt` | `95`    |

Maximum number of characters a filename should have. CDL will truncate filenames longer that this.

```yaml
max_file_name_length: 95
```

# `max_folder_name_length`

| Type          | Default |
| ------------- | ------- |
| `PositiveInt` | `60`    |

Maximum number of characters a folder should have. CDL will truncate folders longer that this.

```yaml
max_folder_name_length: 60
```

# `min_free_space`

| Type       | Default | Restrictions |
| ---------- | ------- | ------------ |
| `ByteSize` | `5GiB`  | `>=512MiB`   |

This is the minimum amount of free space require to start new downloads.

```yaml
min_free_space: 5.0GiB
```

{% hint style="info" %}
Values lower than `512MB` will always be replaced with `512MB`
{% endhint %}

# `cookies`

| Type             | Default |
| ---------------- | ------- |
| `Path` or `null` | `null`  |

Path to a file/folder with Netscape cookies. All cookie files must have a `.txt` extension. If the path is a folder, all `.txt` in the folder are read (non recursive)

These can be used for websites that require login or to pass DDoS-Guard challenges.

You can extract the cookies from your browser using tools like [cookie-editor](https://cookie-editor.com) and save them as a `.txt` file.
The file must be a Netscape formatted cookie file. You can use any name for the file as long as it has a `.txt` extension.

See: [How to extract cookies (DDoSGuard or login errors) #839](https://github.com/Cyberdrop-DL/cyberdrop-dl/discussions/839) for detailed instructions

{% hint style="warning" %}
The `user-agent` config value **MUST** match the `user-agent` of the browser from which you imported the cookies. If they do not match, the cookies will not work
{% endhint %}

# `deep_scrape`

| Type   | Default |
| ------ | ------- |
| `bool` | `false` |

`cyberdrop-dl` uses a some tricks to try to reduce the number of requests it needs to make while scraping a site. However, this may cause a few links to be skipped.
Use `--deep-scrape` to disable this and always make a new requests if required.

```yaml
deep_scrape: false
```

{% hint style="warning" %}
Use this option only if when absolutely necessary, as it will significantly increase the number of requests being made.

For example, scraping an album normally takes one single request.

With `--deep-scrape`, CDL will make `n` requests per album, where `n` is the total number of items in the album
{% endhint %}

# `delete_partial_files`

| Type   | Default |
| ------ | ------- |
| `bool` | `false` |

Files downloaded by CDL have a `.part` extension (or `.cdl_hls` for HLS segments) that will replaced with the original extension the download reaches 100%.

This allows CDL to resume downloads on subsequent runs.

Set `true` will delete any `.part` and `.cdl_hls` files in the download folder at the end of a session.

```yaml
delete_partial_files: false
```

# `ignore_history`

| Type   | Default |
| ------ | ------- |
| `bool` | `false` |

By default, the program tracks your downloads in a database to prevent downloading the same file multiple times, to save time and reduce load on the servers you're downloading from.

Setting this to `true` to disable it, ignoring the database and allowing you to re-download files.

```yaml
ignore_history: false
```

# `delete_empty_folders`

| Type   | Default |
| ------ | ------- |
| `bool` | `false` |

Check (and remove) any empty files and folders in the `--download-folder` and `--sort.input_folder` at the end of a session.

```yaml
delete_empty_folders: true
```

# `mtime`

| Type   | Default |
| ------ | ------- |
| `bool` | `True`  |

CDL dos it's absolute best to extract the upload date of a files.

By default, this date will be set as the `last modified` and `last accessed` date on the downloaded file.

On Windows and macOS, it will also try to set the `created` date.

Change this to `false` and those dates will be the current datetime instead

```yaml
mtime: true
```

# `max_thread_depth`

| Type             | Default |
| ---------------- | ------- |
| `NonNegativeInt` | 0       |

Restricts how many levels deep the scraper is allowed to go while scraping a thread

A value of `0` means only the top level thread will be scraped

```yaml
max_thread_depth: 0
```

{% hint style="info" %}
This setting is hardcoded to `0` for Discourse sites
{% endhint %}

{% hint style="warning" %}
It is not recommended to set this above the default value of `0`, as there is a high chance of infinite nesting in certain cases.

For example, when dealing with Megathreads, if a Megathread is linked to another Megathread, you could end up scraping an undesirable amount of data.
{% endhint %}

## Example

Consider CDL finds the following sub-threads while scraping an input URL:

```shell
└── thread_01
    ├── thread_02
    ├── thread_03
    │   ├── thread_09
    │   ├── thread_10
    │   └── thread_11
    ├── thread_04
    ├── thread_05
    ├── thread_06
    ├── thread_07
    │   └── thread_12
    └── thread_08
```

- With `max_thread_depth` = 0, CDL will only download files in `thread_01`, all the other threads will be ignored
- With `max_thread_depth` = 1, CDL will only download files in `thread_01` to `thread_08`. All threads from `thread_09` to `thread_12` will be ignored
- With `max_thread_depth` >= 2, CDL will download files from all the threads in this case

# `max_thread_folder_depth`

| Type                       | Default |
| -------------------------- | ------- |
| `NonNegativeInt` or `null` | `null`  |

Restricts the max number of nested folders CDL will create when `max_thread_depth` is greater that 0

Values:

- `null`: Create as many nested folders as required (AKA, the same number as `max_thread_depth` allows)
- `0`: Do not create subfolders, use a flat structure for any nested thread.
- `1+`: Create a max of `n` folders

```yaml
max_thread_folder_depth: null
```

## Example

- With `max_thread_folder_depth` = `null`:

```shell
└── thread_01
    ├── thread_02
    ├── thread_03
    │   ├── thread_09
    │   ├── thread_10
    │   └── thread_11
    ├── thread_04
    ├── thread_05
    ├── thread_06
    ├── thread_07
    │   └── thread_12
    └── thread_08
```

- With `max_thread_folder_depth` = 0:

```shell
├── thread_01
├── thread_02
├── thread_03
├── thread_09
├── thread_10
├── thread_11
├── thread_04
├── thread_05
├── thread_06
├── thread_07
├── thread_12
└── thread_08
```

- With `max_thread_folder_depth` = 1:

```shell
└── thread_01
    ├── thread_02
    ├── thread_03
    ├── thread_09
    ├── thread_10
    ├── thread_11
    ├── thread_04
    ├── thread_05
    ├── thread_06
    ├── thread_07
    ├── thread_12
    └── thread_08
```
