---
description: These are some general settings that will be used regardless of which config is loaded
---

# General

## `download_folder`

| Type   | Default     |
| ------ | ----------- |
| `Path` | `Downloads` |

The path to the folder you want `cyberdrop-dl` to download files to.

## `dump_json`

| Type   | Default |
| ------ | ------- |
| `bool` | `False` |

If enabled, CDL will created a [json lines](https://jsonlines.org/) files with the information about every file downloaded in the current run. The path to this file will be the same as `--main-log` but with the extension `.results.jsonl`

Each line in the file will contain the following details (this may change on future versions):

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

## `max_file_name_length`

| Type          | Default |
| ------------- | ------- |
| `PositiveInt` | `95`    |

This is the maximum number of characters a filename should have. CDL will truncate filenames longer that this.

## `max_folder_name_length`

| Type          | Default |
| ------------- | ------- |
| `PositiveInt` | `95`    |

This is the maximum number of characters a folder should have. CDL will truncate folders longer that this.

## `required_free_space`

| Type       | Default | Restrictions |
| ---------- | ------- | ------------ |
| `ByteSize` | `5GB`   | `>=512MB`    |

This is the minimum amount of free space require to start new downloads.

{% hint style="info" %}
If you set a value lower than `512MB`, CDL will override it with `512MB`
{% endhint %}

## `cookies`

| Type             | Default |
| ---------------- | ------- |
| `Path` or `None` | `None`  |

Path to a file/folder with Netscape cookies with a `.txt` extension. If the path is a folder, all `.txt` in the folder are read (Non recursive)

These can be used for websites that require login or to pass DDoS-Guard challenges.

You can extract the cookies from your browser using tools like [cookie-editor](https://cookie-editor.com) and save them as a `.txt` file.
The file must be a Netscape formatted cookie file. You can use any name for the file as long as it has a `.txt` extension.

See: [How to extract cookies (DDoSGuard or login errors) #839](https://github.com/Cyberdrop-DL/cyberdrop-dl/discussions/839) for detailed instructions

{% hint style="info" %}
Multiple cookie files are supported. You could have a `SocialMediaGirls.txt` file and a `cyberdrop.txt` file, for example
{% endhint %}

{% hint style="warning" %}
The `user-agent` config value **MUST** match the `user-agent` of the browser from which you imported the cookies. If they do not match, the cookies will not work
{% endhint %}

## `deep_scrape`

| Type   | Default |
| ------ | ------- |
| `bool` | `false` |

`cyberdrop-dl` uses a some tricks to try to reduce the number of requests it needs to make while scraping a site. However, this may cause a few links to be skipped.
Use `--deep-scrape` to disable this and always make a new requests if required.

{% hint style="warning" %}
Use this option only when absolutely necessary, as it will significantly increase the number of requests being made.

For example, scraping an album normally takes one single request.

With `--deep-scrape`, CDL will make `n` requests per album, where `n` is the total number of items in the album
{% endhint %}

```yaml
deep_scrape: false
```

## `delete_partial_files`

| Type   | Default |
| ------ | ------- |
| `bool` | `false` |

Files downloaded by CDL have a `.part` extension (`.cdl_hls` for HLS segments). CDL only changes the extension to the original one after a successful download.
This allows CDL to resume downloads on subsequent runs.

Setting this to `true` will delete any `.part` and `.cdl_hls` files in the download folder.

```yaml
delete_partial_files: false
```

## `ignore_history`

| Type   | Default |
| ------ | ------- |
| `bool` | `false` |

By default, the program tracks your downloads in a database to prevent downloading the same files multiple times, to save time and reduce strain on the servers you're downloading from.

Setting this to `true` will cause the program to ignore the database, and will allow you to re-download files.

## `delete_empty_folders`

| Type   | Default |
| ------ | ------- |
| `bool` | `false` |

After a run is complete, the program will do a check (and remove) any empty files and folders in the download and scan folder.

Setting this to `false` will disable it.

```yaml
delete_empty_folders: true
```

## `skip_check_for_partial_files`

| Type   | Default |
| ------ | ------- |
| `bool` | `false` |

After a run is complete, the program will do a check to see if any partially downloaded files remain in the downloads folder and will notify you of them.

Setting this to `true` will skip this check.

## `mtime`

| Type   | Default |
| ------ | ------- |
| `bool` | `True`  |

By default the program will do it's absolute best to try and find the upload date of a file. It'll then set the `last modified` and `last accessed` dates on the file to match. On Windows and macOS, it will also try to set the `created` date.

Setting this to `false` will disable this function, and the dates for those metadata entries will be the date the file was downloaded.

```yaml
mtime: true
```

## `max_thread_depth`

| Type             | Default |
| ---------------- | ------- |
| `NonNegativeInt` | 0       |

{% hint style="warning" %}
It is not recommended to set this above the default value of `0`, as there is a high chance of infinite nesting in certain cases.

For example, when dealing with Megathreads, if a Megathread is linked to another Megathread, you could end up scraping an undesirable amount of data.
{% endhint %}

Restricts how many levels deep the scraper is allowed to go while scraping a thread

A value of `0` means only the top level thread will be scraped

{% hint style="info" %}
This setting is hardcoded to `0` for Discourse sites
{% endhint %}

### Example

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

## `max_thread_folder_depth`

| Type                       | Default |
| -------------------------- | ------- |
| `NonNegativeInt` or `None` | `None`  |

Restricts the max number of nested folders CDL will create when `max_thread_depth` is greater that 0

Values:

- `None`: Create as many nested folders as required (AKA, the same number as `max_thread_depth` allows)
- `0`: Do not create subfolders, use a flat structure for any nested thread.
- `1+`: Create a max of `n` folders

### Example

- With `max_thread_folder_depth` = None:

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
