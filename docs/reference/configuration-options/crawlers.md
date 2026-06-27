# Crawlers

## `disabled`

| Type                | Default | Additional Info                                                      |
| ------------------- | ------- | -------------------------------------------------------------------- |
| `list[NonEmptyStr]` | `[]`    | This is an [`AdditiveArg`](../special_setting_types.md#additiveargs) |

You can supply a list of crawlers to disable for the current run. This will make CDL completely ignore the crawler, as if the site was not supported. However, links from the site will still be processed by Real-Debrid (if enabled), Jdownloader (If enabled) and the Generic crawler (If enabled), in that order.

The list should be valid crawlers names. The name of the crawler is the name of the primary site they support. ex: `4Chan`, `Bunkrr`, `Dropbox`

Crawlers names correspond to the column `site` in the [supported sites page](https://script-ware.gitbook.io/cyberdrop-dl/reference/supported-websites#supported-sites).

## Tiktok

### `original`

| Type   | Default |
| ------ | ------- |
| `Bool` | `false` |

By default, CDL will download the "optimized for streaming" version of tiktok videos. Setting this option to `True` will download videos in original (source) quality.

`_original` will be added as a suffix to their filename.

{% hint style="warning" %}
This will make video downloads several times slower

When it is set to `False` (the default) CDL can download 50 videos with a single request.
When it is set to `True` , CDL needs to make at least 3 requests _per_ video to download them.

There's also a daily limit of the API CDL uses: 5000 requests per day per IP

Setting this option to `True` will consume the daily limit faster
{% endhint %}
