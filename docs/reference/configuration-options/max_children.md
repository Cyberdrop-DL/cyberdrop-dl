# Max Children

## `max_children`

| Type                   | Default |
| ---------------------- | ------- |
| `list[NonNegativeInt]` | `[]`    |

Limit the number of items to scrape using a tuple of up to 4 positions. Each position defines the maximum number of sub-items (`children_limit`) a specific type of `scrape_item` will have:

1. Max number of children from a **FORUM URL**
2. Max number of children from a **FORUM POST**
3. Max number of children from a **FILE HOST PROFILE**
4. Max number of children from a **FILE HOST ALBUM**

Using `0` on any position means no limit on the number of children for that type of `scrape_item`. Any tailing value not supplied is assumed as `0`

### Examples

{% tabs %}
{% tab title="example 1" %}
Limit **FORUM** scrape to 15 posts max, grab all links and media within those posts, but only scrape a maximum of 10 items from each link in a post:

```shell
--maximum-number-of-children 15 0 10

```

{% endtab %}

{% tab title="example 2" %}
Only grab the first link from each post in a forum, but that link will have no `children_limit`:

```shell
--maximum-number-of-children 0 1
```

{% endtab %}

{% tab title="example 3" %}
Only grab the first **POST** / **ALBUM** from a **FILE_HOST_PROFILE**

```shell
--maximum-number-of-children 0 0 1
```

{% endtab %}

{% tab title="example 4" %}
No **FORUM** limit, no **FORUM_POST** limit, no **FILE_HOST_PROFILE** limit, maximum of 20 items from any **FILE_HOST_ALBUM**:

```shell
    --maximum-number-of-children 0 0 0 20
```

{% endtab %}
{% endtabs %}

```yaml
max_children:
  album: 0
  forum: 0
  forum_post: 0
  profile: 0
```
