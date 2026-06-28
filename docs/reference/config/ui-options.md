---
description: These are the options for controlling the UI of the program
---

# `mode`

| Type                                            | Default      |
| ----------------------------------------------- | ------------ |
| `DISABLED`, `ACTIVITY`,`SIMPLE` or `FULLSCREEN` | `FULLSCREEN` |

- `DISABLED` : no output at all, only log messages (if enabled)
- `ACTIVITY` : only shows a spinner with the text `running cyberdrop-dl vX.Y.Z...`
- `SIMPLE`: shows spinner + simplified progress bar
- `FULLSCREEN`: shows the normal UI/progress view

```yaml
ui:
  mode: fullscreen
```

{% hint style="info" %}
Values are case insensitive, ex: both `disabled` and `DISABLED` are valid
{% endhint %}

# `portrait`

| Type   | Default |
| ------ | ------- |
| `Bool` | `False` |

Force CDL to run with a vertical layout

```yaml
ui:
  portrait: false
```

# `refresh_rate`

| Type            | Default |
| --------------- | ------- |
| `PositiveFloat` | `10.0`  |

Refresh the UI <n> times per second. Changing this value may help with screen flickering

```yaml
ui:
  refresh_rate: 10.0
```

# `show_stats`

| Type   | Default |
| ------ | ------- |
| `Bool` | `true`  |

Show stats report at the end of a run

```yaml
ui:
  show_stats: true
```
