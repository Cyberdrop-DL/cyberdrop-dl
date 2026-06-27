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

This is a bulk downloader for several sites on the internet. It supports resuming downloads (you can close and reopen
the program at any time and it will pick up where it left off), and keeps track of your download history and hashes to avoid
downloading files you've already downloaded in the past.

## How do I update?

If you are using one of the provided start files, it should do so automatically. Keep in mind that they will only update to
the newest release of the same major version. ex: if you are using v9 start scripts, they will update to the latest v9 release.

This is because every new major release has breaking changes and is not safe to automatically update to them.
Each time there is a new major release, you will need to download new start scripts. Be sure to read the changelog to know about the breaking changes.
You may need to perform some manual actions to update successfully

## Why do I get `DDoS-Guard` error downloading from `x` site?

DDoS-Guard is a protecting some websites use to block automated activity from bots/applications. You can visit the site on your browser to pass
the DDoS-Guard check, export the cookies from your browser and them to import them into `cyberdrop-dl`.

Follow the instructions here: [How to extract cookies (DDoSGuard or login errors) #839](https://github.com/Cyberdrop-DL/cyberdrop-dl/discussions/839)

## What does `SCRAPE_ERRORS` and `DOWNLOAD_ERRORS` mean?

Quite simply, almost all of them will be HTTP Status codes. Such as: 404 - Not Found (dead link)

You can check [this page to learn about what each error code means](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status).

These errors are **NOT** bugs. They are errors from the website itself. If your try to download the files manually from your browser you will most likely
get the same error.

The only exception is `422 Unprocessable Entity`, which `cyberdrop-dl` uses to report some internal errors

{% hint style="info" %}
"Unknown" errors are **definitely** bugs. Please report them on the issue tracker: <https://github.com/Cyberdrop-DL/cyberdrop-dl/issues>
{% endhint %}

## Why do Simpcity URLs show as "Unsupported"?

Support for SimpCity was removed on v5.6.3 in response to a request by the site admins. The site could not keep up with the high amount of traffic generated
by `cyberdrop-dl` on top of the constant DDOS attacks they receive.

## Why are all the files skipped?

The program tracks your download history and will skip any files you've been previously downloaded to avoid duplicates.
You can disable this behavior by using the `--ignore-history` CLI argument or setting `ignore_history` to `true` in your config file

## `cyberdrop-dl` is not a recognized internal command

This issue is caused by an improper installation.

Please revisit the [Getting Started](getting-started/README.md) guide and follow the steps provided to reinstall `cyberdrop-dl` with the start scripts.

Run the `remove` file from the start scripts and them run the `install` file. Your config and database files will not be affected

## How do I scrape forum threads?

You need to import cookies to use as authentication for those sites.

Follow the instructions here: [How to extract cookies (DDoSGuard or login errors) #839](https://github.com/Cyberdrop-DL/cyberdrop-dl/discussions/839)

## Why are the filenames the way they are?

Filenames are taken directly from the source website. Blame whoever uploaded it.
