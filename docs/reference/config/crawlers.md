# `disabled`

| Type                | Default | Additional Info                                                      |
| ------------------- | ------- | -------------------------------------------------------------------- |
| `list[NonEmptyStr]` | `[]`    | This is an [`AdditiveArg`](../special_setting_types.md#additiveargs) |

You can supply a list of crawlers to disable for the current run. This will make CDL completely ignore the crawler, as if the site was not supported.
However, links from the site will still be processed by Real-Debrid (if enabled), JDownloader (If enabled) and the Generic crawler (If enabled), in that order.

The list should be valid crawlers names. The name of the crawler is the name of the primary site they support. ex: `4Chan`, `Mega.nz`, `Dropbox`

You can get the crawler' name from the [supported sites page](https://script-ware.gitbook.io/cyberdrop-dl/reference/supported-websites#supported-sites)
The name of the crawer is the title of their section in the page (in bold).

```yaml
crawlers:
  generic:
    chevereto: []
    discourse: []
    kvs: []
    wordpress_html: []
    wordpress_media: []
```

# `generic`

Generic crawlers are designed to work on any site that uses a **specific** framework. Users can supply a list of sites to map to these crawlers,
and CDL will then be able to download from them. The URL in the list should be the primary URL of the site. ex: `https://forums.docker.com/`

Supported generic crawlers:

- `chevereto`: This works on any site that uses [Chevereto](https://chevereto.com//).

- `discourse`: This works on any forum that uses [Discourse](https://www.discourse.org/).

- `kvs`: Works on any tube site using [Kernel Video Sharing](https://www.kernel-video-sharing.com/en/).
  Basically, any site that looks like one of these: <https://www.kernel-video-sharing.com/en/themes/>, ex: <https://www.kvs-demo.com/>

- `wordpress_media`: This crawler should work on any [WordPress](https://wordpress.com/) site where content primarily consists of images or galleries. The images need to be hosted on the site itself. It requires sites to have a public WordPress REST API.

- `wordpress_html`: This works on any WordPress site. It scrapes the actual HTML of the site, which means it works on sites that have embedded third-party media like videos or links to hosting sites. It is always slower than `wordpress_media`.

## `chevereto`

| Type            | Default |
| --------------- | ------- |
| `list[HttpURL]` | `[]`    |

## `discourse`

| Type            | Default |
| --------------- | ------- |
| `list[HttpURL]` | `[]`    |

## `kvs`

| Type            | Default |
| --------------- | ------- |
| `list[HttpURL]` | `[]`    |

## `wordpress_media`

| Type            | Default |
| --------------- | ------- |
| `list[HttpURL]` | `[]`    |

## `wordpress_html`

| Type            | Default |
| --------------- | ------- |
| `list[HttpURL]` | `[]`    |

# Bandcamp

## `formats`

| Type                                                                          | Default                                                               |
| ----------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| List of `mp3-320`, `mp3`, `aac-hi`, `wav`, `flac`, `vorbis`, `aiff` or `alas` | [`mp3-320`, `mp3`, `aac-hi`, `wav`, `flac`, `vorbis`, `aiff`, `alas`] |

Format to choose for downloads (if available), ordered by preference.

```yaml
crawlers:
  bandcamp:
    formats:
      - mp3-320
      - mp3
      - aac-hi
      - wav
      - flac
      - vorbis
      - aiff
      - alas
```

# Clyp.it

## `prefer_mp3`

| Type   | Default |
| ------ | ------- |
| `Bool` | `false` |

Download audios as `.mp3` files even if WAV (high quality) versions are available

# OnePace

## `prefer_dub`

| Type   | Default |
| ------ | ------- |
| `Bool` | `false` |

Download episodes with english audio tracks instead of japanese (if available)

# Tiktok

## `original`

| Type   | Default |
| ------ | ------- |
| `Bool` | `false` |

By default, CDL will download the "optimized for streaming" version of tiktok videos. Setting this option to `True` will download videos in original (source) quality.

`_original` will be added as a suffix to their filename.

{% hint style="warning" %}
This will make video downloads several times slower

When it is set to `false` (the default) CDL can download 50 videos with a single request.
When it is set to `true` , CDL needs to make at least 3 requests _per_ video to download them.

There's also a daily limit of the API CDL uses: 5000 requests per day per IP

Setting this option to `true` will consume the daily limit faster
{% endhint %}
