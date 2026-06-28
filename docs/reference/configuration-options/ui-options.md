---
description: These are the options for controlling the UI of the program
---

# UI Options

### `mode`

| Type                                            | Default      |
| ----------------------------------------------- | ------------ |
| `DISABLED`, `ACTIVITY`,`SIMPLE` or `FULLSCREEN` | `FULLSCREEN` |

UI can have 1 of these values:

- `DISABLED` : no output at all
- `ACTIVITY` : only shows a spinner with the text `running CDL...`
- `SIMPLE`: shows spinner + simplified progress bar
- `FULLSCREEN`: shows the normal UI/progress view

{% hint style="info" %}
Values are case insensitive, ex: both `disabled` and `DISABLED` are valid
{% endhint %}

```yaml
ui:
  mode: fullscreen
```

### `portrait`

| Type   | Default |
| ------ | ------- |
| `Bool` | `False` |

Force CDL to run with a vertical layout

```yaml
ui:
  portrait: false
```

## `refresh_rate`

| Type          | Default |
| ------------- | ------- |
| `PositiveInt` | `10`    |

This is the refresh rate per second for the UI.

```yaml
ui:
  refresh_rate: 10.0
```

### `show_stats`

| Type   | Default |
| ------ | ------- |
| `Bool` | `true`  |

Show stats report at the end of a run

```yaml
ui:
  show_stats: true
```
