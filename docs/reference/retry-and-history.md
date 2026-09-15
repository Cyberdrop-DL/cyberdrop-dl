---
description: How `cyberdrop-dl` decides to skip a file, and how to make it download the file again
icon: clock-rotate-left
---

# Retries and Download History

## How CDL decides to skip a file

There are four independent checks. A file is skipped if **any** of them matches.

1. **The page was already downloaded**: CDL looks for a completed entry whose referer is the page it is about to request. If there is one, it skips the entire page without requesting it. Most sites do this, but not all.
2. **Download history**: the `media` table in the database, keyed by site and URL path. An entry is created when a download starts and marked as completed when it finishes.
3. **Known hashes**: the hash table in the database. This only applies when the site reports a checksum before the download starts (ex: GoFile reports `md5`, pixeldrain reports `sha256`) and the algorithm is listed in [`hashing.algorithms`](config/hashing.md).
4. **The file on disk**: if a file already exists at the target path and its size matches the size the server reports, CDL skips the download and marks the entry as completed in the database.

Checks 1 to 3 happen while scraping. Check 1 skips a whole page, the other two skip individual files. Check 4 happens right before the download starts.

{% hint style="warning" %}
No option disables check 4. To download a file you already have, you must first move, rename or delete it, or use a different `--download-folder`.
{% endhint %}

## What each option does

| Option             | 1. Page | 2. History | 3. Hashes | 4. On disk |
| ------------------ | ------- | ---------- | --------- | ---------- |
| _(defaults)_       | on      | on         | on        | on         |
| `--ignore-history` | **off** | **off**    | **off**   | on         |
| `--ignore-hashes`  | on      | on         | **off**   | on         |

`--ignore-history` only stops CDL from _reading_ the database. New downloads are still recorded, so the next run without the option will skip them again.

`--ignore-history` also disables auto dedupe at the end of the run, since deduping compares new files against the same hash table.

Neither option has anything to do with caching. CDL does not cache HTTP responses, so there is nothing stored from an earlier run that can go stale. The only reason a page is not requested again is check 1, and `--ignore-history` disables it.

## The `retry` command

`retry` takes no URLs. It reads referer URLs already stored in the database and scrapes them again.

```shell
cyberdrop-dl retry failed   # entries that were never marked as completed
cyberdrop-dl retry all      # every entry, completed or not
```

`retry failed` covers interrupted runs, download errors and files that were rejected by a size or duration limit you have since changed.

Files rejected before the download started (by `skip_hosts`, a filename regex, a file type filter, etc.) never reach the database, so `retry` will not find them. Scrape those URLs again with `download` instead.

{% hint style="info" %}
`retry all` does not re-download the files you already have. The URLs go through the normal scraping process, so every check above still applies. Add `--ignore-history` if you want to download everything again.
{% endhint %}

`retry all` is most useful combined with another option: with `--ignore-history` to download everything in the database again, or with `--force-original-path` to restore files to the folders they came from.

On its own it rarely finds anything new. The URL it re-visits is the referer recorded for each file, which is usually the individual file page and not the album, profile or thread the file came from, so new items added to those are never discovered. On the many sites that use check 1, those recorded pages are skipped without a request.

To pick up new files in an album, profile or thread, scrape that URL again with `download`. CDL downloads what is new and skips what you already have.

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
| An album you downloaded last month has new files     | `cyberdrop-dl download <album url>`                     | Scrapes the album again, downloads the new files, skips the old ones |
| You want every file in the database again            | `cyberdrop-dl retry all --ignore-history`               | Re-downloads everything CDL has ever recorded                        |
| You deleted some downloaded files and want them back | `cyberdrop-dl download <url> --ignore-history`          | Ignores the database and downloads them again                        |
| You want to replace files you still have on disk     | Move or rename them, then run with `--ignore-history`   | Without moving them, the on disk check skips the download            |
| You want CDL to never download a set of URLs         | `cyberdrop-dl download <url> --skip-and-mark-completed` | Marks them as completed without downloading                          |
| You want to start over from scratch                  | Delete the database file                                | `cyberdrop-dl database file` prints its path                         |

## Options that no longer exist

Older guides and issues mention options that have since been removed:

- `--disable-cache`, `file_host_cache_expire_after` and `forum_cache_expire_after` were removed in v9.0.0. CDL no longer caches HTTP responses, so there is nothing to disable. A page is only skipped by check 1 above.
- `--retry-maintenance` was removed.
- `--retry-all` and `--retry-failed` were replaced by the `retry` command.

{% hint style="info" %}
The `cyberdrop-dl cache` command manages the program's JSON cache file (settings such as the last version check). It has nothing to do with scraping or download history.
{% endhint %}
