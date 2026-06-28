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
Usage: cyberdrop-dl COMMAND [OPTIONS]

Bulk asynchronous downloader for multiple file hosts

╭─ Commands ───────────────────────────────────────────────────────────────────────────────────────╮
│ cache      Cache operations                                                                      │
│ cleanup    Perform maintenance tasks                                                             │
│ config     Config file operations                                                                │
│ database   Commands for managing the database                                                    │
│ download   Download URLs                                                                         │
│ hash       Compute and save hashes of every file in a folder (recursively)                       │
│ report     Generate and display information about the system                                     │
│ retry      Retry downloads from the database                                                     │
│ show       Show a list of all supported sites                                                    │
│ --help -h  Display this message and exit.                                                        │
│ --version  Display application version.                                                          │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
╭─ Parameters ─────────────────────────────────────────────────────────────────────────────────────╮
│ --input-file -i  Text/HTML file with URL(s) to download                                          │
│ --config-file    YAML file to use as config                                                      │
│ --cache-file     JSON file to use as cache                                                       │
│ --database-file  SQLite file to use as database                                                  │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
```
<!-- END_CLI_OVERVIEW -->
