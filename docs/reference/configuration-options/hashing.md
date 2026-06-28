---
description: These are options for enable/disable hashing and auto dupe deletion
---

# Hashing

`cyberdrop-dl` maintains an internal database of all downloaded files, indexed by their hashes.
This can be used to automatically delete newly downloaded files if they were downloaded before. To enable auto dupe cleanup:

1. Set `hashing` to `IN_PLACE` or `POST_DOWNLOAD`
2. Set `dedupe` to `true`

## `mode`

| Type      | Default | Restrictions                                 |
| --------- | ------- | -------------------------------------------- |
| `HASMODE` | `OFF`   | Must be `OFF`, `IN_PLACE` or `POST_DOWNLOAD` |

There are three possible options for hashing:

1. `OFF`: disables hashing
2. `IN_PLACE`: performs hashing after each download
3. `POST_DOWNLOAD`: performs hashing after all downloads have completed

```yaml
hashing:
  mode: in_place
```

## `algorithms`

| Type                                | Default                    |
| ----------------------------------- | -------------------------- |
| list of `xxh128`, `md5` or `sha256` | [`xxh128`, `md5`,`sha256`] |

List of checksum algorithms to compute for new downloads. `xxh128` will always be computed even if not present on this list as it is used for file deduplication.
The aditional algorithm are used to skip downloads _before_ the downloads even begins as some file host provide the checksum
information of their files. ex: Gofile provides `md5` and pixeldrain `sha256`

```yaml
hashing:
  algorithms:
    - xxh128
    - md5
    - sha256
```

## `dedupe`

### `enabled`

| Type   | Default |
| ------ | ------- |
| `bool` | `false` |

Delete duplicates downloads automatically. Needs `hashing` to be enabled

Files with matching known hashes from the database are automatically deleted. Only the oldest copy pf the files will be kept.

Deletion will only occur if two or more matching files are found during the database search.

{% hint style="warning" %}
dedupe will delete files if you have _ever_ downloaded them before, even if the original download no longer exists on disk
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
