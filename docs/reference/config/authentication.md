---
description: These are all of the configuration options for Authentication.
icon: user-lock
---

These settings allow you to provide login credentials for sites. All of them go under the `auth` namespace of the config file and they only accept string as values (or `null`)

| Type            | Default |
| --------------- | ------- |
| `str` or `null` | `null`  |

<details>

<summary>DeviantArt</summary>

DeviantArt requires OAuth2 application credentials to access its API. Register an application at <https://www.deviantart.com/developers/apps> to obtain your `client_id` and (for confidential apps) `client_secret`.

**Option 1: App-only authentication (`client_credentials`)** — works for public galleries, deviations, and collections:

```yaml
auth:
  deviantart:
    client_id: <my_client_id>
    client_secret: <my_client_secret>
```

**Option 2: User authentication (`refresh_token`)** — supports user-scoped/PKCE OAuth2 sessions (leave `client_secret` empty if using a public PKCE client, or include it for confidential clients):

```yaml
auth:
  deviantart:
    client_id: <my_client_id>
    client_secret: <my_client_secret_optional>
    refresh_token: <my_refresh_token>
```

{% hint style="info" %}
Rotated refresh tokens are cached automatically in `cache.json` across runs. If you update `refresh_token` in `config.yaml`, the cached token is reset automatically.
{% endhint %}

</details>

<details>

<summary>Forums</summary>

{% hint style="warning" %}
Logging to forums with `Authentication` was deprecated in v6.7.0

You need to use cookie files.

See: [How to extract cookies (DDoSGuard or login errors) #839](https://github.com/Cyberdrop-DL/cyberdrop-dl/discussions/839)
{% endhint %}

</details>

<details>

<summary>GoFile</summary>

If you decide to pay for GoFile Premium (faster downloads, access to frozen files, etc.) you can provide your API key to `cyberdrop-dl` to use it.

```yaml
auth:
  gofile:
    api_key: <my_api_key>
```

You can get your API key from <https://gofile.io/myprofile>

</details>

<details>

<summary>JDownloader</summary>

These are the same values you use in `JDownloder 2` -> `settings` -> `MyJDownloader`

```yaml
auth:
  jdownloader:
    device_name: <my_device_name>
    password: <my_password>
    username: <my_username/email>
```

</details>

<details>

<summary>PixelDrain</summary>

If you decide to pay for PixelDrain premium (faster downloads, unlimited concurrent downloads, etc.) you can provide your API key to `cyberdrop-dl` to use it.

```yaml
auth:
  pixeldrain:
    api_key: <my_api_key>
```

You can get your API key from <https://pixeldrain.com/user/api_keys>

</details>

<details>

<summary>Real-Debrid</summary>

To download files from sites supported by Real-Debrid, you'll need to get the API token from your account.

```yaml
auth:
  real_debrid:
    api_key: <my_api_key>
```

You can get your API key here (you must be logged in): <https://real-debrid.com/apitoken>

</details>

<details>

<summary>Mega.nz</summary>

If you have premium or want to download files/folders only shared with you, provide CDL your account credentials:

```yaml
auth:
  mega_nz:
    email: <my_email>
    password: <my_password>
```

{% hint style="warning" %}
Accounts with 2 factor authentication (2FA) are NOT supported
{% endhint %}

</details>
