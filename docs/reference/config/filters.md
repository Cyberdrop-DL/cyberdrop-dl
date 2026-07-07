# `before`

| Type             | Default | Additional Info                                           |
| ---------------- | ------- | --------------------------------------------------------- |
| `date` or `null` | `null`  | The date should a valid ISO 8601 format, ex: `2021-12-23` |

Only download files uploaded before this date.

```yaml
filters:
  before: null
```

# `after`

| Type             | Default | Additional Info                                           |
| ---------------- | ------- | --------------------------------------------------------- |
| `date` or `null` | `null`  | The date should a valid ISO 8601 format, ex: `2021-12-23` |

Only download files uploaded after this date.

```yaml
filters:
  after: null
```

# `filename_regex`

| Type                    | Default |
| ----------------------- | ------- |
| `NonEmptyStr` or `null` | `null`  |

Only download files if their filename match this regex expression

```yaml
filters:
  filename_regex: null
```

# `only_hosts`

| Type                | Default | Additional Info                                                      |
| ------------------- | ------- | -------------------------------------------------------------------- |
| `list[NonEmptyStr]` | `[]`    | This is an [`AdditiveArg`](../special_setting_types.md#additiveargs) |

You can supply hosts that you'd like the program to exclusively scrape/download from. This setting accepts any domain, even if they are no supported.

```yaml
filters:
  only_hosts: []
```

# `skip_hosts`

| Type                | Default | Additional Info                                                      |
| ------------------- | ------- | -------------------------------------------------------------------- |
| `list[NonEmptyStr]` | `[]`    | This is an [`AdditiveArg`](../special_setting_types.md#additiveargs) |

You can supply hosts that you'd like the program to skip, to not scrape/download from them. This setting accepts any domain, even if they are no supported.

```yaml
filters:
  skip_hosts: []
```

# `allow_files_with_no_extension`

| Type   | Default |
| ------ | ------- |
| `bool` | `false` |

Download files without an extension. These files could potentially be dangerous

{% hint style="info" %}
CDL internally assumes any file without an extension is an `.mp4` file. That means any option that applies to videos like `--no-videos` and `--video.size.min` will apply to them.
The actual file will still be downloaded without an extension
{% endhint %}

```yaml
filters:
  allow_files_with_no_extension: false
```

# Duration Limits

You can provide the maximum and minimum duration for audio and video files.

| Type                  | Default |
| --------------------- | ------- |
| `timedelta` or `null` | `null`  |

- A `timedelta` input is expected to be a valid ISO 8601 timespan, ex: `P10DT2H30M10S`
- An `int` input is assumed to be seconds
- A `str` input is expected to be in the format; `<value> <unit>`, ex: `10 days`.

A value of `0` or `null` means no limit

```yaml
filters:
  duration:
    audio:
      max: null
      min: null
    video:
      max: null
      min: null
```

# File Size Limits

You can provide the maximum and minimum file size for each file "type".

All options on this category take a `ByteSize` input ([more info here](../special_setting_types.md#bytesize)).

| Type                 | Default |
| -------------------- | ------- |
| `ByteSize` or `null` | `null`  |

Setting any of these options to `0` or `null` means that limit is disabled

```yaml
filters:
  sizes:
    audio:
      max: null
      min: null
    image:
      max: null
      min: null
    non_media:
      max: null
      min: null
    video:
      max: null
      min: null
```

# Files

Enable/Disable downloads by file type

| Type   | Default |
| ------ | ------- |
| `bool` | `true`  |

```yaml
filters:
  files:
    audio: true
    images: true
    non_media: true
    videos: true
```
