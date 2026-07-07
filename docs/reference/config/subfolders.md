# `create`

| Type   | Default |
| ------ | ------- |
| `bool` | `true`  |

Normally, downloads may create a folder structure like:

> `downloads/folderA/folderB/folderC/image.jpg`

If this si set to `false` will only create a single folder per URL place all its children inside it:

> `Downloads/folderA/image.jpg`

```yaml
subfolders:
  create: true
```

# `include`

## `album_id`

| Type   | Default |
| ------ | ------- |
| `bool` | `false` |

Include the album ID (random alphanumeric string) of the album in the subfolder name.

## `thread_id`

| Type   | Default |
| ------ | ------- |
| `bool` | `false` |

Include the thread ID (random alphanumeric string) of the forum thread in the subfolder name.

## `domain`

| Type   | Default |
| ------ | ------- |
| `bool` | `false` |

Include "(DOMAIN)" of the website in the subfolder name

```yaml
subfolders:
  include:
    album_id: false
    domain: true
    thread_id: false
```

# `separate_posts`

## `enabled`

| Type   | Default |
| ------ | ------- |
| `bool` | `false` |

Setting this to `true` will separate content from forum and site posts into separate folders.

This option only works with sites that have 'posts':

- `Forums`
- `Discourse`
- `Tiktok`
- `Coomer`, `Kemono` and `Nekohouse`.

For some sites, this value is hardcorded to `true` because each post is always an individual page:

- `Wordpress`
- `eFukt`

```yaml
subfolders:
  separate_posts:
    enabled: false
```

## `format`

| Type          | Default     |
| ------------- | ----------- |
| `NonEmptyStr` | `{default}` |

This is the format for the directory created when using `--separate-posts`.

Unique Path Flags:

> `date`: date of the post. This is a python `datetime` object
>
> `id`: The post id. This is always a `string`, even if some sites use numbers
>
> `number`: This no longer means anything. Currently, it always has the same value as `id`
>
> `title`: post title. This is a `string`

{% hint style="warning" %}
Not all sites support all possible flags.

If you use a format with a field that the site does not support, CDL will replace it with `UNKNOWN_<FIELD_NAME>`

{% endhint %}

Setting it to `{default}` will use the default format, which is different for each crawler:

| Site                                  | Default Format                     |
| ------------------------------------- | ---------------------------------- |
| `Forums (Xenforo/vBulletin/Invision)` | `{date} - {id} - {title}`          |
| `Discourse`                           | `{date} - {id} - {title}`          |
| `Reddit`                              | `{title}`                          |
| `WordPress`                           | `{date:%Y-%m-%d} - {id} - {title}` |
| `eFukt`                               | `{date:%Y-%m-%d} {title}`          |
| `Tiktok`                              | `{date:%Y-%m-%d} - {id}`           |

A date without a `format_spec` defaults to ISO 8601 format

You can use any valid format string supported by python, with the following restrictions:

- You can not have positional arguments in the format string. ex: `post {0} from date {1}`
- You can not have unnamed fields in the format string. ex: `post {} from date {}`
- You can not perform operations within the format string. ex: `post {id + 1} from date {date}`
- All the fields named in the format string must be valid fields for that format option. CDL will validate this at startup

```yaml
subfolders:
  separate_posts:
    format: "{default}"
```
