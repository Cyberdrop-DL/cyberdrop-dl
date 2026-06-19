---
description: Common questions or problems.
icon: comments-question-check
layout:
  title:
    visible: true
  description:
    visible: true
  tableOfContents:
    visible: true
  pagination:
    visible: true
---

# Frequently Asked Questions

## What does this do?

This is a bulk downloader for the supported sites. It supports resumable downloading (you can close and reopen the program at any time and it will pick up where it left off), and keeps track of your download history to avoid downloading files you've already downloaded in the past.

## How do I update?

If you are using one of the provided start files, it should do so automatically. Keep in mind that they will only update to the newest release of the same major version. ex: if you are using v9 start scripts, they will update to the latest v9 release.
This is beacuse every new major relase has breaking changes and is not safe to automatically update to them.
Each time there is a new major release, you will need to download new start scripts. Be sure to read the changelog to know about the breaking changes. You may need to perform some manual action to update successfully

## Why do i get `DDoS-Guard` error downloading from `x` site?

You may need to import cookies. Follow the instructions here: [How to extract cookies (DDoSGuard or login errors) #839](https://github.com/Cyberdrop-DL/cyberdrop-dl/discussions/839)

## I'm trying to report a bug and they ask me for a logs file. Where is this file?

By default, it'll be in `./AppData/configs/Default/logs/`

The `AppData` folder is created inside the folder where you run cyberdrop-dl from

## What does `SCRAPE_ERRORS` and `DOWNLOAD_ERRORS` mean?

Quite simply, almost all of them you see will be HTTP Status codes. Such as: 404 - Not Found (dead link)

You check [this page to learn about what each error code means](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status).

These error are **NOT** bugs. They are errors from the website itself. The only exception is `422 Unprocessable Entity`, which `cyberdrop-dl` uses to report some internal errors

{% hint style="info" %}
"Unknown" errors are **definitely** bugs. Please report them on the issue tracker: <https://github.com/Cyberdrop-DL/cyberdrop-dl/issues>
{% endhint %}

## Why are all the files skipped?

The program tracks your download history and will skip any files you've previously downloaded to avoid duplicates. You can disable this behavior by using the `--ignore-history` CLI argument or setting `ignore_history` to `true` in the config

## `cyberdrop-dl` is not a recognized internal command

This issue is caused by an improper installation.

Please revisit the [Getting Started](getting-started/README.md) guide and follow the steps provided to reinstall or use one of the latest start scripts

## How do I scrape forum threads?

You need to import cookies to use as authentication for those sites. Follow the instructions here: [How to extract cookies (DDoSGuard or login errors) #839](https://github.com/Cyberdrop-DL/cyberdrop-dl/discussions/839)

## Why are the filenames the way they are?

Filenames are taken directly from the source website. Blame whoever uploaded it.
