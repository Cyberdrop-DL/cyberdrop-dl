# `connection_timeout`

| Type          | Default |
| ------------- | ------- |
| `PositiveInt` | `15`    |

The number of seconds to wait while connecting to a website before timing out

{% hint style="info" %} This value will also be used for Flaresolverr (if enabled) as the max number of seconds to solve a CAPTCHA challenge {% endhint %}

```yaml
network:
  connection_timeout: 15.0
```

# `rate_limit`

| Type            | Default |
| --------------- | ------- |
| `PositiveFloat` | `25.0`  |

This is the maximum number of requests that can be made by the program per second.

```yaml
network:
  rate_limit: 25.0
```

{% hint style="info" %}
This setting specifies speed and it's interpreted as `<value> / second`. ex: `25` means `25 requests / second`
{% endhint %}

{% hint style="info" %}
Rate limit is only taken into account while scraping, not for downloads
{% endhint %}

# `read_timeout`

| Type                      | Default |
| ------------------------- | ------- |
| `PositiveFloat` or `null` | `300.0` |

The number of seconds to wait while reading data from a website before timing out. A `null` value will make CDL keep the socket connection open indefinitely,
even if the server is not sending data anymore

```yaml
network:
  read_timeout: 300.0
```

# `flaresolverr`

| Type                | Default |
| ------------------- | ------- |
| `HttpURL` or `null` | `null`  |

[FlareSolverr](https://github.com/FlareSolverr/FlareSolverr) is a proxy server to bypass Cloudflare and `DDoS-Guard` protection. The provided value must be a valid `http` URL of an existing flaresolverr instance. Ex: `http://192.168.1.44:4000`

```yaml
network:
  flaresolverr: null
```

{% hint style="info" %}
`0.0.0.0` is NOT a valid IP address. To set up a flaresolverr instance running on the same machine as CDL, use `127.0.0.1` as the IP
{% endhint %}

{% hint style="warning" %}
This wiki does not cover flaresolverr setup process. If you need help, refer to their documentation. Please do not open issues related to flaresolverr or `DDoS-Guard`.
See: [How to extract cookies (DDoSGuard or login errors) #839](https://github.com/Cyberdrop-DL/cyberdrop-dl/discussions/839) for alternatives using cookies
{% endhint %}

# `proxy`

| Type                | Default |
| ------------------- | ------- |
| `HttpURL` or `null` | `null`  |

The proxy you want CDL to use. Only `http`/`https` proxies are supported. Ex: `https://user:password@ip:port`

```yaml
network:
  proxy: null
```

# `dump_responses`

| Type   | Default |
| ------ | ------- |
| `bool` | `False` |

CDL will save to disk a copy of every non binary request (text/HTML/JSON) as a single file. The files will be saved to a folder named `cdl_responses`, inside the parent folder of the main log file.

```yaml
network:
  dump_responses: false
```

{% hint style="info" %}
Flaresolverr responses are excluded. They are never dumped to disk
{% endhint %}

# `impersonate`

| Type                                                                             | Default | Action        |
| -------------------------------------------------------------------------------- | ------- | ------------- |
| `chrome", "edge", "safari", "safari_ios", "chrome_android", "firefox"` or `null` | `null`  | `store_const` |

Impersonation allows CDL to make requests and appear to be a legitimate web browser. This helps bypass bot-protection on some sites and it's required for any site that only accepts HTTP2 connections.

- The default value (`null`) means CDL will automatically use impersonation for crawlers that were programmed to use it.
- Passing an specific target (ex: `--impersonate chrome_android`) will make CDL use impersonation for all requests, using that tarjet

```yaml
network:
  impersonate: null
```

{% hint style="info" %}
The current default target is `chrome`. The default target can change on any new release without notice, even minor versions
{% endhint %}

# `ssl_context`

| Type                    | Default              |
| ----------------------- | -------------------- |
| `NonEmptyStr` or `null` | `truststore+certifi` |

Context that will used to verify SSL connections. Valid values are:

- `truststore`: Will use certificates already included with the OS

- `certifi`: Will use certificates bundled with the `certifi` version available at the release of the current CDL version

- `truststore+certifi`: Will use certificates already included with the OS, with a fallback to `certifi` for missing certificates

- `null`: Will completely disable SSL verification, allowing insecure connections via `HTTP`.

Setting this to `null` will allow the program to connect to websites without SSL encryption (insecurely).

```yaml
network:
  ssl_context: truststore+certifi
```

{% hint style="danger" %}
Sensitive data may be exposed using an insecure connection. For your safety, is recommended to always use a secure HTTPS connection.
{% endhint %}

# `user_agent`

| Type          | Default                                                                  |
| ------------- | ------------------------------------------------------------------------ |
| `NonEmptyStr` | `Mozilla/5.0 (X11; Linux x86_64; rv:150.0) Gecko/20100101 Firefox/150.0` |

The user agent is the signature of your browser. Some sites use it to identify if the request came from a human or a robot.
You can google "what is my user agent" to get yours.

```yaml
network:
  user_agent: Mozilla/5.0 (X11; Linux x86_64; rv:150.0) Gecko/20100101 Firefox/150.0
```

{% hint style="info" %}
If you use flaresolverr, this value **MUST** match with flaresolverr's user agent. Otherwise, flaresolverr cookies won't work
{% endhint %}

{% hint style="info" %}
These crawlers will ignore custom user-agents and will always use `cyberdrop-dl/<version>`

<!-- START_CUSTOM_UA_CRAWLERS -->
- Archive.org
- E621
- MegaNz
- RealDebrid
- Transfer.it
<!-- END_CUSTOM_UA_CRAWLERS -->

{% endhint %}
