# JDownloader

## `enabled`

| Type   | Default |
| ------ | ------- |
| `bool` | `false` |

Send unsupported URLs to JDdownloader. All other JDownloader settings are ignored if this is `false`

```yaml
jdownloader:
  enabled: false
```

## `autostart`

| Type   | Default |
| ------ | ------- |
| `bool` | `false` |

Setting this to `true` will make JDownloader start downloads as soon as they are sent.

```yaml
jdownloader:
  autostart: false
```

## `download_dir`

| Type             | Default |
| ---------------- | ------- |
| `Path` or `null` | `null`  |

The `download_dir` jdownloader will use. A `null` value (the default) will make JDownloader use the same `download_dir` as `cyberdrop-dl`.
Use this option as path mapping when JDownloader is running on a different host / docker.

```yaml
jdownloader:
  download_dir: null
```

## `whitelist`

| Type                | Default |
| ------------------- | ------- |
| `list[NonEmptyStr]` | `[]`    |

List of domain names. An unsupported URL will only be sent to jdownloader if its host is found on the list. An empty whitelist (the default) will disable this functionality, sending any unsupported URL to jdownloader.

```yaml
jdownloader:
  whitelist: []
```
