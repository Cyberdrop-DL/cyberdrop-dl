---
description: How `cyberdrop-dl` decides to skip a file, and how to make it download the file again
icon: clock-rotate-left
---

# Retries and Download History

## How CDL decides to skip a file

There are three independent checks. A file is skipped if **any** of them matches.

1. **Download history**: the `media` table in the database, keyed by site and URL path. An entry is created when a download starts and marked as completed when it finishes.
2. **Known hashes**: the hash table in the database. This only applies when the site reports a checksum before the download starts (ex: GoFile reports `md5`, pixeldrain reports `sha256`) and the algorithm is listed in [`hashing.algorithms`](config/hashing.md).
3. **The file on disk**: if a file already exists at the target path and its size matches the size the server reports, CDL skips the download and marks the entry as completed in the database.

Checks 1 and 2 happen while scraping, before any download request is made. Check 3 happens right before the download starts.

{% hint style="warning" %}
No option disables check 3. To download a file you already have, you must first move, rename or delete it, or use a different `--download-folder`.
{% endhint %}

## What each option does

| Option             | History check | Hash check | On disk check |
| ------------------ | ------------- | ---------- | ------------- |
| _(defaults)_       | on            | on         | on            |
| `--ignore-history` | **off**       | **off**    | on            |
| `--ignore-hashes`  | on            | **off**    | on            |

`--ignore-history` only stops CDL from _reading_ the database. New downloads are still recorded, so the next run without the option will skip them again.

`--ignore-history` also disables auto dedupe at the end of the run, since deduping compares new files against the same hash table.

Neither option has anything to do with caching. CDL does not cache HTTP responses. Every run requests every page live.

## The `retry` command

`retry` takes no URLs. It reads referer URLs already stored in the database and scrapes them again.

```shell
cyberdrop-dl retry failed   # entries that were never marked as completed
cyberdrop-dl retry all      # every entry, completed or not
```

`retry failed` covers interrupted runs, download errors and files that were rejected by a size or duration limit you have since changed.

Files rejected before the download started (by `skip_hosts`, a filename regex, a file type filter, etc.) never reach the database, so `retry` will not find them. Scrape those URLs again with `download` instead.

{% hint style="info" %}
`retry all` does not re-download the files you already have. The URLs go through the normal scraping process, so all three checks above still apply.

What it does is visit each referer again, which finds files added to those albums, posts and threads since your last run. Add `--ignore-history` if you want to download everything again.
{% endhint %}

Both subcommands accept the same options:

### `--from` and `--to`

Limit the retry to entries added to the database within a date range. The date used is when CDL first attempted the download, not when it completed.

`--from` includes the given day. `--to` excludes it. The default range is everything up to and including today.

```shell
cyberdrop-dl retry failed --from 2026-09-01 --to 2026-09-08
```

### `--force-original-path`

Download each file to the exact path recorded in the database, ignoring `download_folder`, `subfolders` and every other path option.

```shell
cyberdrop-dl retry failed --force-original-path
```

{% hint style="warning" %}
This can write files outside of `--download-folder`. Use it to resume into an existing folder structure, not to start a new one.
{% endhint %}

The main menu asks whether to use the original path after you select `Retry failed downloads`.

### Config options

`retry` accepts every config option that `download` does, so you can combine them:

```shell
cyberdrop-dl retry all --from 2026-08-01 --ignore-history
```

## `skip_and_mark_completed`

[`downloads.skip_and_mark_completed`](config/downloads.md) does the reverse of a retry. It marks every scraped file as completed without downloading anything. Use it to make CDL permanently skip a set of URLs.

## Common scenarios

| What happened                                        | What to run                                             | What CDL does                                                       |
| ---------------------------------------------------- | ------------------------------------------------------- | ------------------------------------------------------------------- |
| A run was interrupted or some downloads errored      | `cyberdrop-dl retry failed`                             | Re-downloads only the files that never completed                     |
| An album you downloaded last month has new files     | `cyberdrop-dl retry all --from 2026-08-01`              | Re-visits those albums, downloads the new files, skips the old ones  |
| You deleted some downloaded files and want them back | `cyberdrop-dl download <url> --ignore-history`          | Ignores the database and downloads them again                        |
| You want to replace files you still have on disk     | Move or rename them, then run with `--ignore-history`   | Without moving them, the on disk check skips the download            |
| You want CDL to never download a set of URLs         | `cyberdrop-dl download <url> --skip-and-mark-completed` | Marks them as completed without downloading                          |
| You want to start over from scratch                  | Delete the database file                                | `cyberdrop-dl database file` prints its path                         |

## Options that no longer exist

Older guides and issues mention options that have since been removed:

- `--disable-cache`, `file_host_cache_expire_after` and `forum_cache_expire_after` were removed in v9.0.0. CDL no longer caches HTTP responses, so every run scrapes live and there is nothing to disable.
- `--retry-maintenance` was removed.
- `--retry-all` and `--retry-failed` were replaced by the `retry` command.

{% hint style="info" %}
The `cyberdrop-dl cache` command manages the program's JSON cache file (settings such as the last version check). It has nothing to do with scraping or download history.
{% endhint %}
