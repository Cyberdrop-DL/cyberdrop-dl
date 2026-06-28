# `attempts`

| Type          | Default |
| ------------- | ------- |
| `PositiveInt` | `2`     |

The number of download attempts per file. Some conditions are never retried (such as a `404` HTTP status)

```yaml
downloads:
  attempts: 2
```

# `delay`

| Type               | Default |
| ------------------ | ------- |
| `NonNegativeFloat` | `0.0`   |

Number of seconds to wait in between downloads to the same domain.

Some domains have internal limits set by the program, which can not be modified:

- `bunkr`: 0.5
- `nhentai.net`: 1

```yaml
downloads:
  delay: 0.0
```

# `speed_limit`

| Type       | Default |
| ---------- | ------- |
| `ByteSize` | `0`     |

{% hint style="info" %}
This setting specifies speed and it's interpreted as `<value> / second`. ex: `8MB` means `8MB/s`
{% endhint %}

This is the max rate of downloading in bytes (per second) for all downloads combined. Set to `0` to disable

```yaml
downloads:
  speed_limit: 0B
```

# `concurrent_segments`

| Type          | Default |
| ------------- | ------- |
| `PositiveInt` | `10`    |

Allow up to `<N>` HLS segments to be downloaded concurrently.

```yaml
downloads:
  concurrent_segments: 10
```

# `jitter`

| Type               | Default |
| ------------------ | ------- |
| `NonNegativeFloat` | `0.0`   |

Additional number of seconds to wait in between downloads. CDL will wait an additional random number of seconds in between 0 and the `jitter` value.

```yaml
downloads:
  jitter: 0.0
```

# `concurrency`

| Type          | Default |
| ------------- | ------- |
| `PositiveInt` | `15`    |

This is the maximum number of files that can be downloaded simultaneously.

```yaml
downloads:
  concurrency: 15
```

# `concurrency_per_domain`

| Type          | Default |
| ------------- | ------- |
| `PositiveInt` | `5`     |

This is the maximum number of files that can be downloaded from a single domain simultaneously.

Some domains have internal limits set by the program, which can not be modified:

- `bunkr`: 1 per unique server
- `cyberfile`: 1
- `noodlemagazine`: 2
- `4chan`: 1
- `pixeldrain`: 2
- `xxxbunker`: 2

```yaml
downloads:
  concurrency_per_domain: 5
```

# `skip_and_mark_completed`

| Type   | Default |
| ------ | ------- |
| `bool` | `false` |

Skip the download process for every file and mark them as downloaded in the database.

```yaml
downloads:
  skip_and_mark_completed: false
```

# `slow_speed`

| Type       | Default |
| ---------- | ------- |
| `ByteSize` | `0`     |

{% hint style="info" %}
This setting specifies speed and it's interpreted as `<value> / second`. ex: `8MB` means `8MB/s`
{% endhint %}

Downloads with a speed lower than this value for more than 10 seconds will be skipped. Set to `0` to disable

```yaml
downloads:
  slow_speed: 0B
```
