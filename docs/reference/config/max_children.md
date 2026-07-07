# Max Children

Limit the number of items to scrape. Each option defines the maximum number of sub-items a specific type of `scrape_item` will have:

1. Max number of children from a **FORUM URL**
2. Max number of children from a **FORUM POST**
3. Max number of children from a **FILE HOST PROFILE**
4. Max number of children from a **FILE HOST ALBUM**

Using `0` for any option means no limit on the number of children for that type.

```yaml
max_children:
  forum: 0
  forum_post: 0
  profile: 0
  album: 0
```

### Examples

{% tabs %}
{% tab title="example 1" %}
Scrape up to 15 forum posts max, grab all links and media within those posts, but only scrape a maximum of 10 items from each link in a post:

```yaml
max_children:
  forum: 15
  forum_post: 0
  profile: 10
  album: 0
```

{% endtab %}

{% tab title="example 2" %}
Only grab the first link from each post in a forum, but that link will have no limit of children:

```yaml
max_children:
  forum: 0
  forum_post: 1
  profile: 0
  album: 0
```

{% endtab %}

{% tab title="example 3" %}
Only grab the first **POST** / **ALBUM** from a profile

```yaml
max_children:
  forum: 0
  forum_post: 0
  profile: 1
  album: 0
```

{% endtab %}

{% tab title="example 4" %}
No limit on the number of posts, no limit of links inside a posts, no limits on a profile, maximum of 20 items from any album:

```yaml
max_children:
  forum: 0
  forum_post: 0
  profile: 0
  album: 20
```

{% endtab %}
{% endtabs %}
