---
icon: envelope-open-text
description: These are the options to setup notifications from CDL.
---

`cyberdrop-dl` generates a report at the end of a run with stats about all the downloads, total runtime, errors, deduplication report, etc.
By default, this report is only shown in the console and at the end of the main log file.

You can set up CDL to sent you the report via discord, email, a native notification of your OS, telegram and many other services.

# Notifications via Discord

To get notifications via discord, you need to provide a valid discord webhook URL in your config file.

You can learn how to setup a webhook following the [official discord guide](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks).

Optionally, you can add the tag `attach_logs=` as a prefix to your webhook url. This will tell CDL to include a copy of the main log as an attachment to Discord.

| Type                   | Default | Restrictions                                    |
| ---------------------- | ------- | ----------------------------------------------- |
| `AppriseURL` or `null` | `null`  | The scheme of the URL must be `http` or `https` |

```yaml
notifications:
  webhook: <URL>
```

{% hint style="info" %}
Attachments have a size limit of 25MB. If you use `attach_logs=` and the main log file exceeds this limit, CDL will ignore it and send the notification without it
{% endhint %}

Example:

> `attach_logs=https://discord.com/api/webhooks/webhook_id/webhook_token`

# Notifications to other services (via Apprise)

`cyberdrop-dl` uses [Apprise](https://github.com/caronc/apprise) to send notifications to any of the services than they support.

{% hint style="info" %}
`apprise` is an an optional dependency; It's not installed by default.

To install `cyberdrop-dl` with `apprise`, add it as extra during installation:

```shell
uv tool install cyberdrop-dl-patched[apprise]
```

{% endhint %}

## How to setup Apprise

To send notifications via Apprise, paste all your Apprrise URLs in your config file. URLs must be in the format of one of the supported apprise services.

You can check the full list of supported services [here](https://appriseit.com/services/).

Apprise services also support the `attach_logs=` tag to send the main log as an attachment.

```yaml
notifications:
  apprise: []
```

{% hint style="info" %}
You can build the URL interactively on their website: <https://appriseit.com/url-builder>
{% endhint %}

## Troubleshooting Apprise notifications

`cyberdrop-dl` will show you a message at the end of a run telling you if the apprise notifications were successfully sent or not. If you are having trouble getting notifications via Apprise, follow their [troubleshooting guide](https://github.com/caronc/apprise/wiki/Troubleshooting).

# Examples

{% tabs %}
{% tab title="Email" %}
To get notifications via email, use this URL format in your `apprise.txt` file:

```shell
mailto://user:password@domain.com
```

{% endtab %}

{% tab title="Email + Logs" %}
Add `attach_logs` to your email URL in your `apprise.txt` file:

```shell
attach_logs=mailto://user:password@domain.com
```

{% endtab %}

{% tab title="Native OS notifications" %}
Some operating systems require additional dependencies for notifications to work. `cyberdrop-dl` includes the required dependencies for Windows if you installed it
with the [`apprise`] extra. Follow the url on the OS name to get additional information on how to set them up.

| OS                                                                   | Syntax                                              |
| -------------------------------------------------------------------- | --------------------------------------------------- |
| [Linux (DBus Notifications)](https://appriseit.com/services/dbus/)   | `dbus://` <br> `qt://` <br> `glib://` <br> `kde://` |
| [Linux (Gnome Notifications)](https://appriseit.com/services/gnome/) | `gnome://`                                          |
| [macOS](https://appriseit.com/services/macosx/)                      | `macosx://`                                         |
| [Windows](https://appriseit.com/services/windows/)                   | `windows://`                                        |

{% endtab %}

{% tab title="Discord + Logs" %}
Add `attach_logs` to the `webhook_url` config option:

```shell
attach_logs=https://discord.com/api/webhooks/webhook_id/webhook_token
```

{% endtab %}
{% endtabs %}
