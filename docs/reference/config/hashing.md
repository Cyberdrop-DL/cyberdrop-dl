---
description: These are options for enable/disable hashing and auto dupe deletion
---

`cyberdrop-dl` maintains an internal database of all downloaded files, indexed by their hashes.
This can be used to automatically delete newly downloaded files if they were downloaded before. To enable auto dupe cleanup:

1. Set `hashing` to `IN_PLACE` or `POST_DOWNLOAD`
2. Set `dedupe` to `true`

# `mode`

| Type                                | Default    |
| ----------------------------------- | ---------- |
| `OFF`,`IN_PLACE` or `POST_DOWNLOAD` | `IN_PLACE` |

1. `OFF`: Do not compute any checksum of downloaded files
2. `IN_PLACE`: compute checksums after each download finishes
3. `POST_DOWNLOAD`: Wait for all downloads to finish and compute checksums for all files at once

```yaml
hashing:
  mode: in_place
```

# `algorithms`

| Type                                | Default                    |
| ----------------------------------- | -------------------------- |
| list of `xxh128`, `md5` or `sha256` | [`xxh128`, `md5`,`sha256`] |

List of checksum algorithms to compute for new downloads. `xxh128` is used for file deduplication and will always be automatically added by CDL if missing from the list.
The additional algorithms are used to skip downloads _before_ they even begin. Some file hosts provide these checksums beforehand.

ex: Gofile provides `md5` and pixeldrain provides `sha256`

```yaml
hashing:
  algorithms:
    - xxh128
    - md5
    - sha256
```

# `dedupe`

## `enabled`

| Type   | Default |
| ------ | ------- |
| `bool` | `false` |

Delete duplicated downloads automatically. Needs `hashing` to be enabled (`IN_PLACE` or `POST_DOWNLOAD`)

Files with matching known hashes from the database are automatically deleted. Only the oldest copy of the files will be kept.

Deletion will only happen if two or more matching files are found during the database search.

{% hint style="warning" %}
dedupe will delete files if you _ever_ downloaded them before, even if the original download no longer exists on disk
{% endhint %}

```yaml
hashing:
  dedupe:
    enabled: true
```

## `use_trash_bin`

| Type   | Default |
| ------ | ------- |
| `bool` | `false` |

Deduped files are sent to the trash bin instead of being deleted

```yaml
hashing:
  dedupe:
    use_trash_bin: true
```
