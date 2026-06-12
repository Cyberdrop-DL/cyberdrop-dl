# Browser Cookies

These can be used for websites that require login or to pass DDoS-Guard challenges.

{% hint style="warning" %}
The `user-agent` config value **MUST** match the `user-agent` of the browser from which you imported the cookies. If they do not match, the cookies will not work
{% endhint %}

## `cookies`

| Type             | Default |
| ---------------- | ------- |
| `Path` or `None` | `None`  |

Path to a file/folder with Netscape cookies with a `.txt` extension. If the path is a folder, all `.txt` in the folder are read (Non recursive)

You can extract the cookies from your browser using tools like [cookie-editor](https://cookie-editor.com) and save them as a `.txt` file.
The file must be a Netscape formatted cookie file. You can use any name for the file as long as it has a `.txt` extension.

See: [How to extract cookies (DDoSGuard or login errors) #839](https://github.com/Cyberdrop-DL/cyberdrop-dl/discussions/839) for detailed instructions

{% hint style="info" %}
Multiple cookie files are supported. You could have a `SocialMediaGirls.txt` file and a `cyberdrop.txt` file, for example
{% endhint %}
