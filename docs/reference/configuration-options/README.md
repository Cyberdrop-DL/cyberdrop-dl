---
icon: sliders
description: Here's how configuration works.
---

# Configuration Options

You can setup a configuration file to customize the default behaviour of `cyberdrop-dl`. All CLI options have a config equivalent
but some options (like account credentials) can only be provided via config file.

The config file format is YAML and it _must_ have a `.yaml` or `.yml` extension. `cyberdrop-dl` will not created a config file by default.
You can manually create a config with all the default settings using the `Edit config` option on the main menu or running the command `cyberdrop-dl config new`

`cyberdrop-dl` will always look for a config file at these default locations:

- Windows: `%AppData%/cyberdrop-dl/config.yaml`
- macOS/Linux/Android: `${XDG_CONFIG_HOME}/cyberdrop-dl/config.yaml` or `~/.config/cyberdrop-dl/config.yaml`

You can also provide a config file manually via the `--config-file` CLI argument. If provided, the default config file will be ignored (if it exists).
A file provided by `--config-file` _must_ exists already. `cyberdrop-dl` will refuse to run otherwise.

Config files can have partial settings. You do not have to specific every single option on the files, just the ones you want to use/override.

For example, the following is a valid config that specifies only 2 settings:

```yaml
dump_json: true
ignore_history: true
```

{% hint style="info" %}
Options provided explicit via CLI arguments will always take priority over config options.

Option will apply in this order:

CLI Options > options from `--config-file` (if provided) > options from default config file (if it exists) > Internal defaults of the program
{% endhint %}
